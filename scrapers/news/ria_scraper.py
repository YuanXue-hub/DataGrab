"""RIA Novosti 俄新社爬虫

从 RIA Novosti（俄罗斯新闻社）爬取俄乌冲突相关俄语新闻。
RIA 是俄罗斯最大的国内新闻机构之一。
"""

from typing import List
from urllib.parse import urljoin

from loguru import logger

from core.base_scraper import BaseScraper
from parsers.news_parser import NewsParser
from storage.models import DataItem, RawData


class RiaScraper(BaseScraper):
    """RIA Novosti 俄新社新闻爬虫

    从 RIA Novosti 搜索页面抓取乌克兰冲突相关俄语新闻。
    """

    BASE_URL = "https://ria.ru"

    # 搜索页面
    SEARCH_URL = "https://ria.ru/search/?query=СВО+Украина"

    # 专题页面
    TOPIC_URLS = [
        "https://ria.ru/world/",
        "https://ria.ru/defense_safety/",
    ]

    # 俄乌冲突相关俄语关键词（用于筛选链接）
    UKRAINE_KEYWORDS = [
        "Украин",
        "СВО",
        "Донбасс",
        "Киев",
        "Зеленск",
        "спецопераци",
        "фронт",
        "ВСУ",
        "обстрел",
        "мобилизаци",
        "санкци",
        "НАТО",
        "Курск",
        "Белгород",
        "Херсон",
        "Запорож",
    ]

    def __init__(self, max_articles: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.max_articles = max_articles
        self.parser = NewsParser(source_language=self.source_language)

    def get_source_name(self) -> str:
        return "ria"

    def scrape(self, **kwargs) -> List[DataItem]:
        """爬取 RIA Novosti 俄乌冲突新闻

        Returns:
            NewsArticle 列表
        """
        self.logger.info(f"Starting RIA scrape (max={self.max_articles})")

        # Step 1: 从多个页面聚合文章链接
        article_urls = self._aggregate_article_urls()
        self.logger.info(f"Aggregated {len(article_urls)} RIA article URLs")

        if not article_urls:
            self.logger.warning("No RIA article URLs found")
            return []

        # Step 2: 逐个抓取文章详情页
        results: List[DataItem] = []
        urls_seen: set[str] = set()

        for url in article_urls:
            if len(results) >= self.max_articles:
                break
            if url in urls_seen:
                continue
            urls_seen.add(url)

            self.logger.debug(f"Fetching article: {url}")
            raw = self.fetch(url)
            if raw.status_code == 0:
                self.logger.warning(f"Failed to fetch RIA article: {url}")
                continue

            try:
                items = self.parser.parse(raw)
                for item in items:
                    item.source_url = url
                results.extend(items)
                self.logger.debug(f"  Parsed {len(items)} items from {url}")
            except Exception as e:
                self.logger.warning(f"Failed to parse RIA article {url}: {e}")
                continue

        self.logger.info(f"RIA scrape done: {len(results)} articles")
        return results

    def _aggregate_article_urls(self) -> List[str]:
        """从多个页面聚合文章 URL"""
        all_urls: list[tuple[str, str]] = []

        # 从搜索页获取
        search_raw = self.fetch(self.SEARCH_URL)
        if search_raw.status_code != 0:
            urls = self._extract_article_urls(search_raw)
            all_urls.extend(urls)
            self.logger.debug(f"  search page -> {len(urls)} URLs")

        # 从专题页面获取
        for topic_url in self.TOPIC_URLS:
            raw = self.fetch(topic_url)
            if raw.status_code == 0:
                continue
            urls = self._extract_article_urls(raw)
            self.logger.debug(f"  {topic_url} -> {len(urls)} URLs")
            all_urls.extend(urls)

        # 去重并按日期降序排列
        seen: set[str] = set()
        unique_urls = []
        for url, date_str in sorted(all_urls, key=lambda x: x[1], reverse=True):
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _extract_article_urls(self, raw_data: RawData) -> list[tuple[str, str]]:
        """从页面提取文章 URL

        RIA URL 格式通常为 /20260615/XXXXXXX.html

        Args:
            raw_data: 页面原始数据

        Returns:
            [(url, date_string), ...] 列表
        """
        soup = self.parser.make_soup(raw_data)
        urls = []

        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "").strip()
            text = a_tag.get_text(strip=True)

            if not href or not text:
                continue

            # 构建完整 URL
            if href.startswith("http"):
                full_url = href
            else:
                full_url = urljoin(self.BASE_URL, href)

            # 必须是 ria.ru 域名
            if "ria.ru" not in full_url:
                continue

            # 排除非文章链接
            if self._is_non_article_url(full_url):
                continue

            # 检查是否包含俄乌关键词
            combined = (text + " " + href).lower()
            if not any(kw.lower() in combined for kw in self.UKRAINE_KEYWORDS):
                continue

            # 提取日期
            date_str = self._extract_date_from_url(full_url)
            if date_str:
                urls.append((full_url, date_str))
            else:
                urls.append((full_url, "00000000"))

        return urls

    @staticmethod
    def _is_non_article_url(url: str) -> bool:
        """判断 URL 是否为非文章页"""
        non_article_patterns = [
            "/search", "/tag/", "/tags/",
            "/video/", "/photo/", "/audio/", "/infographics/",
            "/radio/", "/tv/", "/podcast/",
            "ria.ru/#", "ria.ru/?",
            "/author/", "/rubric/", "/services/",
        ]
        return any(pattern in url for pattern in non_article_patterns)

    @staticmethod
    def _extract_date_from_url(url: str) -> str:
        """从 RIA URL 中提取日期

        RIA URL 格式示例：
        - https://ria.ru/20260615/ukraina-12345678.html
        - https://ria.ru/2026/06/15/12345678.html

        Returns:
            日期字符串 (YYYYMMDD) 或空字符串
        """
        import re
        # 格式：/20260615/
        match = re.search(r"/(20\d{6})/", url)
        if match:
            return match.group(1)
        # 格式：/2026/06/15/
        match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
        if match:
            return f"{match.group(1)}{match.group(2)}{match.group(3)}"
        return ""
