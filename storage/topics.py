"""监控相关表 CRUD 操作

包含：
- topic          主题分类
- keyword        关键词（归属主题）
- grab_keyword_hit   文章-关键词命中关联
- keyword_trend  词频趋势快照
- hotspot_event  热点事件/告警
- schedule_config 调度配置
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

import pymysql
from loguru import logger

from storage.database import get_connection


# ============================
#  Topic CRUD
# ============================

def topic_list(include_disabled: bool = False) -> List[dict]:
    """列出所有主题，按 sort_order 排序。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if include_disabled:
                cur.execute("SELECT * FROM topic ORDER BY sort_order, id")
            else:
                cur.execute("SELECT * FROM topic WHERE enabled = 1 ORDER BY sort_order, id")
            return cur.fetchall()
    finally:
        conn.close()


def topic_get(topic_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM topic WHERE id = %s", (topic_id,))
            return cur.fetchone()
    finally:
        conn.close()


def topic_create(name: str, description: str = "", color: str = "#409EFF",
                 sort_order: int = 0, enabled: int = 1) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO topic (name, description, color, sort_order, enabled) "
                "VALUES (%s, %s, %s, %s, %s)",
                (name, description, color, sort_order, enabled)
            )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def topic_update(topic_id: int, **kwargs):
    allowed = {"name", "description", "color", "sort_order", "enabled"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            set_clause = ", ".join(f"{k} = %s" for k in updates)
            values = list(updates.values()) + [topic_id]
            cur.execute(f"UPDATE topic SET {set_clause} WHERE id = %s", values)
        conn.commit()
    finally:
        conn.close()


def topic_delete(topic_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM topic WHERE id = %s", (topic_id,))
        conn.commit()
    finally:
        conn.close()


# ============================
#  Keyword CRUD
# ============================

def keyword_list(topic_id: Optional[int] = None, include_disabled: bool = False) -> List[dict]:
    """列出关键词；可按主题过滤，可选包含禁用。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params: list = []
            if topic_id is not None:
                conditions.append("k.topic_id = %s")
                params.append(topic_id)
            if not include_disabled:
                conditions.append("k.enabled = 1")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT k.*, t.name AS topic_name, t.color AS topic_color "
                f"FROM keyword k LEFT JOIN topic t ON k.topic_id = t.id "
                f"{where} ORDER BY k.topic_id, k.weight DESC, k.id",
                params
            )
            return cur.fetchall()
    finally:
        conn.close()


def keyword_list_enabled() -> List[dict]:
    """获取所有启用的关键词（含主题信息），供 Analyzer 使用。"""
    return keyword_list(include_disabled=False)


def keyword_get(keyword_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT k.*, t.name AS topic_name FROM keyword k "
                "LEFT JOIN topic t ON k.topic_id = t.id WHERE k.id = %s",
                (keyword_id,)
            )
            return cur.fetchone()
    finally:
        conn.close()


def keyword_create(topic_id: Optional[int] = None, word: str = "", language: str = "",
                   match_mode: str = "fuzzy", weight: int = 1,
                   enabled: int = 1,
                   variants: Optional[List[str]] = None) -> int:
    conn = get_connection()
    variants_json = None
    if variants:
        try:
            variants_json = json.dumps([v for v in variants if v], ensure_ascii=False)
        except Exception:
            variants_json = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO keyword (topic_id, word, language, match_mode, weight, enabled, variants) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (topic_id, word, language, match_mode, weight, enabled, variants_json)
            )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def keyword_update(keyword_id: int, **kwargs):
    allowed = {"topic_id", "word", "language", "match_mode", "weight", "enabled"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if "variants" in kwargs:
        variants = kwargs["variants"]
        if variants is None:
            updates["variants"] = None
        elif isinstance(variants, (list, tuple)):
            try:
                updates["variants"] = json.dumps([v for v in variants if v], ensure_ascii=False)
            except Exception:
                updates["variants"] = None
        elif isinstance(variants, str):
            updates["variants"] = variants
    if not updates:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            set_clause = ", ".join(f"{k} = %s" for k in updates)
            values = list(updates.values()) + [keyword_id]
            cur.execute(f"UPDATE keyword SET {set_clause} WHERE id = %s", values)
        conn.commit()
    finally:
        conn.close()


def keyword_delete(keyword_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM keyword WHERE id = %s", (keyword_id,))
        conn.commit()
    finally:
        conn.close()


def keyword_bulk_import(topic_id: Optional[int], items: List[Tuple[str, str, str, int]]) -> int:
    """批量导入关键词，返回实际插入数量。
    items: [(word, language, match_mode, weight), ...]
    """
    conn = get_connection()
    inserted = 0
    try:
        with conn.cursor() as cur:
            for word, lang, mode, weight in items:
                if not word.strip():
                    continue
                cur.execute(
                    "INSERT IGNORE INTO keyword (topic_id, word, language, match_mode, weight, enabled) "
                    "VALUES (%s, %s, %s, %s, %s, 1)",
                    (topic_id, word.strip(), lang, mode, weight)
                )
                if cur.rowcount > 0:
                    inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


# ============================
#  Grab-Keyword Hit CRUD
# ============================

def hit_insert_batch(rows: List[Tuple[int, int, int, int, int]]):
    """批量写入命中记录，UNIQUE 冲突则更新计数与分数（旧版本，保留兼容）。
    rows: [(grab_id, keyword_id, topic_id, hit_count, score), ...]
    """
    if not rows:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = (
                "INSERT INTO grab_keyword_hit (grab_id, keyword_id, topic_id, hit_count, score, created_at) "
                "VALUES (%s, %s, %s, %s, %s, NOW()) "
                "ON DUPLICATE KEY UPDATE "
                "hit_count = hit_count + VALUES(hit_count), "
                "score = score + VALUES(score)"
            )
            cur.executemany(sql, rows)
        conn.commit()
    finally:
        conn.close()


def hit_insert_batch_v2(rows: List[Tuple[int, int, int, int, int, str, str, int]]):
    """批量写入命中记录（教程升级版：含 match_type / matched_variant / direct_mention）。
    rows: [(grab_id, keyword_id, topic_id, hit_count, score,
            match_type, matched_variant, direct_mention), ...]
    """
    if not rows:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = (
                "INSERT INTO grab_keyword_hit "
                "(grab_id, keyword_id, topic_id, hit_count, score, "
                " match_type, matched_variant, direct_mention, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW()) "
                "ON DUPLICATE KEY UPDATE "
                "hit_count = hit_count + VALUES(hit_count), "
                "score = score + VALUES(score), "
                "match_type = CASE "
                "  WHEN VALUES(match_type)='word' THEN 'word' "
                "  ELSE match_type END, "
                "matched_variant = CASE "
                "  WHEN VALUES(match_type)='word' THEN VALUES(matched_variant) "
                "  ELSE COALESCE(matched_variant, VALUES(matched_variant)) END, "
                "direct_mention = GREATEST(COALESCE(direct_mention,0), VALUES(direct_mention))"
            )
            cur.executemany(sql, rows)
        conn.commit()
    finally:
        conn.close()


def hit_get_by_grab_ids(grab_ids: List[int]) -> List[dict]:
    """查询一批 grab 记录的命中关键词（含关键词详情 + 新字段）。"""
    if not grab_ids:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(grab_ids))
            cur.execute(
                f"SELECT h.grab_id, h.keyword_id, h.topic_id, h.hit_count, h.score, "
                f"h.match_type, h.matched_variant, h.direct_mention, "
                f"k.word, k.weight, k.match_mode, k.variants, "
                f"t.name AS topic_name, t.color AS topic_color "
                f"FROM grab_keyword_hit h "
                f"JOIN keyword k ON h.keyword_id = k.id "
                f"JOIN topic t ON h.topic_id = t.id "
                f"WHERE h.grab_id IN ({placeholders}) "
                f"ORDER BY h.grab_id, h.score DESC",
                grab_ids
            )
            return cur.fetchall()
    finally:
        conn.close()


def hit_stats_match_type(hours: int = 24) -> List[dict]:
    """按 match_type 与 keyword 统计（教程第 7 节 Query Expansion 效果观测）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT k.id AS keyword_id, k.word, k.language,
                       JSON_LENGTH(k.variants) AS variant_cnt,
                       SUM(CASE WHEN h.match_type='word' THEN h.hit_count ELSE 0 END)   AS direct_hits,
                       SUM(CASE WHEN h.match_type='variant' THEN h.hit_count ELSE 0 END) AS variant_hits,
                       COUNT(DISTINCT CASE WHEN h.match_type='word' THEN h.grab_id END)    AS direct_grabs,
                       COUNT(DISTINCT CASE WHEN h.match_type='variant' THEN h.grab_id END) AS variant_grabs,
                       SUM(h.hit_count)                                                AS total_hits
                FROM grab_keyword_hit h
                JOIN grab g ON h.grab_id = g.id
                JOIN keyword k ON h.keyword_id = k.id
                WHERE g.grabbed_at >= NOW() - INTERVAL %s HOUR
                  AND k.variants IS NOT NULL AND JSON_LENGTH(k.variants) > 0
                GROUP BY k.id, k.word, k.language
                HAVING total_hits > 0
                ORDER BY total_hits DESC
                LIMIT 50
                """,
                (hours,)
            )
            return cur.fetchall()
    finally:
        conn.close()


def hit_delete_by_grab_ids(grab_ids: List[int]):
    """清除一批 grab 的命中记录（用于重算前清理）。"""
    if not grab_ids:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(grab_ids))
            cur.execute(f"DELETE FROM grab_keyword_hit WHERE grab_id IN ({placeholders})", grab_ids)
        conn.commit()
    finally:
        conn.close()


# ============================
#  Keyword Trend CRUD
# ============================

def trend_upsert_batch(rows: List[Tuple[int, int, datetime, str, int, int]]):
    """批量 UPSERT 趋势快照。
    rows: [(keyword_id, topic_id, time_bucket, grain, article_cnt, hit_cnt), ...]
    """
    if not rows:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = (
                "INSERT INTO keyword_trend (keyword_id, topic_id, time_bucket, grain, article_cnt, hit_cnt, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, NOW()) "
                "ON DUPLICATE KEY UPDATE "
                "article_cnt = article_cnt + VALUES(article_cnt), "
                "hit_cnt = hit_cnt + VALUES(hit_cnt)"
            )
            cur.executemany(sql, rows)
        conn.commit()
    finally:
        conn.close()


def trend_query(keyword_ids: List[int], grain: str,
                start: datetime, end: datetime) -> List[dict]:
    """查询若干关键词的时间序列。"""
    if not keyword_ids:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(keyword_ids))
            cur.execute(
                f"SELECT keyword_id, time_bucket, grain, article_cnt, hit_cnt "
                f"FROM keyword_trend "
                f"WHERE keyword_id IN ({placeholders}) AND grain = %s "
                f"AND time_bucket >= %s AND time_bucket < %s "
                f"ORDER BY keyword_id, time_bucket",
                keyword_ids + [grain, start, end]
            )
            return cur.fetchall()
    finally:
        conn.close()


def trend_query_by_topics(topic_ids: List[int], grain: str,
                          start: datetime, end: datetime) -> List[dict]:
    """按主题聚合的趋势：同 time_bucket 下文章数、命中次数求和。"""
    if not topic_ids:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(topic_ids))
            cur.execute(
                f"SELECT topic_id, time_bucket, grain, "
                f"SUM(article_cnt) AS article_cnt, SUM(hit_cnt) AS hit_cnt "
                f"FROM keyword_trend "
                f"WHERE topic_id IN ({placeholders}) AND grain = %s "
                f"AND time_bucket >= %s AND time_bucket < %s "
                f"GROUP BY topic_id, grain, time_bucket "
                f"ORDER BY topic_id, time_bucket",
                topic_ids + [grain, start, end]
            )
            return cur.fetchall()
    finally:
        conn.close()


def trend_get_baseline(keyword_id: int, grain: str,
                       window_start: datetime,
                       days_back: int = 7) -> Tuple[float, float]:
    """计算关键词基线：过去 days_back 同时段均值和标准差。
    grain=hour 时：取过去 N 天同一 hour 的统计
    返回 (mean, std)；数据不足时 std=0
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if grain == "hour":
                target_hour = window_start.hour
                min_bucket = (window_start - timedelta(days=days_back)).replace(
                    minute=0, second=0, microsecond=0
                )
                cur.execute(
                    "SELECT article_cnt FROM keyword_trend "
                    "WHERE keyword_id = %s AND grain = 'hour' "
                    "AND HOUR(time_bucket) = %s "
                    "AND time_bucket >= %s AND time_bucket < %s",
                    (keyword_id, target_hour, min_bucket, window_start)
                )
            else:
                min_bucket = (window_start - timedelta(days=days_back)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                cur.execute(
                    "SELECT article_cnt FROM keyword_trend "
                    "WHERE keyword_id = %s AND grain = 'day' "
                    "AND time_bucket >= %s AND time_bucket < %s",
                    (keyword_id, min_bucket, window_start)
                )
            rows = [r["article_cnt"] for r in cur.fetchall()]
        if not rows:
            return 0.0, 0.0
        n = len(rows)
        mean = sum(rows) / n
        if n < 2:
            return mean, 0.0
        var = sum((x - mean) ** 2 for x in rows) / (n - 1)
        std = var ** 0.5
        return mean, std
    finally:
        conn.close()


def trend_clear_range(keyword_ids: List[int], grain: str,
                      start: datetime, end: datetime):
    """删除指定关键词在某时间范围内的趋势快照（重算前清理）。"""
    if not keyword_ids:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(keyword_ids))
            cur.execute(
                f"DELETE FROM keyword_trend "
                f"WHERE keyword_id IN ({placeholders}) AND grain = %s "
                f"AND time_bucket >= %s AND time_bucket < %s",
                keyword_ids + [grain, start, end]
            )
        conn.commit()
    finally:
        conn.close()


# ============================
#  Hotspot Event CRUD
# ============================

def event_create(keyword_id: Optional[int], topic_id: Optional[int],
                 window_start: datetime, window_end: datetime,
                 article_cnt: int, hit_cnt: int,
                 baseline: float, ratio: float, level: str) -> int:
    """创建一条热点事件记录，同一 (keyword_id, window_start) 已存在则跳过。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM hotspot_event "
                "WHERE keyword_id <=> %s AND window_start = %s",
                (keyword_id, window_start)
            )
            existing = cur.fetchone()
            if existing:
                return existing["id"]
            cur.execute(
                "INSERT INTO hotspot_event (keyword_id, topic_id, window_start, window_end, "
                "article_cnt, hit_cnt, baseline, ratio, level, is_read) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)",
                (keyword_id, topic_id, window_start, window_end,
                 article_cnt, hit_cnt, round(baseline, 2), round(ratio, 2), level)
            )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def event_list(level: Optional[str] = None, topic_id: Optional[int] = None,
               keyword_id: Optional[int] = None,
               start: Optional[datetime] = None, end: Optional[datetime] = None,
               limit: int = 50, offset: int = 0,
               only_unread: bool = False) -> List[dict]:
    """热点事件列表（按窗口时间倒序）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params: list = []
            if level:
                conditions.append("e.level = %s")
                params.append(level)
            if topic_id is not None:
                conditions.append("e.topic_id = %s")
                params.append(topic_id)
            if keyword_id is not None:
                conditions.append("e.keyword_id = %s")
                params.append(keyword_id)
            if start:
                conditions.append("e.window_start >= %s")
                params.append(start)
            if end:
                conditions.append("e.window_start < %s")
                params.append(end)
            if only_unread:
                conditions.append("e.is_read = 0")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT e.*, t.name AS topic_name, t.color AS topic_color, "
                f"k.word AS keyword_word "
                f"FROM hotspot_event e "
                f"LEFT JOIN keyword k ON e.keyword_id = k.id "
                f"LEFT JOIN topic t ON e.topic_id = t.id "
                f"{where} ORDER BY e.window_start DESC LIMIT %s OFFSET %s",
                params + [limit, offset]
            )
            return cur.fetchall()
    finally:
        conn.close()


def event_count(level: Optional[str] = None, topic_id: Optional[int] = None,
                start: Optional[datetime] = None, end: Optional[datetime] = None,
                only_unread: bool = False) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params: list = []
            if level:
                conditions.append("level = %s")
                params.append(level)
            if topic_id is not None:
                conditions.append("topic_id = %s")
                params.append(topic_id)
            if start:
                conditions.append("window_start >= %s")
                params.append(start)
            if end:
                conditions.append("window_start < %s")
                params.append(end)
            if only_unread:
                conditions.append("is_read = 0")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(f"SELECT COUNT(*) AS cnt FROM hotspot_event {where}", params)
            return cur.fetchone()["cnt"]
    finally:
        conn.close()


def event_mark_read(event_ids: List[int]):
    if not event_ids:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(event_ids))
            cur.execute(f"UPDATE hotspot_event SET is_read = 1 WHERE id IN ({placeholders})", event_ids)
        conn.commit()
    finally:
        conn.close()


