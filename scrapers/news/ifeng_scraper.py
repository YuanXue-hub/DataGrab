"""凤凰网军事爬虫

从凤凰网军事频道爬取俄乌冲突相关新闻。
凤凰网有丰富的中文军事新闻和分析。
"""

from typing import List
from urllib.parse import urljoin

from loguru import logger

from core.base_scraper import BaseScraper
from parsers.news_parser import NewsParser
from storage.models import DataItem, RawData


class IfengScraper(BaseScraper):
    """凤凰网军事新闻爬虫

    从凤凰网军事频道和搜索页面抓取俄乌冲突新闻。
    """

    BASE_URL = "https://www.ifeng.com"

    # 数据源页面
    SOURCE_URLS = [
        "https://mil.ifeng.com/",                                          # 军事频道首页
        "https://search.ifeng.com/sofeng/search.action?q=%E4%BF%84%E4%B9%8C&c=1",  # 搜索"俄乌"
    ]

    # 俄乌冲突关键词（用于筛选文章）
    UKRAINE_KEYWORDS = [
        "乌克兰", "ukraine",
        "俄乌", "乌俄",
        "泽连斯基", "普京",
        "基辅", "莫斯科",
        "顿涅茨克", "顿巴斯",
        "赫尔松", "哈尔科夫",
        "乌军", "俄军",
        "北约", "nato",
        "克里米亚", "黑海",
        "停火", "和谈", "谈判",
    ]

    def __init__(self, max_articles: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.max_articles = max_articles
        self.parser = NewsParser(source_language=self.source_language)

    def get_source_name(self) -> str:
        return "ifeng"

    def scrape(self, **kwargs) -> List[DataItem]:
        """爬取凤凰网俄乌冲突新闻

        1. 从多个来源页面聚合文章链接
        2. 逐个抓取文章详情页

        Returns:
            NewsArticle 列表
        """
        self.logger.info(f"Starting Ifeng scrape (max={self.max_articles})")

        # Step 1: 聚合文章链接
        article_urls = self._aggregate_urls()
        self.logger.info(f"Aggregated {len(article_urls)} article URLs")

        if not article_urls:
            self.logger.warning("No Ifeng article URLs found")
            return []

        # Step 2: 逐篇抓取
        results: List[DataItem] = []
        for url in article_urls:
            if len(results) >= self.max_articles:
                break

            self.logger.debug(f"Fetching: {url}")
            raw = self.fetch(url)
            if raw.status_code == 0:
                self.logger.warning(f"Failed to fetch: {url}")
                continue

            try:
                items = self.parser.parse(raw)
                for item in items:
                    item.source_url = url
                    item.source_name = self.get_source_name()
                results.extend(items)
            except Exception as e:
                self.logger.warning(f"Failed to parse {url}: {e}")
                continue

        self.logger.info(f"Ifeng scrape done: {len(results)} articles")
        return results

    def _aggregate_urls(self) -> List[str]:
        """从多个页面聚合文章链接

        Returns:
            去重后的文章 URL 列表
        """
        all_urls: set[str] = set()

        for page_url in self.SOURCE_URLS:
            raw = self.fetch(page_url)
            if raw.status_code == 0:
                self.logger.warning(f"Failed to fetch source page: {page_url}")
                continue

            urls = self._extract_urls(raw)
            all_urls.update(urls)
            self.logger.debug(f"  {page_url} -> {len(urls)} URLs")

        return list(all_urls)

    def _extract_urls(self, raw_data: RawData) -> List[str]:
        """从页面提取符合关键词的文章链接

        凤凰网文章 URL 格式：/c/{article_id}
        如：https://mil.ifeng.com/c/8tmTKsahZf9

        Args:
            raw_data: 页面 HTML 数据

        Returns:
            文章 URL 列表
        """
        soup = self.parser.make_soup(raw_data)
        urls = []

        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "").strip()
            text = a_tag.get_text(strip=True)

            if not href or not text:
                continue

            # 检查是否为文章链接
            if "/c/" not in href:
                continue

            # 构建完整 URL
            if href.startswith("http"):
                full_url = href
            else:
                full_url = urljoin("https://www.ifeng.com", href)

            # 必须是 ifeng.com 域名
            if "ifeng.com" not in full_url:
                continue

            # 排除视频链接和非新闻链接
            if "/v.ifeng.com/" in full_url or "video" in full_url.lower():
                continue

            # 关键词筛选
            combined = (text + " " + href).lower()
            if not any(kw in combined for kw in self.UKRAINE_KEYWORDS):
                continue

            if full_url not in urls:
                urls.append(full_url)

        return urls
