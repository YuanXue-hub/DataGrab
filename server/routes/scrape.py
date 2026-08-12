"""爬取任务路由（MySQL 持久化）

POST /api/scrape          — 触发爬取任务（web/api 双模式）
GET  /api/scrape          — 查询任务历史列表
GET  /api/scrape/{job_id} — 查询单个任务状态

任务状态持久化到 scrape_job 表，grab 表通过 job_id 关联，
支持"哪次任务抓了哪些数据"的回溯。

limit: 限制爬取的文章条数（web 模式=CSS提取条数，api 模式=tRPC查询条数）
"""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from storage.database import source_get, grab_insert, grab_list, job_list, job_count
from server.dependencies import (
    create_job, get_job, update_job, set_job_results, evict_job,
)
from server.models.responses import ScrapeJobResponse, ScrapeJobListResponse

router = APIRouter()


class ScrapeRequest(BaseModel):
    """触发爬取任务

    limit: 限制爬取条数。web 模式限制 CSS 提取的文章数；
           api 模式限制 tRPC 查询返回的记录数。
    """
    source_name: str = Field(..., description="数据源名称（source 表中的 name）")
    limit: int = Field(default=20, ge=1, le=500, description="最大抓取条数（0=不限制）")


def _scrape_web(source_id: int, source_name: str, url: str,
                selectors: dict, limit: int, job_id: str) -> list:
    """HTML 页面爬取（web 类型数据源）。"""
    from scrapers.generic_scraper import GenericScraper

    scraper = GenericScraper(source_name=source_name)
    try:
        results = scraper.scrape(url=url, limit=limit)
    finally:
        scraper.close()

    # 不再用标题兜底 content/summary：
    # 详情页提取失败时 content 留空，前端展示"暂无正文"
    # 这样能真实反映爬取质量，便于发现问题数据源
    return results


def _scrape_api(source_id: int, source_name: str, url: str,
                selectors: dict, limit: int, job_id: str) -> list:
    """API 类型爬取：支持 tRPC（有 endpoint）和普通 REST API。"""
    import httpx
    from storage.models import NewsArticle

    endpoint = (selectors or {}).get("endpoint", "")

    # ── tRPC 模式（redroom 等）──
    if endpoint:
        from scrapers.redroom.trpc_client import TRPCClient, TRPCError
        from scrapers.redroom.parser import RedroomParser

        # 除 endpoint 外的字段作为查询参数
        params = {k: v for k, v in (selectors or {}).items() if k != "endpoint"}
        if "limit" not in params:
            params["limit"] = limit

        client = TRPCClient(base_url=url)
        parser = RedroomParser()
        try:
            logger.info(f"tRPC query: {endpoint} with {params}")
            raw = client.query(endpoint, params)
            if endpoint.startswith("articles"):
                return parser.parse_articles(raw if isinstance(raw, list) else [raw])
            elif endpoint.startswith("agencies"):
                return parser.parse_agencies(raw if isinstance(raw, list) else [raw])
            elif endpoint.startswith("facilities"):
                return parser.parse_facilities(raw if isinstance(raw, list) else [raw])
            return parser.parse_articles(raw if isinstance(raw, list) else [raw])
        except TRPCError as e:
            logger.error(f"tRPC error: {e}")
            return []
        finally:
            client.close()

    # ── 通用 REST API 模式 ──
    logger.info(f"REST API: GET {url}")
    try:
        resp = httpx.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0", "Accept": "application/json"
        })
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"REST API error: {e}")
        return []

    # 尝试解析 JSON 为文章列表
    items = data if isinstance(data, list) else data.get("data", data.get("results", data.get("items", [])))
    if isinstance(items, dict):
        items = list(items.values())
    if not isinstance(items, list):
        items = [data]

    results = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        results.append(NewsArticle(
            title=str(item.get("title", item.get("name", ""))),
            summary=str(item.get("summary", item.get("description", "")))[:300],
            content=str(item.get("content", item.get("body", ""))),
            source_name=source_name,
            source_url=str(item.get("url", item.get("link", url))),
            language=str(item.get("language", item.get("lang", ""))),
            tags=list(item.get("tags", item.get("keywords", []))) if isinstance(item.get("tags", item.get("keywords")), list) else [],
            category=str(item.get("category", item.get("type", ""))),
        ))
    logger.info(f"REST API: {len(results)} items")
    return results


def _serialize_item(item) -> dict:
    """将 DataItem 序列化为 JSON 安全字典。"""
    if hasattr(item, "__dataclass_fields__"):
        d = asdict(item)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        return d
    return {"_raw": str(item)}


