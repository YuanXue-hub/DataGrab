"""TASS 俄通社爬虫

从 TASS（俄罗斯国家通讯社）RSS 源爬取俄乌冲突相关俄语新闻。
TASS 是俄罗斯最大的官方新闻机构，网站为 JS 渲染，但提供 RSS 接口。
"""

from typing import List
from datetime import datetime
from xml.etree import ElementTree as ET

from loguru import logger

from core.base_scraper import BaseScraper
from storage.models import DataItem, NewsArticle
from utils.text_cleaner import clean_text


class TassScraper(BaseScraper):
    """TASS 俄通社新闻爬虫（RSS 源）

    从 TASS RSS 2.0 源抓取俄语新闻，按关键词筛选乌克兰相关条目。
    """

    BASE_URL = "https://tass.ru"

    # RSS 源 URL
    RSS_URL = "https://tass.ru/rss/v2.xml"

    # 俄乌冲突相关俄语关键词
    UKRAINE_KEYWORDS = [
        "Украин", "СВО", "Донбасс", "Киев", "Зеленск",
        "спецопераци", "фронт", "ВСУ", "обстрел", "мобилизаци",
        "санкци", "НАТО", "Курск", "Белгород", "Херсон",
    ]

    def __init__(self, max_articles: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.max_articles = max_articles

    def get_source_name(self) -> str:
        return "tass"

    def scrape(self, **kwargs) -> List[DataItem]:
        """从 TASS RSS 爬取俄乌冲突新闻

        Returns:
            NewsArticle 列表
        """
        self.logger.info(f"Starting TASS RSS scrape (max={self.max_articles})")

        # Step 1: 抓取 RSS
        raw = self.fetch(self.RSS_URL)
        if raw.status_code == 0 or not raw.raw_html:
            self.logger.error("Failed to fetch TASS RSS")
            return []

        # Step 2: 解析 RSS XML
        items = self._parse_rss(raw.raw_html)
        self.logger.info(f"RSS contains {len(items)} items, filtering...")

        # Step 3: 筛选乌克兰相关条目
        results: List[DataItem] = []
        for item in items:
            if len(results) >= self.max_articles:
                break

            title = item.get("title", "")
            description = item.get("description", "")

            # 检查关键词
            combined = (title + " " + description).lower()
            if not any(kw.lower() in combined for kw in self.UKRAINE_KEYWORDS):
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
                language=self.source_language or "ru",
                published_at=published_at,
                tags=["russia", "tass"],
                category="war",
            )
            results.append(article)

        self.logger.info(f"TASS scrape done: {len(results)} articles")
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
            self.logger.error(f"Failed to parse TASS RSS XML: {e}")

        return items
