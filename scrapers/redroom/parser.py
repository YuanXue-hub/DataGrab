"""Redroom 数据解析器

将 redroomcn tRPC API 返回的 JSON 数据映射为 DataGrab 数据模型。
"""

from typing import List, Optional
from datetime import datetime

from storage.models import NewsArticle


class RedroomParser:
    """将 redroom API 响应解析为 DataGrab 模型。

    支持解析：
    - articles.* → List[NewsArticle]
    - agencies.* → List[dict]（透传，暂无专用模型）
    - facilities.* → List[dict]（透传，暂无专用模型）
    - timeline → List[dict]
    - networkGraph → dict
    """

    def parse_articles(self, raw_articles: list) -> List[NewsArticle]:
        """将 redroom Article JSON 列表解析为 NewsArticle 列表。

        字段映射：
            title        → title
            content      → content（null 时回退到 summary）
            summary      → summary
            agencyName   → source_name
            url          → source_url
            language     → language
            publishedAt  → published_at
            keywords     → tags
            topics[0]    → category
        """
        results = []
        for art in raw_articles:
            if not isinstance(art, dict):
                continue

            # 提取发布时间（可能是 datetime 或字符串）
            published_at = art.get("publishedAt")
            if isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    published_at = None

            # 构造 source_name
            source_name = art.get("agencyName") or f"redroom-{art.get('agencyId', 'unknown')}"

            # 提取 tags
            keywords = art.get("keywords") or []
            topics = art.get("topics") or []

            article = NewsArticle(
                title=art.get("title") or "",
                content=art.get("content") or art.get("summary") or "",
                summary=art.get("summary") or "",
                source_name=source_name,
                source_url=art.get("url") or "",
                language=art.get("language") or "en",
                published_at=published_at,
                tags=list(keywords) if keywords else [],
                category=topics[0] if topics else "",
            )
            results.append(article)

        return results

    def parse_agencies(self, raw_data: list) -> List[dict]:
        """透传 agencies 数据（暂无专用 Agency 模型）。"""
        return raw_data if isinstance(raw_data, list) else [raw_data]

    def parse_facilities(self, raw_data: list) -> List[dict]:
        """透传 facilities 数据（暂无专用 Facility 模型）。"""
        return raw_data if isinstance(raw_data, list) else [raw_data]

    def parse_timeline(self, raw_data: list) -> List[dict]:
        """透传 timeline 聚合数据。"""
        return raw_data if isinstance(raw_data, list) else [raw_data]

    def parse_network_graph(self, raw_data: dict) -> dict:
        """透传 network graph 数据。"""
        return raw_data if isinstance(raw_data, dict) else {}

    def parse_stats(self, raw_data) -> dict:
        """透传统计数据。"""
        return raw_data if isinstance(raw_data, dict) else {}
