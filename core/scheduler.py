"""APScheduler 定时调度封装

按 schedule_config 表配置的 cron 表达式自动触发各数据源的爬取。
单例模式：start()/stop() 全局一个 BackgroundScheduler。
"""

import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _APS_AVAILABLE = True
except ImportError:
    _APS_AVAILABLE = False
    BackgroundScheduler = None
    CronTrigger = None
    logger.warning("APScheduler not installed. Scheduler disabled.")


DISABLE_ENV = "DATAGRAB_DISABLE_SCHEDULER"

_scheduler: Optional["BackgroundScheduler"] = None
_lock = threading.Lock()
_initialized = False


def _import_scrape_runner():
    """延迟导入，避免循环依赖。"""
    from server.dependencies import create_job  # noqa: F401
    from server.routes.scrape import _run_scrape_job
    return create_job, _run_scrape_job


def _source_is_running(source_name: str) -> bool:
    """检查某数据源是否有 running 状态的任务（防重入）。"""
    from storage.database import job_count
    return job_count(source_name=source_name, status="running") > 0


def _scheduled_job_wrapper(source_id: int, source_name: str, limit_count: int):
    """APScheduler 回调：按数据源触发。

    - 防重入：已有 running 任务则跳过
    - 先创建 job 记录（status=pending），再同步调用 _run_scrape_job
    """
    try:
        if _source_is_running(source_name):
            logger.info(f"[Scheduler] skip {source_name}: already running")
            return

        create_job, run_job = _import_scrape_runner()
        job = create_job(
            source_id=source_id,
            source_name=source_name,
            limit_count=limit_count,
            params={"scheduled": True, "triggered_at": datetime.now().isoformat()},
        )
        logger.info(f"[Scheduler] start {source_name} limit={limit_count} job={job.job_id}")
        run_job(job.job_id, source_name, limit_count)
    except Exception as e:
        logger.exception(f"[Scheduler] job failed for {source_name}: {e}")


class DataGrabScheduler:
    """调度管理外壳（对外暴露 start/stop/reload/trigger/status）。"""

    def __init__(self):
        self._sched: Optional[BackgroundScheduler] = None
        self._job_ids: Dict[int, str] = {}  # source_id -> apscheduler job_id

    # ---- lifecycle ----
    def start(self):
        if not _APS_AVAILABLE:
            logger.warning("[Scheduler] APScheduler missing, not starting")
            return False
        if os.environ.get(DISABLE_ENV):
            logger.warning(f"[Scheduler] disabled via env {DISABLE_ENV}=1")
            return False
        if self._sched and self._sched.running:
            return True
        self._sched = BackgroundScheduler(timezone=os.environ.get("TZ", "Asia/Shanghai"))
        self._sched.start()
        self.reload()
        logger.info("[Scheduler] started")
        return True

    def stop(self):
        if self._sched and self._sched.running:
            self._sched.shutdown(wait=False)
            logger.info("[Scheduler] stopped")
        self._sched = None
        self._job_ids.clear()

    # ---- jobs ----
    def reload(self):
        """从 DB schedule_config 表重新加载所有启用项。"""
        if not (self._sched and self._sched.running):
            return
        import storage.topics as st
        from storage.database import source_get as src_get

        configs = st.schedule_list() or []
        # 先全清
        for jid in list(self._job_ids.values()):
            try:
                self._sched.remove_job(jid)
            except Exception:
                pass
        self._job_ids.clear()

        for cfg in configs:
            sid = cfg["source_id"]
            if sid == 0:
                # 全局默认配置：跳过，单独处理
                continue
            if not cfg.get("enabled") or not cfg.get("cron_expr"):
                continue
            # 数据源本身也要启用
            src = src_get(cfg.get("source_name", "")) if cfg.get("source_name") else None
            src_cfg = src or _source_by_id(sid)
            if not src_cfg or not src_cfg.get("enabled"):
                logger.info(f"[Scheduler] skip source_id={sid}: source disabled/missing")
                continue
            self._add_job(
                source_id=sid,
                source_name=src_cfg["name"],
                cron_expr=cfg["cron_expr"],
                limit_count=cfg.get("limit_count", 10),
            )
        logger.info(f"[Scheduler] reload done: {len(self._job_ids)} jobs registered")

    def _add_job(self, source_id: int, source_name: str, cron_expr: str, limit_count: int):
        """注册单个 cron 作业。"""
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
        except Exception as e:
            logger.warning(f"[Scheduler] invalid cron '{cron_expr}' for {source_name}: {e}")
            return
        jid = f"sched_source_{source_id}"
        self._sched.add_job(
            _scheduled_job_wrapper,
            trigger=trigger,
            id=jid,
            replace_existing=True,
            misfire_grace_time=300,  # 5 分钟内的错过仍然执行
            coalesce=True,          # 多个错过合并为一次
            max_instances=1,
            args=[source_id, source_name, limit_count],
        )
        self._job_ids[source_id] = jid
        logger.debug(f"[Scheduler] registered {source_name} cron='{cron_expr}' limit={limit_count}")

    def remove_job(self, source_id: int):
        if not self._sched:
            return
        jid = self._job_ids.pop(source_id, None)
        if jid:
            try:
                self._sched.remove_job(jid)
            except Exception:
                pass

    def trigger_now(self, source_name: str, limit_count: int = 10) -> Optional[str]:
        """手动立即触发一次（不经过 cron）。返回 job_id 或 None。"""
        from storage.database import source_get as src_get
        src = src_get(source_name)
        if not src:
            return None
        if _source_is_running(source_name):
            logger.info(f"[Scheduler] trigger_now skip {source_name}: running")
            return None
        try:
            create_job, run_job = _import_scrape_runner()
            job = create_job(
                source_id=src["id"],
                source_name=source_name,
                limit_count=limit_count,
                params={"manual": True, "triggered_at": datetime.now().isoformat()},
            )
            # 在独立线程跑，不阻塞 API 调用
            t = threading.Thread(
                target=run_job, args=(job.job_id, source_name, limit_count),
                daemon=True, name=f"sched_manual_{job.job_id[:8]}"
            )
            t.start()
            return job.job_id
        except Exception as e:
            logger.exception(f"[Scheduler] trigger_now failed {source_name}: {e}")
            return None

    # ---- status ----
    def status(self) -> Dict:
        """返回调度器运行状态 + 已注册作业列表。"""
        running = bool(self._sched and self._sched.running)
        jobs: List[Dict] = []
        if self._sched and running:
            for j in self._sched.get_jobs():
                jobs.append({
                    "id": j.id,
                    "name": j.name,
                    "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                    "trigger": str(j.trigger),
                })
        return {"running": running, "disabled_env": bool(os.environ.get(DISABLE_ENV)),
                "aps_available": _APS_AVAILABLE, "jobs": jobs}


# ============================
#  全局单例
# ============================

_instance: Optional[DataGrabScheduler] = None


def get_scheduler() -> DataGrabScheduler:
    global _instance
    if _instance is None:
        _instance = DataGrabScheduler()
    return _instance


def _source_by_id(source_id: int):
    """按 id 取 source（storage.database 只有按 name 取，这里补一条）。"""
    from storage.database import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM source WHERE id = %s", (source_id,))
            return cur.fetchone()
    finally:
        conn.close()
