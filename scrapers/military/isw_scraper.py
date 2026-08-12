"""ISW (Institute for the Study of War) 爬虫

从 ISW 网站爬取每日战报和战场分析。
ISW 提供俄乌冲突最权威的每日战场评估。
"""

from typing import List
from urllib.parse import urljoin

from loguru import logger

from core.base_scraper import BaseScraper
from parsers.military_parser import MilitaryParser
from storage.models import DataItem, RawData


class ISWScraper(BaseScraper):
    """ISW 战争研究所爬虫"""

    BASE_URL = "https://www.understandingwar.org"

    # 俄罗斯进攻战役每日更新页面
    CAMPAIGN_URL = (
        "https://www.understandingwar.org/analysis/"
        "russia-ukraine/russian-offensive-campaign-update/"
    )

    # Publications 页面（备选）
    PUBLICATIONS_URL = (
        "https://www.understandingwar.org/publications"
        "?field_region_target_id%5B1%5D=1"
    )

    def __init__(self, max_articles: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.max_articles = max_articles
        self.parser = MilitaryParser(source_language=self.source_language)

    def get_source_name(self) -> str:
        return "isw"

    def scrape(self, **kwargs) -> List[DataItem]:
        """爬取 ISW 乌克兰战场更新

        Returns:
            MilitaryData 和 NewsArticle 列表
        """
        self.logger.info(f"Starting ISW scrape (max={self.max_articles})")

        results: List[DataItem] = []

        # 使用增强的浏览器请求头绕过 Cloudflare
        browser_headers = {
            "Referer": "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
        }

        # 抓取战役更新页面
        raw = self.fetch(self.CAMPAIGN_URL, headers=browser_headers)
        if raw.status_code == 0:
            self.logger.warning("ISW campaign page fetch failed, trying publications page")
            raw = self.fetch(self.PUBLICATIONS_URL, headers=browser_headers)

        if raw.status_code == 0:
            self.logger.error("All ISW fetch attempts failed")
            return []

        # 提取报告链接
        report_urls = self._extract_report_urls(raw)

        if not report_urls:
            self.logger.warning("No ISW report URLs found on page")
            return []

        self.logger.info(f"Found {len(report_urls)} ISW report URLs")

        # 抓取每份报告详情
        for url in report_urls[:self.max_articles]:
            self.logger.debug(f"Fetching ISW report: {url}")
            report_raw = self.fetch(url, headers=browser_headers)
            if report_raw.status_code == 0:
                self.logger.warning(f"Failed to fetch report: {url}")
                continue

            try:
                items = self.parser.parse(report_raw)
                results.extend(items)
                self.logger.debug(f"  Parsed {len(items)} items from {url}")
            except Exception as e:
                self.logger.warning(f"Failed to parse report {url}: {e}")
                continue

        self.logger.info(f"ISW scrape done: {len(results)} items")
        return results

    def _extract_report_urls(self, raw_data: RawData) -> List[str]:
        """从 ISW 页面提取报告链接

        匹配 ISW 报告 URL 模式：
        - /research/russia-ukraine/russian-offensive-campaign-assessment-{date}/
        - /backgrounder/...
        - /publications/...

        Args:
            raw_data: 页面原始数据

        Returns:
            去重后的报告 URL 列表
        """
        soup = self.parser.make_soup(raw_data)
        urls = []

        for link in soup.select("a[href]"):
            href = link.get("href", "").strip()
            text = link.get_text(strip=True)

            if not href or href == "/" or href == "#":
                continue

            # 跳过非报告链接（地图、导航等）
            skip_patterns = ["/map/", "/education/", "/fair-use", "/user/",
                           "facebook", "twitter", "youtube", "mailto:"]
            if any(p in href.lower() for p in skip_patterns):
                continue

            # 匹配 ISW 报告 URL 模式
            report_patterns = [
                "/research/russia-ukraine/",
                "/backgrounder/",
            ]

            is_report = any(pattern in href for pattern in report_patterns)
            if not is_report:
                continue

            # 需要有意义的链接文本
            if not text or len(text) < 10:
                continue

            # 构建完整 URL
            full_url = urljoin(self.BASE_URL, href)

            # 只保留 understandingwar.org 域名的链接
            if "understandingwar.org" not in full_url:
                continue

            if full_url not in urls:
                urls.append(full_url)

        self.logger.debug(f"Extracted {len(urls)} report URLs")
        return urls
