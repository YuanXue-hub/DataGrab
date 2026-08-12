"""新华网爬虫

从新华网各频道爬取中文俄乌冲突新闻。
由于搜索 API (so.news.cn/getNews) 已禁用，
改为直接从各列表页抓取并筛选相关文章。
"""

from typing import List
from urllib.parse import urljoin

from loguru import logger

from core.base_scraper import BaseScraper
from parsers.news_parser import NewsParser
from storage.models import DataItem, RawData


class XinhuaScraper(BaseScraper):
    """新华网新闻爬虫

    从新华网世界、军事、政治等频道抓取俄乌冲突相关新闻。
    由于网站使用 JavaScript 渲染，静态 HTML 中可提取的
    链接数量有限，因此会从多个列表页面聚合链接。
    """

    BASE_URL = "https://www.news.cn"

    # 俄乌冲突相关关键词（用于筛选文章链接）
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
    ]

    # 列表页 URL（按优先级排列）
    LIST_PAGE_URLS = [
        f"{BASE_URL}/world/",      # 国际新闻
        f"{BASE_URL}/mil/",        # 军事新闻
        f"{BASE_URL}/politics/",   # 政治新闻
        f"{BASE_URL}/",            # 首页
    ]

    def __init__(self, max_articles: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.max_articles = max_articles
        self.parser = NewsParser(source_language=self.source_language)

    def get_source_name(self) -> str:
        return "xinhua"

    def scrape(self, **kwargs) -> List[DataItem]:
        """爬取新华网俄乌冲突新闻

        1. 从多个列表页聚合文章链接
        2. 逐个抓取文章详情页
        3. 使用 NewsParser 解析文章内容

        Returns:
            NewsArticle 列表
        """
        self.logger.info(f"Starting Xinhua scrape (max={self.max_articles})")

        # Step 1: 从多个列表页聚合文章链接
        article_urls = self._aggregate_article_urls()
        self.logger.info(f"Aggregated {len(article_urls)} article URLs")

        if not article_urls:
            self.logger.warning("No Xinhua article URLs found")
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
                self.logger.warning(f"Failed to fetch article: {url}")
                continue

            # Step 3: 解析文章
            try:
                items = self.parser.parse(raw)
                for item in items:
                    item.source_url = url  # 确保使用正确的 URL
                results.extend(items)
                self.logger.debug(f"  Parsed {len(items)} items from {url}")
            except Exception as e:
                self.logger.warning(f"Failed to parse article {url}: {e}")
                continue

        self.logger.info(f"Xinhua scrape done: {len(results)} articles")
        return results

    def _aggregate_article_urls(self) -> List[str]:
        """从多个列表页聚合文章链接

        遍历 LIST_PAGE_URLS 中的页面，提取包含俄乌关键词的文章链接。
        按链接中的日期降序排列，优先返回最新文章。

        Returns:
            去重后的文章 URL 列表
        """
        all_urls: list[tuple[str, str]] = []  # (url, date_string)
        headers = {
            "Referer": self.BASE_URL,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        for page_url in self.LIST_PAGE_URLS:
            raw = self.fetch(page_url, headers=headers)
            if raw.status_code == 0:
                self.logger.warning(f"Failed to fetch list page: {page_url}")
                continue

            urls = self._extract_article_urls(raw)
            self.logger.debug(f"  {page_url} -> {len(urls)} URLs")
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
        """从单个列表页提取文章 URL

        筛选条件：
        1. 链接文本或 URL 中包含俄乌关键词
        2. URL 中包含日期格式（/2024/, /2025/, /2026/ 等）
        3. 排除非文章页（如导航、广告链接）

        Args:
            raw_data: 列表页的原始 HTML 数据

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

            # 必须是 news.cn 域名
            if "news.cn" not in full_url and "xinhuanet.com" not in full_url:
                continue

            # 排除非文章链接
            if self._is_non_article_url(full_url):
                continue

            # 检查是否包含俄乌关键词
            combined = (text + " " + href).lower()
            if not any(kw in combined for kw in self.UKRAINE_KEYWORDS):
                continue

            # 提取日期（用于排序）
            date_str = self._extract_date_from_url(full_url)
            if date_str:
                urls.append((full_url, date_str))

        return urls

    @staticmethod
    def _is_non_article_url(url: str) -> bool:
        """判断 URL 是否为非文章页（导航、列表、搜索等）"""
        non_article_patterns = [
            "/search", "/tag/", "/channel/", "/list/",
            "/video/", "/photo/", "/live/", "/audio/",
            "/enterprise/", "/local/", "/company/",
            "news.cn/#", "news.cn/?",
        ]
        return any(pattern in url for pattern in non_article_patterns)

    @staticmethod
    def _extract_date_from_url(url: str) -> str:
        """从 URL 中提取日期字符串

        新华网 URL 格式示例：
        - /world/20260608/{hash}/c.html
        - /20260608/{hash}/c.html
        - /2020-12/28/c_1210950901.htm (旧格式)

        Returns:
            日期字符串 (YYYYMMDD) 或空字符串
        """
        import re
        # 新格式：/20260608/
        match = re.search(r"/(20\d{6})/", url)
        if match:
            return match.group(1)
        # 旧格式：/2020-12/28/
        match = re.search(r"/(20\d{2})[-/](\d{2})[-/](\d{2})/", url)
        if match:
            return f"{match.group(1)}{match.group(2)}{match.group(3)}"
        return ""
