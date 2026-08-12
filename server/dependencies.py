"""FastAPI 依赖注入

管理 Engine 单例、MySQL 初始化、爬取任务状态。

任务持久化策略：
- scrape_job 表为主存储，任务状态/结果计数/错误全部入库
- 内存字典 _jobs_cache 仅缓存 running 中任务的最新解析结果，
  用于任务完成时一次性返回给 GET /scrape/{job_id}，
  进程重启后从数据库恢复任务状态（结果预览丢失，但 total 等元数据保留）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List, Any
import uuid
import threading

from loguru import logger

from core.engine import ScraperEngine
from storage.database import init_database
from scrapers.generic_scraper import GenericScraper

# ---- Engine Singleton ----

_engine: Optional[ScraperEngine] = None


def _seed_default_sources():
    """确保默认数据源（redroom）已存在于 source 表。"""
    from storage.database import source_get, source_create

    defaults = [
        {
            "name": "redroom",
            "url": "http://localhost:3000",
            "description": "RedroomCN 地缘政治情报平台 (tRPC API)",
            "source_type": "api",
            "selectors": {"endpoint": "articles.list", "region": "MENA"},
        },
    ]
    for src in defaults:
        if not source_get(src["name"]):
            sid = source_create(**src)
            logger.info(f"Seeded default source: {src['name']} (id={sid})")


def init_engine():
    """初始化 ScraperEngine + MySQL 数据库。"""
    global _engine

    # 初始化 MySQL
    logger.info("Initializing MySQL database...")
    try:
        init_database()
        logger.info("MySQL database ready: DataGrab (source + scrape_job + grab tables)")
    except Exception as e:
        logger.error(f"MySQL init failed: {e}")
        raise

    # 种子数据源
    _seed_default_sources()

    # 初始化引擎
    logger.info("Initializing ScraperEngine...")
    _engine = ScraperEngine()

    # 注册通用爬虫
    _engine.register_scraper("generic", GenericScraper)

    logger.info("Engine ready")


def cleanup_engine():
    """清理引擎资源。"""
    global _engine
    if _engine:
        _engine.cleanup()
        _engine = None


def get_engine() -> ScraperEngine:
    """FastAPI 依赖：返回共享的 ScraperEngine 实例。"""
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    return _engine


# ---- Job Store（MySQL 主存 + 内存结果缓存）----

@dataclass
class ScrapeJob:
    """任务运行时对象（数据库行的镜像 + 结果缓存）。"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: int = 0
    source_name: str = ""
    status: str = "pending"
    limit_count: int = 20
    total: int = 0
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # 仅内存：任务完成时缓存的解析结果预览，供 API 一次性返回
    results: List[Any] = field(default_factory=list)


# 内存缓存：仅存 running 中任务的最新结果，避免轮询期间反复读库
_jobs_cache: Dict[str, ScrapeJob] = {}
_jobs_lock = threading.Lock()


def create_job(source_id: int, source_name: str, limit_count: int = 20,
               params: dict = None) -> ScrapeJob:
    """创建任务：写库 + 加内存缓存。"""
    from storage.database import job_create

    job = ScrapeJob(
        source_id=source_id,
        source_name=source_name,
        limit_count=limit_count,
    )
    job_create(job.job_id, source_id, source_name, limit_count, params)
    with _jobs_lock:
        _jobs_cache[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[ScrapeJob]:
    """获取任务：优先读内存缓存，未命中则从数据库恢复。"""
    from storage.database import job_get

    with _jobs_lock:
        cached = _jobs_cache.get(job_id)
        if cached is not None:
            return cached

    # 内存未命中（可能是服务重启后），从数据库恢复
    row = job_get(job_id)
    if not row:
        return None
    job = ScrapeJob(
        job_id=row["job_id"],
        source_id=row["source_id"],
        source_name=row["source_name"],
        status=row["status"],
        limit_count=row.get("limit_count", 20),
        total=row.get("total", 0),
        error=row.get("error"),
        created_at=row["created_at"] if isinstance(row.get("created_at"), datetime)
                   else _parse_dt(row.get("created_at")),
        started_at=_parse_dt(row.get("started_at")),
        completed_at=_parse_dt(row.get("completed_at")),
        # results 预览不持久化，恢复后为空
    )
    with _jobs_lock:
        _jobs_cache[job_id] = job
    return job


def update_job(job_id: str, **kwargs):
    """更新任务：同步写库 + 更新内存缓存。"""
    from storage.database import job_update

    job_update(job_id, **kwargs)
    with _jobs_lock:
        job = _jobs_cache.get(job_id)
        if job:
            for k, v in kwargs.items():
                if hasattr(job, k) and v is not None:
                    setattr(job, k, v)


def set_job_results(job_id: str, results: List[Any]):
    """缓存任务结果预览（仅内存，不落库）。"""
    with _jobs_lock:
        job = _jobs_cache.get(job_id)
        if job:
            job.results = results


def evict_job(job_id: str):
    """任务结束并确认无需再轮询后，从内存缓存移除。"""
    with _jobs_lock:
        _jobs_cache.pop(job_id, None)


def _parse_dt(v) -> Optional[datetime]:
    """容错解析数据库返回的 datetime 字段。"""
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", ""))
    except Exception:
        return None
