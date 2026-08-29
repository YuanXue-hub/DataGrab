"""数据查询路由（MySQL）

GET /api/data — 查询已爬取数据
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Query

from storage.database import grab_list, grab_count, get_connection
import storage.topics as st
from server.models.responses import DataResponse

router = APIRouter()


def _filter_grab_ids_by_topic_or_keyword(topic_id: Optional[int],
                                         keyword_id: Optional[int]) -> Optional[List[int]]:
    """返回命中主题/关键词的 grab_id 列表；未过滤时返回 None。"""
    if topic_id is None and keyword_id is None:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            if keyword_id is not None:
                conditions.append("keyword_id = %s")
                params.append(keyword_id)
            if topic_id is not None:
                conditions.append("topic_id = %s")
                params.append(topic_id)
            where = "WHERE " + " AND ".join(conditions)
            cur.execute(
                f"SELECT DISTINCT grab_id FROM grab_keyword_hit {where}",
                params
            )
            return [r["grab_id"] for r in cur.fetchall()]
    finally:
        conn.close()


@router.get("/data", response_model=DataResponse)
def api_query_data(
    source_name: Optional[str] = Query(default=None, description="按数据源名称过滤"),
    topic_id: Optional[int] = Query(default=None, description="按主题过滤（只返回命中该主题关键词的文章）"),
    keyword_id: Optional[int] = Query(default=None, description="按关键词过滤"),
    keyword: Optional[str] = Query(default=None, description="关键词搜索（标题/摘要 LIKE）"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """查询已爬取数据（从 MySQL grab 表读取），支持主题/关键词筛选。"""

    # 1. 主题/关键词（结构化命中）过滤：取得 grab_id 范围
    restricted_ids = _filter_grab_ids_by_topic_or_keyword(topic_id, keyword_id)
    if restricted_ids is not None and not restricted_ids:
        # 有过滤条件但 0 匹配，直接返回空
        return DataResponse(total=0, limit=limit, offset=offset, items=[])

    # 2. 如果有限制的 grab_id 或 keyword 模糊搜索，走自定义 SQL
    need_custom_sql = restricted_ids is not None or keyword is not None
    if need_custom_sql:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                where_parts = []
                params = []
                if source_name:
                    where_parts.append("source_name = %s")
                    params.append(source_name)
                if restricted_ids:
                    ph = ",".join(["%s"] * len(restricted_ids))
                    where_parts.append(f"id IN ({ph})")
                    params.extend(restricted_ids)
                elif restricted_ids == []:
                    pass  # already handled above
                if keyword:
                    like = f"%{keyword}%"
                    where_parts.append("(title LIKE %s OR summary LIKE %s OR content LIKE %s)")
                    params.extend([like, like, like])
                where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

                cur.execute(f"SELECT COUNT(*) AS cnt FROM grab {where_sql}", params)
                total = cur.fetchone()["cnt"]

                cur.execute(
                    f"SELECT * FROM grab {where_sql} ORDER BY grabbed_at DESC "
                    f"LIMIT %s OFFSET %s",
                    params + [limit, offset]
                )
                rows = list(cur.fetchall())
        finally:
            conn.close()
    else:
        total = grab_count(source_name=source_name)
        rows = grab_list(source_name=source_name, limit=limit, offset=offset)

    # 3. 查询命中关键词附加字段
    grab_ids = [r["id"] for r in rows] if rows else []
    hit_map = {}
    if grab_ids:
        all_hits = st.hit_get_by_grab_ids(grab_ids)
        for h in all_hits:
            hit_map.setdefault(h["grab_id"], []).append({
                "keyword_id": h["keyword_id"],
                "keyword": h["word"],
                "topic_id": h["topic_id"],
                "topic_name": h["topic_name"],
                "topic_color": h["topic_color"],
                "hit_count": h["hit_count"],
                "score": h["score"],
                "weight": h["weight"],
                "match_type": h.get("match_type") or "word",
                "matched_variant": h.get("matched_variant"),
                "direct_mention": bool(h.get("direct_mention")),
            })

    # 4. 后处理：JSON 解析、日期转字符串、附加命中词
    items = []
    for r in rows:
        item = dict(r)
        for field in ("tags", "raw_json"):
            if isinstance(item.get(field), str):
                try:
                    item[field] = json.loads(item[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        for field in ("published_at", "grabbed_at"):
            if item.get(field):
                item[field] = str(item[field])
        item["matched_keywords"] = hit_map.get(item["id"], [])
        # 命中的主题集合（用于前端筛选）
        topics_seen = {}
        for m in item["matched_keywords"]:
            topics_seen[m["topic_id"]] = {
                "topic_id": m["topic_id"], "name": m["topic_name"], "color": m["topic_color"]
            }
        item["matched_topics"] = list(topics_seen.values())
        items.append(item)

    return DataResponse(total=total, limit=limit, offset=offset, items=items)
