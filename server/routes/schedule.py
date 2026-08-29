"""调度配置路由

GET    /api/schedules                 — 所有调度配置（含数据源名称）
POST   /api/schedules                 — 新增/覆盖某数据源调度配置
PATCH  /api/schedules/{source_id}    — 更新调度配置
DELETE /api/schedules/{source_id}    — 删除调度配置
GET    /api/schedules/status          — 调度器运行状态 + 已注册 cron
POST   /api/schedules/reload          — 从 DB 重新加载作业
POST   /api/schedules/trigger/{source_name} — 立即手动触发一次
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

import storage.topics as st
from core.scheduler import get_scheduler
from server.models.analytics_models import (
    ScheduleConfigCreate, ScheduleConfigOut, ScheduleConfigUpdate,
    ScheduleStatus, ScheduleTriggerNowResponse,
)

router = APIRouter()


@router.get("/schedules", response_model=List[ScheduleConfigOut])
def list_schedules():
    rows = st.schedule_list() or []
    return [ScheduleConfigOut(**r) for r in rows]


@router.post("/schedules", response_model=ScheduleConfigOut)
def create_or_update_schedule(body: ScheduleConfigCreate):
    from storage.database import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, enabled FROM source WHERE id = %s", (body.source_id,))
            src = cur.fetchone()
    finally:
        conn.close()
    if not src:
        raise HTTPException(status_code=404, detail=f"Source id={body.source_id} not found")

    st.schedule_upsert(body.source_id, body.cron_expr, body.limit_count, body.enabled)
    row = st.schedule_get(body.source_id) or {}
    row["source_name"] = src.get("name")
    row["source_enabled"] = src.get("enabled")

    # 立即生效
    sched = get_scheduler()
    if body.enabled and body.cron_expr:
        sched.reload()
    else:
        sched.remove_job(body.source_id)
        sched.reload()
    return ScheduleConfigOut(**row)


@router.patch("/schedules/{source_id}", response_model=ScheduleConfigOut)
def update_schedule(source_id: int, body: ScheduleConfigUpdate):
    existing = st.schedule_get(source_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Schedule for source_id={source_id} not found")
    cron_expr = body.cron_expr if body.cron_expr is not None else existing["cron_expr"]
    limit_count = body.limit_count if body.limit_count is not None else existing["limit_count"]
    enabled = body.enabled if body.enabled is not None else existing["enabled"]
    st.schedule_upsert(source_id, cron_expr, limit_count, enabled)
    sched = get_scheduler()
    sched.reload()
    row = st.schedule_get(source_id) or {}
    # 补充数据源信息
    rows_with_join = st.schedule_list() or []
    for r in rows_with_join:
        if r["source_id"] == source_id:
            row = r
            break
    return ScheduleConfigOut(**row)


@router.delete("/schedules/{source_id}")
def delete_schedule(source_id: int):
    existing = st.schedule_get(source_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Schedule for source_id={source_id} not found")
    st.schedule_delete(source_id)
    sched = get_scheduler()
    sched.remove_job(source_id)
    return {"ok": True}


@router.get("/schedules/status", response_model=ScheduleStatus)
def scheduler_status():
    sched = get_scheduler()
    return ScheduleStatus(**sched.status())


@router.post("/schedules/reload", response_model=ScheduleStatus)
def scheduler_reload():
    sched = get_scheduler()
    sched.reload()
    return ScheduleStatus(**sched.status())


@router.post("/schedules/trigger/{source_name}", response_model=ScheduleTriggerNowResponse)
def trigger_source_now(
    source_name: str,
    limit: int = Query(default=10, ge=1, le=500, description="抓取条数上限"),
):
    sched = get_scheduler()
    job_id = sched.trigger_now(source_name, limit_count=limit)
    if job_id is None:
        return ScheduleTriggerNowResponse(
            ok=False,
            message=f"Source '{source_name}' not found or already running"
        )
    return ScheduleTriggerNowResponse(ok=True, job_id=job_id, message="Triggered")
