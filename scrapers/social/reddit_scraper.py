"""Reddit 爬虫

从 Reddit 爬取俄乌冲突相关帖子和讨论。
使用 Reddit JSON API（无需 PRAW 即可访问公开数据）。
"""

from typing import List
from datetime import datetime
import json

from loguru import logger

from core.base_scraper import BaseScraper
from parsers.social_parser import SocialParser
from storage.models import DataItem, RawData


class RedditScraper(BaseScraper):
    """Reddit 公共数据爬虫

    使用 Reddit 的公开 JSON API (.json 后缀) 获取数据。
    无需 API Key，但有限速（每分钟约 60 请求）。
    """

    BASE_URL = "https://www.reddit.com"

    # 俄乌冲突相关 subreddits
    DEFAULT_SUBREDDITS = [
        "ukraine",
        "ukrainewarvideoreport",
        "UkrainianConflict",
    ]

    # 排序方式
    SORT_OPTIONS = ["hot", "new", "top"]

    def __init__(
        self,
        subreddits: List[str] = None,
        max_posts_per_sub: int = 25,
        sort: str = "hot",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.subreddits = subreddits or self.DEFAULT_SUBREDDITS
        self.max_posts_per_sub = max_posts_per_sub
        self.sort = sort if sort in self.SORT_OPTIONS else "hot"
        self.parser = SocialParser(source_language=self.source_language)

    def get_source_name(self) -> str:
        return "reddit"

    def scrape(self, **kwargs) -> List[DataItem]:
        """爬取 Reddit 帖子

        Returns:
            SocialPost 列表
        """
        self.logger.info(
            f"Starting Reddit scrape "
            f"(subreddits={self.subreddits}, sort={self.sort})"
        )

        results: List[DataItem] = []

        for subreddit in self.subreddits:
            if len(results) >= self.max_posts_per_sub * len(self.subreddits):
                break

            try:
                items = self._scrape_subreddit(subreddit)
                results.extend(items)
                self.logger.info(f"r/{subreddit}: {len(items)} posts")
            except Exception as e:
                self.logger.error(f"Failed to scrape r/{subreddit}: {e}")

        self.logger.info(f"Reddit scrape done: {len(results)} posts")
        return results

    def _scrape_subreddit(self, subreddit: str) -> List[DataItem]:
        """爬取单个 subreddit"""
        url = f"{self.BASE_URL}/r/{subreddit}/{self.sort}.json"
        headers = {
            "User-Agent": "DataGrab/0.1 (Research Tool; contact@example.com)",
        }

        try:
            response = self.http.get(url, headers=headers)
            data = response.json()

            raw = RawData(
                source_name=f"reddit-r-{subreddit}",
                source_url=url,
                raw_json=data,
                status_code=response.status_code,
            )

            return self.parser.parse(raw)

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON from Reddit API: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Reddit API error for r/{subreddit}: {e}")
            return []

    def _extract_post_urls(self, raw_data: RawData) -> List[str]:
        """提取帖子链接（备用，从 HTML 中提取）"""
        soup = self.parser.make_soup(raw_data)
        urls = []
        for link in soup.select('a[data-click-id="body"]'):
            href = link.get("href", "")
            if "/comments/" in href:
                full_url = self.BASE_URL + href if href.startswith("/") else href
                urls.append(full_url)
        return urls