# ============================
#  Schedule Config CRUD
# ============================

def schedule_list() -> List[dict]:
    """列出所有调度配置，含数据源名称。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.*, src.name AS source_name, src.url AS source_url, src.enabled AS source_enabled "
                "FROM schedule_config s LEFT JOIN source src ON s.source_id = src.id "
                "ORDER BY s.id"
            )
            return cur.fetchall()
    finally:
        conn.close()


def schedule_get(source_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM schedule_config WHERE source_id = %s", (source_id,))
            return cur.fetchone()
    finally:
        conn.close()


def schedule_upsert(source_id: int, cron_expr: str,
                    limit_count: int = 10, enabled: int = 1):
    """新增或更新某数据源的调度配置。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO schedule_config (source_id, cron_expr, limit_count, enabled) "
                "VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "cron_expr = VALUES(cron_expr), "
                "limit_count = VALUES(limit_count), "
                "enabled = VALUES(enabled)",
                (source_id, cron_expr, limit_count, enabled)
            )
        conn.commit()
    finally:
        conn.close()


def schedule_delete(source_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM schedule_config WHERE source_id = %s", (source_id,))
        conn.commit()
    finally:
        conn.close()


# ============================
#  Notification Pending CRUD（教程扩展 4：通知聚合）
# ============================

def notify_list(limit: int = 100, status: Optional[str] = None,
                channel: str = "inapp") -> List[dict]:
    """按时间倒序查询待处理/已发送的聚合通知。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            where = ["n.channel = %s"]
            params: list = [channel]
            if status:
                where.append("n.status = %s")
                params.append(status)
            where_sql = "WHERE " + " AND ".join(where)
            cur.execute(
                f"SELECT n.*, t.name AS topic_name, t.color AS topic_color, k.word AS keyword_word "
                f"FROM notification_pending n "
                f"LEFT JOIN topic t ON n.topic_id = t.id "
                f"LEFT JOIN keyword k ON n.keyword_id = k.id "
                f"{where_sql} ORDER BY n.bucket_start DESC, n.event_level DESC LIMIT %s",
                params + [limit]
            )
            return cur.fetchall()
    finally:
        conn.close()


def notify_count(status: Optional[str] = "pending", channel: str = "inapp") -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            where = ["channel = %s"]
            params: list = [channel]
            if status:
                where.append("status = %s")
                params.append(status)
            where_sql = "WHERE " + " AND ".join(where)
            cur.execute(
                f"SELECT COUNT(*) AS c, COALESCE(SUM(article_cnt),0) AS total_art "
                f"FROM notification_pending {where_sql}",
                params
            )
            return cur.fetchone()
    finally:
        conn.close()


def notify_mark_sent(ids: Optional[List[int]] = None):
    """标记通知为 sent（全部 pending 或指定 id 列表）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                cur.execute(
                    f"UPDATE notification_pending SET status='sent', sent_at=NOW() "
                    f"WHERE id IN ({placeholders})",
                    ids
                )
            else:
                cur.execute(
                    "UPDATE notification_pending SET status='sent', sent_at=NOW() "
                    "WHERE status='pending'"
                )
        conn.commit()
    finally:
        conn.close()


def notify_flush(channel: str = "inapp") -> dict:
    """把当前 bucket_end <= NOW() 的 pending 汇总为 sent，返回批次摘要。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c, COALESCE(SUM(article_cnt),0) AS total_art "
                "FROM notification_pending "
                "WHERE channel = %s AND status = 'pending' AND bucket_end <= NOW()",
                (channel,)
            )
            row = cur.fetchone()
            cur.execute(
                "UPDATE notification_pending SET status='sent', sent_at=NOW() "
                "WHERE channel = %s AND status = 'pending' AND bucket_end <= NOW()",
                (channel,)
            )
        conn.commit()
        return {"flushed_batches": int(row["c"] or 0),
                "flushed_articles": int(row["total_art"] or 0)}
    finally:
        conn.close()