def _run_scrape_job(job_id: str, source_name: str, limit: int):
    """后台任务：从指定数据源爬取并存入 MySQL。"""
    update_job(job_id, status="running", started_at=datetime.now())

    try:
        cfg = source_get(source_name)
        if not cfg:
            update_job(job_id, status="failed",
                       error=f"Source '{source_name}' not found",
                       completed_at=datetime.now())
            return

        source_id = cfg["id"]
        source_url = cfg["url"]
        source_type = cfg.get("source_type", "web")
        selectors_raw = cfg.get("selectors")

        if isinstance(selectors_raw, str):
            selectors = json.loads(selectors_raw) if selectors_raw else {}
        else:
            selectors = selectors_raw or {}

        logger.info(f"Scraping [{source_name}] type={source_type} url={source_url} limit={limit} job={job_id}")

        # 按数据源类型分派爬虫
        if source_type == "api":
            results = _scrape_api(source_id, source_name, source_url, selectors, limit, job_id)
        else:
            results = _scrape_web(source_id, source_name, source_url, selectors, limit, job_id)

        # 存入 MySQL grab 表，关联 job_id
        saved = 0
        for item in results:
            try:
                if hasattr(item, "title"):
                    grab_insert(
                        source_id=source_id,
                        job_id=job_id,
                        source_name=source_name,
                        title=getattr(item, "title", "") or "",
                        content=getattr(item, "content", "") or "",
                        summary=getattr(item, "summary", "") or "",
                        source_url=getattr(item, "source_url", "") or source_url,
                        language=getattr(item, "language", "") or "",
                        category=getattr(item, "category", "") or "",
                        tags=getattr(item, "tags", None) if hasattr(item, "tags") else None,
                        published_at=getattr(item, "published_at", None) if hasattr(item, "published_at") else None,
                    )
                    saved += 1
            except Exception as e:
                logger.warning(f"Failed to save: {e}")

        # 缓存结果预览（仅内存，供 GET /scrape/{job_id} 一次性返回）
        serialized = [_serialize_item(item) for item in results]
        set_job_results(job_id, serialized)

        update_job(job_id, status="completed", total=saved,
                   completed_at=datetime.now())
        logger.info(f"Job {job_id}: {len(results)} items, saved {saved}")
        # 完成后保留缓存一段时间供前端拉取结果，
        # 不主动 evict（前端拉过一次后由其自己停止轮询）

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        update_job(job_id, status="failed", error=str(e), completed_at=datetime.now())


def _job_to_response(job) -> ScrapeJobResponse:
    """把 ScrapeJob 运行时对象转为 API 响应。"""
    resp = ScrapeJobResponse(
        job_id=job.job_id,
        status=job.status,
        source_name=job.source_name,
        sources=[job.source_name] if job.source_name else [],
        total=job.total,
        limit_count=job.limit_count,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
    # 仅 completed 状态返回结果预览
    if job.status == "completed" and job.results:
        resp.results = job.results
    return resp


@router.post("/scrape", response_model=ScrapeJobResponse)
def api_trigger_scrape(body: ScrapeRequest, background_tasks: BackgroundTasks):
    """触发爬取任务。

    - web 类型：用 CSS 选择器从 HTML 页面提取文章
    - api 类型：用 tRPC 协议调用 redroomcn API

    limit 控制每种模式下的最大抓取条数。
    任务状态持久化到 scrape_job 表，可历史回溯。
    """
    cfg = source_get(body.source_name)
    if not cfg:
        raise HTTPException(status_code=404,
                            detail=f"Source '{body.source_name}' not found")

    job = create_job(
        source_id=cfg["id"],
        source_name=body.source_name,
        limit_count=body.limit,
        params={"limit": body.limit},
    )
    background_tasks.add_task(_run_scrape_job, job.job_id, body.source_name, body.limit)

    return _job_to_response(job)


@router.get("/scrape", response_model=ScrapeJobListResponse)
def api_list_scrape_jobs(
    source_name: Optional[str] = Query(default=None, description="按数据源过滤"),
    status: Optional[str] = Query(default=None, description="按状态过滤"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """查询任务历史列表（从 scrape_job 表读取）。"""
    total = job_count(source_name=source_name, status=status)
    rows = job_list(source_name=source_name, status=status,
                    limit=limit, offset=offset)

    items = []
    for r in rows:
        items.append(ScrapeJobResponse(
            job_id=r["job_id"],
            status=r["status"],
            source_name=r["source_name"],
            sources=[r["source_name"]] if r.get("source_name") else [],
            total=r.get("total", 0),
            limit_count=r.get("limit_count", 20),
            error=r.get("error"),
            created_at=r["created_at"],
            started_at=r.get("started_at"),
            completed_at=r.get("completed_at"),
        ))

    return ScrapeJobListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/scrape/{job_id}", response_model=ScrapeJobResponse)
def api_get_scrape_job(job_id: str):
    """查询爬取任务状态（含结果预览，仅 completed 状态返回）。"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    resp = _job_to_response(job)
    # 拉过一次结果后，从内存缓存移除（避免长期占用内存）
    if job.status == "completed" and job.results:
        evict_job(job_id)
    return resp


@router.get("/scrape/{job_id}/data")
def api_get_job_data(job_id: str, limit: int = Query(default=100, ge=1, le=500)):
    """查询某次任务实际抓取到的数据列表（从 grab 表按 job_id 过滤）。"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    rows = grab_list(job_id=job_id, limit=limit, offset=0)
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
        items.append(item)

    return {"job_id": job_id, "total": len(items), "items": items}
