"""分析与热点监控路由

GET  /api/analytics/summary           — Dashboard 顶部统计卡
GET  /api/analytics/trend/keywords    — 关键词趋势时间序列（多选 keyword_id）
GET  /api/analytics/trend/topics      — 主题聚合趋势时间序列
GET  /api/analytics/top-keywords      — 最近 N 小时关键词命中排行
GET  /api/analytics/topic-dist        — 主题分布（饼图数据）
GET  /api/analytics/hourly-articles   — 近 24h 每小时文章数（柱图数据）

GET  /api/analytics/events            — 热点事件列表（分页+筛选）
POST /api/analytics/events/read       — 事件标记已读
POST /api/analytics/recalc            — 历史数据重算（离线分析）
"""

import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

import storage.topics as st
from storage.database import get_connection
from core.analyzer import analyze_history
from server.models.analytics_models import (
    DashboardSummary, EventMarkReadRequest, HotspotEventListResponse,
    HotspotEventOut, KeywordTrendSeries, RecalcRequest, RecalcResponse,
    TopicTrendSeries, TrendPoint,
)

router = APIRouter()


# ============================
#  内部工具
# ============================

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _bucket_to_iso(dt) -> str:
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


# ============================
#  Dashboard Summary
# ============================

@router.get("/analytics/summary", response_model=DashboardSummary)
def dashboard_summary(
    hours: int = Query(default=24, ge=1, le=720, description="统计窗口小时数"),
):
    from storage.database import get_connection, grab_count
    from core.analyzer import _relevance_threshold
    from datetime import timezone

    now = datetime.now()
    start_24h = now - timedelta(hours=hours)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    threshold = _relevance_threshold()

    # 1. 近 24h 新增文章 + 相关性指标
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM grab WHERE grabbed_at >= %s", (start_24h,))
            articles_24h = cur.fetchone()["cnt"]

            cur.execute(
                """
                SELECT
                  COUNT(*)                                                     AS scored,
                  SUM(CASE WHEN relevance_score >= %s THEN 1 ELSE 0 END)        AS high_rel,
                  SUM(CASE WHEN keyword_mentioned = 1 THEN 1 ELSE 0 END)       AS mentioned,
                  COALESCE(AVG(relevance_score), 0)                             AS avg_score,
                  COALESCE(AVG(CASE WHEN relevance_score IS NOT NULL
                               THEN relevance_score END), 0)                   AS avg_score_scored
                FROM grab
                WHERE grabbed_at >= %s
                """,
                (threshold, start_24h),
            )
            rel = cur.fetchone()
    finally:
        conn.close()

    scored = int(rel["scored"] or 0)
    high_rel = int(rel["high_rel"] or 0)
    mentioned = int(rel["mentioned"] or 0)
    avg_score_scored = float(rel["avg_score_scored"] or 0.0)
    high_rel_rate = (high_rel / scored) if scored > 0 else 0.0
    mentioned_rate = (mentioned / scored) if scored > 0 else 0.0

    # 2. 今日事件 & 未读 & 高级别
    today_events = st.event_count(start=today_start)
    unread_events = st.event_count(only_unread=True)
    high_level_events = st.event_count(level="high", start=today_start)

    # 3. 监控关键词总数 & 活跃主题（近 24h 至少 1 篇命中的）
    all_keywords = st.keyword_list(include_disabled=False) or []
    keywords_total = len(all_keywords)

    # 活跃主题：从 grab_keyword_hit 近 24h 分组
    conn = get_connection()
    active_topic_ids = set()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT topic_id FROM grab_keyword_hit h "
                "JOIN grab g ON h.grab_id = g.id "
                "WHERE g.grabbed_at >= %s",
                (start_24h,)
            )
            rows = cur.fetchall()
            for r in rows:
                if r["topic_id"]:
                    active_topic_ids.add(r["topic_id"])
    finally:
        conn.close()
    active_topics = len(active_topic_ids)

    # 4. Top 10 关键词（近 24h 命中文章数 + Query Expansion 变体/直接提及拆分）
    top_keywords: List[Dict[str, Any]] = []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.keyword_id, k.word, k.topic_id, t.name AS topic_name, t.color AS topic_color,
                       COUNT(DISTINCT h.grab_id)                                           AS article_cnt,
                       SUM(h.hit_count)                                                    AS hit_cnt,
                       SUM(CASE WHEN h.match_type='word'    THEN h.hit_count ELSE 0 END)    AS direct_hits,
                       SUM(CASE WHEN h.match_type='variant' THEN h.hit_count ELSE 0 END)    AS variant_hits,
                       COUNT(DISTINCT CASE WHEN h.match_type='word'    THEN h.grab_id END)  AS direct_grabs,
                       COUNT(DISTINCT CASE WHEN h.match_type='variant' THEN h.grab_id END)  AS variant_grabs,
                       MAX(JSON_LENGTH(k.variants))                                         AS variant_count
                FROM grab_keyword_hit h
                JOIN grab g ON h.grab_id = g.id
                JOIN keyword k ON h.keyword_id = k.id
                LEFT JOIN topic t ON h.topic_id = t.id
                WHERE g.grabbed_at >= %s
                GROUP BY h.keyword_id, k.word, k.topic_id, topic_name, topic_color
                ORDER BY article_cnt DESC LIMIT 10
                """,
                (start_24h,)
            )
            top_keywords = list(cur.fetchall())
    finally:
        conn.close()

    # 5. 主题分布（近 24h 各主题命中的独立文章数，同文章多词去重）
    topic_dist: List[Dict[str, Any]] = []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT h.topic_id, t.name, t.color, COUNT(DISTINCT h.grab_id) AS article_cnt "
                "FROM grab_keyword_hit h "
                "JOIN grab g ON h.grab_id = g.id "
                "JOIN topic t ON h.topic_id = t.id "
                "WHERE g.grabbed_at >= %s "
                "GROUP BY h.topic_id, t.name, t.color "
                "ORDER BY article_cnt DESC",
                (start_24h,)
            )
            topic_dist = list(cur.fetchall())
    finally:
        conn.close()

    summary = DashboardSummary(
        today_events=today_events,
        unread_events=unread_events,
        articles_24h=articles_24h,
        active_topics=active_topics,
        keywords_total=keywords_total,
        high_level_events=high_level_events,
        top_keywords=top_keywords,
        topic_distribution=topic_dist,
    )
    # 把相关性指标塞进去（不强制改 Pydantic 结构，额外字段不影响 response）
    summary_dict = summary.model_dump() if hasattr(summary, "model_dump") else summary.dict()
    summary_dict.update({
        "relevance_threshold": threshold,
        "scored_grabs": scored,
        "high_relevance_grabs": high_rel,
        "high_relevance_rate": round(high_rel_rate, 4),
        "keyword_mentioned_true": mentioned,
        "keyword_mentioned_rate": round(mentioned_rate, 4),
        "avg_relevance_score_scored": round(avg_score_scored, 2),
    })
    return summary_dict


# ============================
#  Trend Series
# ============================

@router.get("/analytics/trend/keywords", response_model=List[KeywordTrendSeries])
def keyword_trend(
    keyword_ids: str = Query(..., description="逗号分隔 keyword_id 列表，例如 1,3,7"),
    grain: str = Query(default="hour", pattern="^(hour|day)$"),
    days: int = Query(default=7, ge=1, le=90),
):
    try:
        kids = [int(x.strip()) for x in keyword_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="keyword_ids 必须是逗号分隔的整数列表")
    if not kids:
        return []
    now = datetime.now()
    if grain == "hour":
        start = now - timedelta(days=min(days, 7))
    else:
        start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = st.trend_query(kids, grain, start, now)

    # 查 keyword_id → (word, topic_id, color)
    conn = get_connection()
    kw_meta = {}
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(kids))
            cur.execute(
                f"SELECT k.id, k.word, k.topic_id, t.color FROM keyword k "
                f"LEFT JOIN topic t ON k.topic_id = t.id WHERE k.id IN ({placeholders})",
                kids,
            )
            for r in cur.fetchall():
                kw_meta[r["id"]] = (r["word"], r["topic_id"], r["color"])
    finally:
        conn.close()

    buckets_by_kw: Dict[int, List[TrendPoint]] = defaultdict(list)
    for r in rows:
        buckets_by_kw[r["keyword_id"]].append(TrendPoint(
            time_bucket=r["time_bucket"],
            article_cnt=int(r["article_cnt"]),
            hit_cnt=int(r["hit_cnt"]),
        ))
    result: List[KeywordTrendSeries] = []
    for kid in kids:
        word, topic_id, color = kw_meta.get(kid, (None, None, None))
        result.append(KeywordTrendSeries(
            keyword_id=kid, word=word, topic_id=topic_id, color=color,
            points=sorted(buckets_by_kw.get(kid, []), key=lambda p: p.time_bucket),
        ))
    return result


@router.get("/analytics/trend/topics", response_model=List[TopicTrendSeries])
def topic_trend(
    topic_ids: str = Query(..., description="逗号分隔 topic_id 列表"),
    grain: str = Query(default="hour", pattern="^(hour|day)$"),
    days: int = Query(default=7, ge=1, le=90),
):
    try:
        tids = [int(x.strip()) for x in topic_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="topic_ids 必须是逗号分隔的整数列表")
    if not tids:
        return []
    now = datetime.now()
    if grain == "hour":
        start = now - timedelta(days=min(days, 7))
    else:
        start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = st.trend_query_by_topics(tids, grain, start, now)

    topics = {t["id"]: t for t in (st.topic_list() or [])}

    buckets_by_topic: Dict[int, List[TrendPoint]] = defaultdict(list)
    for r in rows:
        buckets_by_topic[r["topic_id"]].append(TrendPoint(
            time_bucket=r["time_bucket"],
            article_cnt=int(r["article_cnt"]),
            hit_cnt=int(r["hit_cnt"]),
        ))
    result: List[TopicTrendSeries] = []
    for tid in tids:
        t = topics.get(tid, {})
        result.append(TopicTrendSeries(
            topic_id=tid, name=t.get("name"), color=t.get("color"),
            points=sorted(buckets_by_topic.get(tid, []), key=lambda p: p.time_bucket),
        ))
    return result


# ============================
#  Helper endpoints (charts data)
# ============================

@router.get("/analytics/top-keywords")
def top_keywords(
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=20, ge=1, le=100),
):
    """返回 [{keyword_id, word, topic_id, topic_name, topic_color, article_cnt, hit_cnt}]"""
    start = datetime.now() - timedelta(hours=hours)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT h.keyword_id, k.word, k.topic_id, t.name AS topic_name, t.color AS topic_color, "
                "COUNT(DISTINCT h.grab_id) AS article_cnt, "
                "SUM(h.hit_count) AS hit_cnt "
                "FROM grab_keyword_hit h "
                "JOIN grab g ON h.grab_id = g.id "
                "JOIN keyword k ON h.keyword_id = k.id "
                "JOIN topic t ON h.topic_id = t.id "
                "WHERE g.grabbed_at >= %s "
                "GROUP BY h.keyword_id, k.word, k.topic_id, topic_name, topic_color "
                "ORDER BY article_cnt DESC LIMIT %s",
                (start, limit),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


@router.get("/analytics/topic-dist")
def topic_distribution(hours: int = Query(default=24, ge=1, le=720)):
    """主题分布（饼图）。"""
    start = datetime.now() - timedelta(hours=hours)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT h.topic_id, t.name, t.color, COUNT(DISTINCT h.grab_id) AS article_cnt "
                "FROM grab_keyword_hit h "
                "JOIN grab g ON h.grab_id = g.id "
                "JOIN topic t ON h.topic_id = t.id "
                "WHERE g.grabbed_at >= %s "
                "GROUP BY h.topic_id, t.name, t.color ORDER BY article_cnt DESC",
                (start,),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


@router.get("/analytics/hourly-articles")
def hourly_articles(hours: int = Query(default=24, ge=1, le=168)):
    """近 N 小时每小时文章数柱图（全部文章，不区分主题）。"""
    start = (datetime.now() - timedelta(hours=hours)).replace(minute=0, second=0, microsecond=0)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DATE_FORMAT(grabbed_at, '%%Y-%%m-%%d %%H:00:00') AS bucket, "
                "COUNT(*) AS cnt FROM grab "
                "WHERE grabbed_at >= %s GROUP BY bucket ORDER BY bucket",
                (start,),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


# ============================
#  Hotspot Events
# ============================

@router.get("/analytics/events", response_model=HotspotEventListResponse)
def list_events(
    level: Optional[str] = Query(default=None, description="low|mid|high"),
    topic_id: Optional[int] = Query(default=None),
    keyword_id: Optional[int] = Query(default=None),
    start: Optional[str] = Query(default=None, description="ISO8601 窗口起点"),
    end: Optional[str] = Query(default=None, description="ISO8601 窗口终点"),
    only_unread: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)
    total = st.event_count(level=level, topic_id=topic_id,
                           start=start_dt, end=end_dt, only_unread=only_unread)
    rows = st.event_list(level=level, topic_id=topic_id, keyword_id=keyword_id,
                         start=start_dt, end=end_dt, only_unread=only_unread,
                         limit=limit, offset=offset)
    items = [HotspotEventOut(**r) for r in rows]
    return HotspotEventListResponse(total=total, limit=limit, offset=offset, items=items)


@router.post("/analytics/events/read")
def mark_events_read(body: EventMarkReadRequest):
    if body.all:
        rows = st.event_list(only_unread=True, limit=100000)
        ids = [r["id"] for r in rows]
    else:
        ids = body.ids or []
    st.event_mark_read(ids)
    return {"ok": True, "marked": len(ids)}


# ============================
#  History Recalc
# ============================

@router.post("/analytics/recalc", response_model=RecalcResponse)
def recalc_history(body: RecalcRequest, background_tasks: BackgroundTasks):
    """触发历史数据重算。

    数据量大时以异步方式后台执行；立刻返回 ok=True。
    """
    start = body.start_time
    end = body.end_time

    def _runner():
        try:
            result = analyze_history(start_time=start, end_time=end)
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    # 时间跨度 < 1 天同步返回，否则放到后台
    span = None
    if start and end:
        span = end - start
    if span and span.days < 1:
        result = _runner()
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return RecalcResponse(ok=True, **result)

    background_tasks.add_task(_runner)
    return RecalcResponse(ok=True)


# ============================
#  教程第 7 节扩展：相关性评估 PRF
# ============================

@router.get("/analytics/evaluate")
def evaluate_relevance_endpoint(
    hours: int = Query(default=24, ge=1, le=720),
):
    """相关性规则评分的 Precision / Recall / F1 评估报告。
    近似定义（无需人工标注的 proxy）：
    - TP  = score ≥ 阈值  AND  keyword_mentioned=True（命中且直接提到）
    - FP  = score ≥ 阈值  AND (keyword_mentioned=False OR NULL)（未直接提到但判高相关）
    - FN  = score < 阈值   AND  keyword_mentioned=True（直接提到但被判低相关，漏检）
    """
    from core.analyzer import evaluate_relevance
    try:
        return evaluate_relevance(hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluate failed: {e}")


# ============================
#  教程第 7 节扩展：Query Expansion 效果统计
# ============================

@router.get("/analytics/keywords/stats")
def keyword_match_stats(
    hours: int = Query(default=24, ge=1, le=720),
):
    """按关键词展示「直接提及 vs 变体命中」的拆分，供优化变体使用。"""
    try:
        stats = st.hit_stats_match_type(hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query stats failed: {e}")
    return {"hours": hours, "items": stats}


# ============================
#  教程扩展 4：聚合通知
# ============================

@router.get("/analytics/notify")
def notify_list_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[str] = Query(default=None, description="pending | sent | 留空=全部"),
):
    """聚合通知列表（每批按 30 分钟窗口 + topic + keyword + level 汇总）。"""
    try:
        items = st.notify_list(limit=limit, status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notify list failed: {e}")
    # 附带 pending 数量统计（前端展示角标）
    pending_info = st.notify_count(status="pending")
    sent_info = st.notify_count(status="sent")
    return {
        "items": items,
        "pending_count": int(pending_info["c"] or 0),
        "pending_articles": int(pending_info["total_art"] or 0),
        "sent_count": int(sent_info["c"] or 0),
        "sent_articles": int(sent_info["total_art"] or 0),
    }


@router.post("/analytics/notify/mark")
def notify_mark_sent_endpoint(ids: Optional[List[int]] = None):
    """标记通知为 sent。不传 ids 则把全部 pending 标记。"""
    try:
        st.notify_mark_sent(ids=ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mark failed: {e}")
    pending_info = st.notify_count(status="pending")
    return {
        "ok": True,
        "remaining_pending": int(pending_info["c"] or 0),
        "remaining_articles": int(pending_info["total_art"] or 0),
    }


@router.post("/analytics/notify/flush")
def notify_flush_endpoint():
    """把「窗口时间已结束」的 pending 通知批量刷为 sent。
    适合定时任务或后台定时调用。"""
    try:
        r = st.notify_flush()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flush failed: {e}")
    return {"ok": True, **r}
