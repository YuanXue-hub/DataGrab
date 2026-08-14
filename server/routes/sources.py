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
    """创建数据源——只需填 name + url

    selectors 可选：用户手动配置时传入，标记为 selector_source="manual"。
    不传则系统自动检测/匹配预设。
    """
    name: str = Field(..., description="数据源名称")
    url: str = Field(..., description="目标网址")
    description: str = Field(default="")
    selectors: Optional[dict] = Field(default=None, description="手动配置的选择器（可选）")


class SourceUpdate(BaseModel):
    url: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    selectors: Optional[dict] = None


class URLTest(BaseModel):
    url: str = Field(..., description="要测试的 URL")


class PreviewRequest(BaseModel):
    """选择器预览请求——输入 URL + 可选 selectors，返回抓取样本"""
    url: str = Field(..., description="目标网址")
    selectors: Optional[dict] = Field(default=None, description="手动配置的选择器（可选，不传则自动检测）")
    sample_size: int = Field(default=3, ge=1, le=5, description="抓取样本数（1-5）")


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
            "selector_source": r.get("selector_source", "manual"),
            "enabled": bool(r.get("enabled", 1)),
            "created_at": str(r.get("created_at", "")),
            "updated_at": str(r.get("updated_at", "")),
        })
    return result


@router.post("/sources")
def api_create_source(body: SourceCreate):
    """创建数据源——只需 name + url，类型和选择器全自动。

    用户也可手动传入 selectors，此时 selector_source 标记为 "manual"。

    示例:
        {"name": "新华网", "url": "https://www.news.cn"}
        {"name": "redroom-local", "url": "http://localhost:3000"}
        {"name": "custom", "url": "https://x.com", "selectors": {"article_selector": "li.news"}}
    """
    from scrapers.selector_presets import get_selectors, PRESETS
    from scrapers.selector_detector import detect_selectors
    from urllib.parse import urlparse

    # 用户手动传入 selectors → 直接使用，标记为 manual
    if body.selectors:
        source_type, _ = _detect_source_type(body.url)
        selectors = body.selectors
        selector_source = "manual"
    else:
        # 自动检测类型 + 默认参数
        source_type, auto_selectors = _detect_source_type(body.url)

        # 选择器：web 类型自动检测（真实分析页面 HTML），失败才用预设
        if source_type == "web":
            detected = detect_selectors(body.url)
            if detected:
                selectors = detected
                selector_source = "detector"
            else:
                selectors = get_selectors(body.url)
                hostname = urlparse(body.url).hostname or ""
                is_preset = any(
                    hostname == d or hostname.endswith("." + d) for d in PRESETS
                )
                selector_source = "preset" if is_preset else "fallback"
        else:
            # api 类型：selectors = 查询参数
            selectors = auto_selectors
            selector_source = "manual"

    # 检查重复
    if source_get(body.name):
        raise HTTPException(status_code=409, detail=f"Source '{body.name}' already exists")

    sid = source_create(
        name=body.name, url=body.url,
        description=body.description,
        source_type=source_type,
        selectors=selectors,
        selector_source=selector_source,
    )
    return {
        "success": True, "id": sid, "name": body.name,
        "source_type": source_type, "selectors": selectors,
        "selector_source": selector_source,
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
    # 手动修改 selectors 时，更新 selector_source 为 manual
    if "selectors" in updates:
        updates["selector_source"] = "manual"
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


@router.post("/sources/preview")
def api_preview_source(body: PreviewRequest):
    """选择器预览：输入 URL + 可选 selectors，返回前 N 条抓取样本。

    两种模式：
    - 仅 URL：自动调用 detect_selectors，返回检测结果 + 试抓样本
    - URL + selectors：跳过检测，直接用传入选择器试抓

    返回 samples 包含标题、链接、摘要、正文前 200 字、正文长度、发布时间。
    验证失败时返回 failure_reasons 列表，帮助用户定位选择器问题。
    """
    import time
    import httpx
    from urllib.parse import urlparse
    from scrapers.selector_presets import get_selectors, PRESETS
    from scrapers.selector_detector import detect_selectors_with_reason, validate_selectors
    from scrapers.content_extractor import extract_content, extract_date

    start = time.monotonic()
    url = body.url.rstrip("/")
    sample_size = body.sample_size

    # ── 1. 确定 selectors 和 selector_source ──
    detect_reason = ""  # detector 失败原因（仅 URL 模式）
    if body.selectors:
        selectors = dict(body.selectors)
        selector_source = "manual"
    else:
        try:
            detected, detect_reason = detect_selectors_with_reason(url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"detect_selectors failed: {e}")

        if detected:
            selectors = detected
            selector_source = "detector"
        else:
            selectors = get_selectors(url)
            hostname = urlparse(url).hostname or ""
            is_preset = any(
                hostname == d or hostname.endswith("." + d) for d in PRESETS
            )
            selector_source = "preset" if is_preset else "fallback"

    # ── 2. 抓取列表页 + 验证取样本 ──
    validation = validate_selectors(url, selectors, sample_size=sample_size)

    # ── 3. 抓取详情页，补充 content_preview 和 published_at ──
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    samples = []
    for s in validation["samples"]:
        sample = {
            "title": s.get("title", ""),
            "url": s.get("url", ""),
            "summary": (s.get("summary") or "")[:200],
            "content_preview": "",
            "content_length": 0,
            "published_at": None,
        }
        if s.get("url"):
            try:
                r = httpx.get(s["url"], headers=headers, timeout=10, follow_redirects=True)
                if r.status_code == 200:
                    html = r.text
                    content = extract_content(html)
                    if content:
                        sample["content_preview"] = content[:200]
                        sample["content_length"] = len(content)
                    date_str = extract_date(html)
                    if date_str:
                        sample["published_at"] = date_str
            except Exception:
                pass
        samples.append(sample)

    # ── 4. JS 渲染标记：detector 已标记则保留，否则根据样本正文长度判断 ──
    js_rendered = bool(selectors.get("js_rendered", False))
    if not js_rendered and samples:
        short_count = sum(1 for s in samples if s["content_length"] < 150)
        if short_count >= max(len(samples) // 2, 1):
            js_rendered = True

    # ── 5. 汇总失败原因 ──
    failure_reasons = []
    # detector 失败原因（仅 URL 模式且 detector 未命中时）
    if detect_reason and selector_source != "detector":
        failure_reasons.append(f"自动检测失败：{detect_reason}")
        if selector_source == "preset":
            failure_reasons.append(f"已回退到预设模板（{urlparse(url).hostname}）")
        elif selector_source == "fallback":
            failure_reasons.append("已回退到通用兜底选择器，效果可能不佳")
    # 验证失败原因
    if not validation["passed"]:
        failure_reasons.extend(validation.get("reasons", []))

    elapsed_ms = round((time.monotonic() - start) * 1000)

    return {
        "success": True,
        "url": url,
        "selector_source": selector_source,
        "selectors": selectors,
        "js_rendered": js_rendered,
        "samples": samples,
        "validation": {
            "total": validation["total_count"],
            "valid": validation["valid_count"],
            "passed": validation["passed"],
        },
        "failure_reasons": failure_reasons,
        "elapsed_ms": elapsed_ms,
    }
