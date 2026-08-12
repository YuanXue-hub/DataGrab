"""BBC News 爬虫

从 BBC 新闻网站爬取俄乌冲突相关新闻。
"""

from typing import List
from urllib.parse import urljoin

from loguru import logger

from core.base_scraper import BaseScraper
from parsers.news_parser import NewsParser
from storage.models import DataItem, RawData


class BBCScraper(BaseScraper):
    """BBC 新闻爬虫"""

    BASE_URL = "https://www.bbc.com"
    SEARCH_URL = "https://www.bbc.com/search?q=ukraine+war&d=news"

    def __init__(self, max_articles: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.max_articles = max_articles
        self.parser = NewsParser(source_language=self.source_language)

    def get_source_name(self) -> str:
        return "bbc"

    def scrape(self, **kwargs) -> List[DataItem]:
        """爬取 BBC 俄乌冲突新闻

        Returns:
            NewsArticle 列表
        """
        self.logger.info(f"Starting BBC scrape (max={self.max_articles})")

        # Step 1: 抓取搜索结果页
        search_raw = self.fetch(self.SEARCH_URL)
        if search_raw.status_code == 0:
            self.logger.warning("BBC search page fetch failed")
            return []

        # Step 2: 从搜索结果页提取文章链接
        article_urls = self._extract_article_urls(search_raw)

        # Step 3: 逐个抓取文章详情页
        results: List[DataItem] = []
        for url in article_urls[:self.max_articles]:
            self.logger.debug(f"Fetching article: {url}")
            raw = self.fetch(url)
            if raw.status_code == 0:
                continue

            # Step 4: 解析文章
            items = self.parser.parse(raw)
            results.extend(items)

            if len(results) >= self.max_articles:
                break

        self.logger.info(f"BBC scrape done: {len(results)} articles")
        return results

    def _extract_article_urls(self, raw_data: RawData) -> List[str]:
        """从搜索结果页提取文章 URL"""
        soup = self.parser.make_soup(raw_data)
        urls = []

        # BBC 搜索结果中的文章链接
        for link in soup.select('a[href^="/news/"]'):
            href = link.get("href", "")
            if "/news/articles/" in href or "/news/world" in href:
                full_url = urljoin(self.BASE_URL, href)
                if full_url not in urls:
                    urls.append(full_url)

        self.logger.debug(f"Found {len(urls)} article URLs")
        return urls
