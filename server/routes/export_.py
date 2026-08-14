"""数据导出路由（MySQL）

GET /api/export — 导出数据为 JSON / CSV / DOCX，全部通过浏览器下载
"""

import csv
import io
import json as json_mod
import os
import tempfile
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from storage.database import grab_list, grab_count

router = APIRouter()


def _rows_to_items(rows: List[dict]):
    """把 grab 表的 dict 行转换为 NewsArticle 对象，供 WordExporter 使用。"""
    from storage.models import NewsArticle

    items = []
    for r in rows:
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


@router.get("/export")
def api_export_data(
    format: str = Query(default="json", pattern="^(json|csv|docx)$"),
    source_name: Optional[str] = Query(default=None, description="按数据源过滤"),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """导出已爬取数据，通过浏览器直接下载到本地。

    三种格式均返回文件流，由浏览器触发下载。
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

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    source_suffix = f"_{source_name}" if source_name else ""
    filename_base = f"datagrab_export{source_suffix}_{ts}"

    # ── JSON 导出 ──
    if format == "json":
        content = json_mod.dumps(items, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=content.encode("utf-8"),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}.json"',
                "X-Export-Count": str(len(items)),
                "X-Export-Format": "json",
            },
        )

    # ── CSV 导出 ──
    if format == "csv":
        output = io.StringIO()
        if items:
            flat_items = []
            for item in items:
                flat = dict(item)
                if isinstance(flat.get("tags"), list):
                    flat["tags"] = ",".join(str(t) for t in flat["tags"])
                if isinstance(flat.get("raw_json"), dict):
                    del flat["raw_json"]
                flat_items.append(flat)

            writer = csv.DictWriter(output, fieldnames=flat_items[0].keys())
            writer.writeheader()
            writer.writerows(flat_items)

        csv_content = output.getvalue()
        return Response(
            content=csv_content.encode("utf-8-sig"),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}.csv"',
                "X-Export-Count": str(len(items)),
                "X-Export-Format": "csv",
            },
        )

    # ── DOCX 导出 ──
    if format == "docx":
        from storage.repository import Repository
        from exporters.word_exporter import export_to_word

        repo = Repository()
        repo.add_all(_rows_to_items(rows))

        title = "DataGrab 数据报告"
        if source_name:
            title = f"DataGrab 数据报告 - {source_name}"

        # 生成到临时文件，读取后删除
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            export_to_word(repo, tmp_path, report_title=title)
            with open(tmp_path, "rb") as f:
                docx_content = f.read()
        finally:
            os.unlink(tmp_path)

        return Response(
            content=docx_content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_base}.docx"',
                "X-Export-Count": str(len(items)),
                "X-Export-Format": "docx",
            },
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
