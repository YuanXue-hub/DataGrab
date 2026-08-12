"""数据暂存仓库

提供数据的内存缓存和基本的 CRUD 操作。
"""

from typing import List, Optional, Type, TypeVar
from datetime import datetime

from loguru import logger

from storage.models import DataItem, NewsArticle, MilitaryData, EconomicData, SocialPost

T = TypeVar("T", bound=DataItem)


class Repository:
    """数据暂存仓库

    在内存中暂存爬取的数据，支持按类型、来源、日期查询。
    """

    def __init__(self):
        self._items: List[DataItem] = []

    def add(self, item: DataItem):
        """添加单条数据"""
        self._items.append(item)

    def add_all(self, items: List[DataItem]):
        """批量添加数据"""
        self._items.extend(items)

    def get_all(self, item_type: Type[T] = None) -> List[DataItem]:
        """获取所有数据，可按类型过滤

        Args:
            item_type: 数据类型（NewsArticle, MilitaryData, etc.）

        Returns:
            数据列表
        """
        if item_type is None:
            return self._items
        return [item for item in self._items if isinstance(item, item_type)]

    def get_by_source(self, source_name: str) -> List[DataItem]:
        """按数据源名称查询"""
        return [
            item for item in self._items
            if hasattr(item, "source_name") and item.source_name == source_name
        ]

    def get_by_date(self, after: datetime) -> List[DataItem]:
        """查询指定日期之后的数据"""
        return [
            item for item in self._items
            if hasattr(item, "scraped_at") and item.scraped_at and item.scraped_at >= after
        ]

    def get_news(self) -> List[NewsArticle]:
        """获取所有新闻文章"""
        return [item for item in self._items if isinstance(item, NewsArticle)]

    def get_military(self) -> List[MilitaryData]:
        """获取所有军事数据"""
        return [item for item in self._items if isinstance(item, MilitaryData)]

    def get_economic(self) -> List[EconomicData]:
        """获取所有经济数据"""
        return [item for item in self._items if isinstance(item, EconomicData)]

    def get_social(self) -> List[SocialPost]:
        """获取所有社交媒体数据"""
        return [item for item in self._items if isinstance(item, SocialPost)]

    def count(self) -> int:
        """返回数据总数"""
        return len(self._items)

    def summary(self) -> dict:
        """返回数据摘要统计"""
        return {
            "total": len(self._items),
            "news": len(self.get_news()),
            "military": len(self.get_military()),
            "economic": len(self.get_economic()),
            "social": len(self.get_social()),
            "by_source": self._count_by_source(),
        }

    def _count_by_source(self) -> dict:
        """按数据源统计"""
        counts = {}
        for item in self._items:
            source = getattr(item, "source_name", "unknown")
            counts[source] = counts.get(source, 0) + 1
        return counts

    def clear(self):
        """清空所有数据"""
        self._items.clear()
        logger.info("Repository cleared")

    def __len__(self):
        return len(self._items)

    def __repr__(self):
        return f"Repository(items={len(self._items)}, news={len(self.get_news())})"
