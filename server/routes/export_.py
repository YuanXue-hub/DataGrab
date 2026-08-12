"""数据导出路由（MySQL）

GET /api/export — 导出数据为 JSON / CSV / DOCX
"""

import json as json_mod
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from storage.database import grab_list, grab_count
from server.models.responses import ExportResponse

router = APIRouter()


def _rows_to_items(rows: List[dict]):
    """把 grab 表的 dict 行转换为 NewsArticle 对象，供 WordExporter 使用。"""
    from storage.models import NewsArticle

    items = []
    for r in rows:
        # 解析 JSON 字段
        tags = r.get("tags")
        if isinstance(tags, str):
            try:
                tags = json_mod.loads(tags)
            except (json_mod.JSONDecodeError, TypeError):
                tags = None

        published = r.get("published_at")
        if isinstance(published, str):
            try:
                published = datetime.fromisoformat(published)
            except ValueError:
                published = None

        items.append(NewsArticle(
            title=r.get("title", "") or "",
            content=r.get("content", "") or "",
            summary=r.get("summary", "") or "",
            source_name=r.get("source_name", "") or "",
            source_url=r.get("source_url", "") or "",
            language=r.get("language", "") or "",
            category=r.get("category", "") or "",
            tags=tags or [],
            published_at=published,
        ))
    return items


@router.get("/export", response_model=ExportResponse)
def api_export_data(
    format: str = Query(default="json", pattern="^(json|csv|docx)$"),
    source_name: Optional[str] = Query(default=None, description="按数据源过滤"),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """导出已爬取数据。

    - format=json: 返回内联 JSON，前端可直接下载
    - format=csv:  保存到 output/ 目录，返回文件路径
    - format=docx: 生成格式化 Word 报告，保存到 output/ 目录
    """
    total = grab_count(source_name=source_name)
    if total == 0:
        raise HTTPException(status_code=404, detail="No data to export")

    rows = grab_list(source_name=source_name, limit=limit, offset=0)

    # 解析 JSON / datetime 字段为可序列化结构
    items = []
    for r in rows:
        item = dict(r)
        for field in ("tags", "raw_json"):
            if isinstance(item.get(field), str):
                try:
                    item[field] = json_mod.loads(item[field])
                except (json_mod.JSONDecodeError, TypeError):
                    pass
        for field in ("published_at", "grabbed_at"):
            if item.get(field):
                item[field] = str(item[field])
        items.append(item)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── JSON 导出 ──
    if format == "json":
        content = json_mod.dumps(items, ensure_ascii=False, indent=2, default=str)
        return ExportResponse(success=True, format="json", content=content)

    # ── CSV 导出 ──
    if format == "csv":
        filename = f"export_{ts}.csv"
        filepath = output_dir / filename

        if items:
            flat_items = []
            for item in items:
                flat = dict(item)
                if isinstance(flat.get("tags"), list):
                    flat["tags"] = ",".join(str(t) for t in flat["tags"])
                if isinstance(flat.get("raw_json"), dict):
                    del flat["raw_json"]
                flat_items.append(flat)

            import csv
            with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=flat_items[0].keys())
                writer.writeheader()
                writer.writerows(flat_items)

        return ExportResponse(
            success=True, format="csv",
            file_path=str(filepath),
            message=f"Exported {len(items)} rows to {filepath}",
        )

    # ── DOCX 导出 ──
    if format == "docx":
        from storage.repository import Repository
        from exporters.word_exporter import export_to_word

        repo = Repository()
        repo.add_all(_rows_to_items(rows))

        # 报告标题带上数据源标识
        title = "DataGrab 数据报告"
        if source_name:
            title = f"DataGrab 数据报告 - {source_name}"

        filepath = output_dir / f"export_{ts}.docx"
        final_path = export_to_word(repo, str(filepath), report_title=title)

        return ExportResponse(
            success=True, format="docx",
            file_path=final_path,
            message=f"Exported {len(items)} rows to {final_path}",
        )

    # 不会到达这里（pattern 已限制）
    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
