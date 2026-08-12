"""社交媒体解析器

解析来自 Reddit, Twitter 等社交平台的数据。
支持多语言内容检测。
"""

from typing import List, Optional
from datetime import datetime

from core.base_parser import BaseParser
from storage.models import RawData, DataItem, SocialPost
from utils.language_detector import detect_language


class SocialParser(BaseParser):
    """社交媒体内容解析器"""

    def __init__(self, source_language: str = None):
        """
        Args:
            source_language: 数据源配置的语言代码，作为语言检测提示
        """
        self.source_language = source_language

    def parse(self, raw_data: RawData) -> List[DataItem]:
        """解析社交媒体原始数据

        Args:
            raw_data: 原始数据（通常包含 JSON）

        Returns:
            SocialPost 列表
        """
        if raw_data.raw_json:
            return self._parse_json(raw_data)
        elif raw_data.raw_html:
            return self._parse_html(raw_data)
        return []

    def _parse_json(self, raw_data: RawData) -> List[DataItem]:
        """解析 JSON 格式的社交媒体数据（Reddit API 等）"""
        results = []
        data = raw_data.raw_json

        # 处理 Reddit 格式
        if "data" in data and "children" in data.get("data", {}):
            for child in data["data"]["children"]:
                post_data = child.get("data", {})
                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                post_language = detect_language(
                    title + " " + selftext,
                    hint=self.source_language,
                )
                post = SocialPost(
                    platform="reddit",
                    author=post_data.get("author", "unknown"),
                    content=selftext or title,
                    language=post_language,
                    engagement={
                        "score": post_data.get("score", 0),
                        "num_comments": post_data.get("num_comments", 0),
                        "upvote_ratio": post_data.get("upvote_ratio", 0),
                    },
                    posted_at=datetime.fromtimestamp(
                        post_data.get("created_utc", 0)
                    ) if post_data.get("created_utc") else None,
                    url=f"https://reddit.com{post_data.get('permalink', '')}",
                )
                results.append(post)

        return results

    def _parse_html(self, raw_data: RawData) -> List[DataItem]:
        """解析 HTML 格式的社交媒体数据"""
        soup = self.make_soup(raw_data)
        # 通用 HTML 社交媒体解析逻辑
        # 具体平台可在子类中重写
        return []
