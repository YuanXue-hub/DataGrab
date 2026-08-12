"""数据查询路由（MySQL）

GET /api/data — 查询已爬取数据
"""

import json
from typing import Optional

from fastapi import APIRouter, Query

from storage.database import grab_list, grab_count
from server.models.responses import DataResponse

router = APIRouter()


@router.get("/data", response_model=DataResponse)
def api_query_data(
    source_name: Optional[str] = Query(default=None, description="按数据源名称过滤"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """查询已爬取数据（从 MySQL grab 表读取）。"""
    total = grab_count(source_name=source_name)
    rows = grab_list(source_name=source_name, limit=limit, offset=offset)

    # 解析 JSON 字段
    items = []
    for r in rows:
        item = dict(r)
        for field in ("tags", "raw_json"):
            if isinstance(item.get(field), str):
                try:
                    item[field] = json.loads(item[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        # 格式化日期
        for field in ("published_at", "grabbed_at"):
            if item.get(field):
                item[field] = str(item[field])
        items.append(item)

    return DataResponse(total=total, limit=limit, offset=offset, items=items)
