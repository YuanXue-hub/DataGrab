"""数据源管理路由

只需填 name + url，类型和选择器全自动检测/匹配。
GET    /api/sources           — 列出
POST   /api/sources           — 创建
GET    /api/sources/{name}    — 详情
PUT    /api/sources/{name}    — 更新
DELETE /api/sources/{name}    — 删除
POST   /api/sources/test      — 连通性测试
"""

import json
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from storage.database import (
    source_list, source_get, source_create, source_update, source_delete,
)
from server.models.responses import ConnectionTestResult

router = APIRouter()


class SourceCreate(BaseModel):
    """创建数据源——只需填 name + url"""
    name: str = Field(..., description="数据源名称")
    url: str = Field(..., description="目标网址")
    description: str = Field(default="")


class SourceUpdate(BaseModel):
    url: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class URLTest(BaseModel):
    url: str = Field(..., description="要测试的 URL")


def _detect_source_type(url: str) -> tuple:
    """自动检测：api 还是 web。

    策略：
    1. 请求 URL，看 Content-Type（JSON → api）
    2. 如果是 HTML，再试 URL + /api/trpc（可能是 tRPC 服务如 redroom）
    3. 都不行 → web
    """
    import httpx
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 先试直接请求
    try:
        r = httpx.get(url, timeout=5, follow_redirects=True, headers=headers)
        ct = r.headers.get("content-type", "")
        if "application/json" in ct:
            return ("api", {"endpoint": "articles.list"})
    except Exception:
        pass

    # 再试 /api/trpc（tRPC 服务常见路径）
    try:
        api_url = url.rstrip("/") + "/api/trpc/agencies.list?batch=1&input=%7B%220%22%3A%7B%22json%22%3A%7B%22limit%22%3A1%7D%7D%7D"
        r = httpx.get(api_url, timeout=5, headers=headers)
        if r.status_code == 200:
            return ("api", {"endpoint": "articles.list"})
    except Exception:
        pass

    return ("web", {})


# ============ 路由 ============

@router.get("/sources")
def api_list_sources():
    rows = source_list()
    result = []
    for r in rows:
        sel = r.get("selectors")
        if isinstance(sel, str):
            sel = json.loads(sel) if sel else None
        result.append({
            "name": r["name"], "url": r["url"],
            "description": r.get("description", ""),
            "source_type": r.get("source_type", "web"),
            "selectors": sel,
            "enabled": bool(r.get("enabled", 1)),
            "created_at": str(r.get("created_at", "")),
            "updated_at": str(r.get("updated_at", "")),
        })
    return result


@router.post("/sources")
def api_create_source(body: SourceCreate):
    """创建数据源——只需 name + url，类型和选择器全自动。

    示例:
        {"name": "新华网", "url": "https://www.news.cn"}
        {"name": "redroom-local", "url": "http://localhost:3000"}
    """
    from scrapers.selector_presets import get_selectors
    from scrapers.selector_detector import detect_selectors

    # 自动检测类型 + 默认参数
    source_type, auto_selectors = _detect_source_type(body.url)

    # 选择器：web 类型自动检测（真实分析页面 HTML），失败才用预设
    if source_type == "web":
        detected = detect_selectors(body.url)
        if detected:
            selectors = detected
        else:
            selectors = get_selectors(body.url)
    else:
        # api 类型：selectors = 查询参数
        selectors = auto_selectors

    # 检查重复
    if source_get(body.name):
        raise HTTPException(status_code=409, detail=f"Source '{body.name}' already exists")

    sid = source_create(
        name=body.name, url=body.url,
        description=body.description,
        source_type=source_type,
        selectors=selectors,
    )
    return {
        "success": True, "id": sid, "name": body.name,
        "source_type": source_type, "selectors": selectors,
    }


@router.get("/sources/{name}")
def api_get_source(name: str):
    row = source_get(name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    if isinstance(row.get("selectors"), str):
        row["selectors"] = json.loads(row["selectors"]) if row["selectors"] else None
    row["enabled"] = bool(row.get("enabled", 1))
    row["created_at"] = str(row.get("created_at", ""))
    row["updated_at"] = str(row.get("updated_at", ""))
    return row


@router.put("/sources/{name}")
def api_update_source(name: str, body: SourceUpdate):
    if not source_get(name):
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        source_update(name, **updates)
    return {"success": True, "name": name}


@router.delete("/sources/{name}")
def api_delete_source(name: str):
    if not source_get(name):
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    from storage.database import grab_delete_by_source
    grab_delete_by_source(name)
    source_delete(name)
    return {"success": True, "name": name}


@router.post("/sources/test", response_model=ConnectionTestResult)
def api_test_url(body: URLTest):
    import httpx
    url = body.url.rstrip("/")
    try:
        start = time.monotonic()
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        latency = (time.monotonic() - start) * 1000
        return ConnectionTestResult(
            success=r.status_code < 500,
            message=f"HTTP {r.status_code}: reachable",
            latency_ms=round(latency, 1),
        )
    except Exception as e:
        return ConnectionTestResult(success=False, message=str(e))
