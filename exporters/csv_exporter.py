"""CSV 导出器

将数据导出为 CSV 格式，方便用 Excel/Pandas 进一步分析。
"""

import csv
from pathlib import Path
from typing import List
from datetime import datetime

from loguru import logger

from storage.models import DataItem, NewsArticle, MilitaryData, SocialPost
from storage.repository import Repository


class CSVExporter:
    """CSV 格式导出器"""

    def export(
        self, repository: Repository, output_dir: str = "./output"
    ) -> List[str]:
        """导出所有数据为 CSV 文件

        按数据类型分别导出到不同 CSV 文件。

        Args:
            repository: 数据仓库
            output_dir: 输出目录

        Returns:
            生成的文件路径列表
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files = []

        # 导出新闻
        news = repository.get_news()
        if news:
            path = out_dir / f"news_{timestamp}.csv"
            self._export_news(news, path)
            files.append(str(path))

        # 导出军事数据
        military = repository.get_military()
        if military:
            path = out_dir / f"military_{timestamp}.csv"
            self._export_military(military, path)
            files.append(str(path))

        # 导出社交媒体
        social = repository.get_social()
        if social:
            path = out_dir / f"social_{timestamp}.csv"
            self._export_social(social, path)
            files.append(str(path))

        logger.info(f"CSV exports: {len(files)} files")
        return files

    def _export_news(self, items: List[NewsArticle], path: Path):
        """导出新闻到 CSV"""
        fieldnames = [
            "title", "summary", "content", "source_name", "source_url",
            "language", "published_at", "scraped_at", "tags", "category",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow({
                    "title": item.title,
                    "summary": item.summary[:500],
                    "content": item.content[:2000],
                    "source_name": item.source_name,
                    "source_url": item.source_url,
                    "language": item.language,
                    "published_at": item.published_at.isoformat() if item.published_at else "",
                    "scraped_at": item.scraped_at.isoformat() if item.scraped_at else "",
                    "tags": "|".join(item.tags),
                    "category": item.category,
                })
        logger.info(f"  Exported {len(items)} news to {path.name}")

    def _export_military(self, items: List[MilitaryData], path: Path):
        """导出军事数据到 CSV"""
        fieldnames = [
            "data_type", "metric_name", "value", "unit", "side",
            "language", "location", "source_name", "source_url",
            "reported_at", "scraped_at", "confidence", "notes",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow({
                    "data_type": item.data_type,
                    "metric_name": item.metric_name,
                    "value": item.value,
                    "unit": item.unit,
                    "side": item.side,
                    "language": item.language,
                    "location": item.location or "",
                    "source_name": item.source_name,
                    "source_url": item.source_url,
                    "reported_at": item.reported_at.isoformat() if item.reported_at else "",
                    "scraped_at": item.scraped_at.isoformat() if item.scraped_at else "",
                    "confidence": item.confidence,
                    "notes": item.notes,
                })
        logger.info(f"  Exported {len(items)} military records to {path.name}")

    def _export_social(self, items: List[SocialPost], path: Path):
        """导出社交媒体数据到 CSV"""
        fieldnames = [
            "platform", "author", "content", "language",
            "likes", "shares", "comments",
            "posted_at", "scraped_at", "url", "hashtags",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow({
                    "platform": item.platform,
                    "author": item.author,
                    "content": item.content[:1000],
                    "language": item.language,
                    "likes": item.engagement.get("score", item.engagement.get("likes", 0)),
                    "shares": item.engagement.get("shares", 0),
                    "comments": item.engagement.get("num_comments", item.engagement.get("comments", 0)),
                    "posted_at": item.posted_at.isoformat() if item.posted_at else "",
                    "scraped_at": item.scraped_at.isoformat() if item.scraped_at else "",
                    "url": item.url,
                    "hashtags": "|".join(item.hashtags),
                })
        logger.info(f"  Exported {len(items)} social posts to {path.name}")
