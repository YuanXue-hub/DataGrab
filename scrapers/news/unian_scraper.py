"""UNIAN 乌克兰独立新闻社爬虫

从 UNIAN（乌克兰独立新闻社）RSS 源爬取乌克兰语新闻。
UNIAN 是乌克兰主要新闻机构之一，提供稳定的 RSS 接口。
"""

from typing import List
from datetime import datetime
from xml.etree import ElementTree as ET

from loguru import logger

from core.base_scraper import BaseScraper
from storage.models import DataItem, NewsArticle
from utils.text_cleaner import clean_text


class UnianScraper(BaseScraper):
    """UNIAN 乌克兰独立新闻社爬虫（RSS 源）

    从 UNIAN RSS 源抓取乌克兰语新闻，按关键词筛选战争相关条目。
    """

    BASE_URL = "https://www.unian.ua"

    # RSS 源 URL
    RSS_URL = "https://rss.unian.ua/site/news_ukr.rss"

    # 俄乌冲突相关乌克兰语关键词
    WAR_KEYWORDS = [
        "війн", "фронт", "ЗСУ", "оборон", "наступ",
        "Росі", "Путін", "Кремл", "обстріл", "атак",
        "мобілізац", "волонтер", "евакуац", "допомог",
        "санкці", "НАТО", "Харків", "Херсон", "Запоріж",
        "Донбас", "Крим", "окупант", "звільнен",
        "контрнаступ", "безпек", "ракет",
    ]

    def __init__(self, max_articles: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.max_articles = max_articles

    def get_source_name(self) -> str:
        return "unian"

    def scrape(self, **kwargs) -> List[DataItem]:
        """从 UNIAN RSS 爬取乌克兰战争新闻

        Returns:
            NewsArticle 列表
        """
        self.logger.info(f"Starting UNIAN RSS scrape (max={self.max_articles})")

        # Step 1: 抓取 RSS
        raw = self.fetch(self.RSS_URL)
        if raw.status_code == 0 or not raw.raw_html:
            self.logger.error("Failed to fetch UNIAN RSS")
            return []

        # Step 2: 解析 RSS XML
        items = self._parse_rss(raw.raw_html)
        self.logger.info(f"RSS contains {len(items)} items, filtering...")

        # Step 3: 筛选战争相关条目
        results: List[DataItem] = []
        for item in items:
            if len(results) >= self.max_articles:
                break

            title = item.get("title", "")
            description = item.get("description", "")

            # 检查关键词
            combined = (title + " " + description).lower()
            if not any(kw.lower() in combined for kw in self.WAR_KEYWORDS):
                continue

            # 解析日期
            published_at = None
            pub_date = item.get("pubDate", "")
            if pub_date:
                try:
                    from dateutil.parser import parse as dateutil_parse
                    published_at = dateutil_parse(pub_date)
                except Exception:
                    pass

            article = NewsArticle(
                title=clean_text(title),
                content=clean_text(description),
                summary=clean_text(description)[:300],
                source_name=self.get_source_name(),
                source_url=item.get("link", ""),
                language=self.source_language or "uk",
                published_at=published_at,
                tags=["ukraine", "unian"],
                category="war",
            )
            results.append(article)

        self.logger.info(f"UNIAN scrape done: {len(results)} articles")
        return results

    def _parse_rss(self, xml_content: str) -> List[dict]:
        """解析 RSS 2.0 XML，提取条目列表

        Args:
            xml_content: RSS XML 字符串

        Returns:
            [{title, description, link, pubDate}, ...]
        """
        items = []
        try:
            root = ET.fromstring(xml_content)
            channel = root.find("channel")
            if channel is None:
                return items

            for item in channel.findall("item"):
                data = {}
                for field in ["title", "description", "link", "pubDate"]:
                    el = item.find(field)
                    if el is not None and el.text:
                        data[field] = el.text.strip()
                    else:
                        data[field] = ""
                if data.get("title") and data.get("link"):
                    items.append(data)

        except ET.ParseError as e:
            self.logger.error(f"Failed to parse UNIAN RSS XML: {e}")

        return items
