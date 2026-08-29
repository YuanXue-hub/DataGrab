"""数据导出路由（MySQL）

GET /api/export — 导出数据为 JSON / CSV / DOCX，全部通过浏览器下载
"""

import csv
import io
import json as json_mod
import logging
import os
import tempfile
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote as url_quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from storage.database import grab_list, grab_count

router = APIRouter()
logger = logging.getLogger(__name__)


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
    keyword_id: Optional[int] = Query(default=None, description="按关键词过滤（仅导出命中该关键词的文章）"),
    search: Optional[str] = Query(default=None, description="按搜索词在标题/摘要/正文模糊匹配"),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """导出已爬取数据，通过浏览器直接下载到本地。

    支持按数据源、关键词、搜索词过滤，三种格式均返回文件流。
    """
    total = grab_count(source_name=source_name, keyword_id=keyword_id, search=search)
    if total == 0:
        parts = []
        if source_name:
            parts.append(f"数据源「{source_name}」")
        if keyword_id:
            parts.append(f"关键词ID={keyword_id}")
        if search:
            parts.append(f"搜索词「{search}」")
        scope = "、".join(parts) if parts else "全部数据"
        detail = f"No data to export for {scope}"
        logger.warning(f"[EXPORT] 跳过：{scope} 下没有抓取记录")
        raise HTTPException(status_code=404, detail=detail)

    rows = grab_list(source_name=source_name, keyword_id=keyword_id, search=search,
                     limit=limit, offset=0)
    logger.info(f"[EXPORT] format={format} source={source_name or 'ALL'} "
                f"keyword_id={keyword_id} search={search} limit={limit}, 命中 {len(rows)} 条")

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
    parts = []
    if source_name:
        parts.append(source_name)
    if keyword_id:
        # 查关键词文本用于文件名
        try:
            from storage.database import get_connection
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT word FROM keyword WHERE id = %s", (keyword_id,))
                row = cur.fetchone()
            conn.close()
            kw_word = row["word"] if row else f"kw{keyword_id}"
        except Exception:
            kw_word = f"kw{keyword_id}"
        parts.append(kw_word)
    if search:
        parts.append(f"search_{search}")
    suffix = ("_" + "_".join(parts)) if parts else ""
    filename_base = f"datagrab_export{suffix}_{ts}"
    # kw_word 可能在 keyword_id 分支未定义，确保 DOCX 标题安全访问
    kw_word_safe = kw_word if 'kw_word' in locals() else (f"kw{keyword_id}" if keyword_id else "")

    def _content_disposition(fmt_ext: str) -> str:
        """生成兼容中文文件名的 Content-Disposition（RFC 5987）。"""
        fn = f"{filename_base}.{fmt_ext}"
        fn_ascii = url_quote(fn, safe='')
        return f"attachment; filename=\"{fn_ascii}\"; filename*=UTF-8''{fn_ascii}"

    # ── JSON 导出 ──
    if format == "json":
        content = json_mod.dumps(items, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=content.encode("utf-8"),
            media_type="application/json",
            headers={
                "Content-Disposition": _content_disposition("json"),
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
                "Content-Disposition": _content_disposition("csv"),
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
        title_parts = []
        if source_name:
            title_parts.append(source_name)
        if keyword_id:
            title_parts.append(kw_word_safe)
        if search:
            title_parts.append(f"搜索:{search}")
        if title_parts:
            title = f"DataGrab 数据报告 - {' / '.join(title_parts)}"

        # 生成到临时目录，WordExporter 内部会追加时间戳到文件名
        tmp_dir = tempfile.mkdtemp()
        tmp_stub = os.path.join(tmp_dir, "export.docx")
        try:
            actual_path = export_to_word(repo, tmp_stub, report_title=title)
            with open(actual_path, "rb") as f:
                docx_content = f.read()
        finally:
            # 清理临时目录下的所有文件（含 word_exporter 追加的时间戳文件）
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return Response(
            content=docx_content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": _content_disposition("docx"),
                "X-Export-Count": str(len(items)),
                "X-Export-Format": "docx",
            },
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
