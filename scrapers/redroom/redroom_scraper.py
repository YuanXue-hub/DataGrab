"""RedroomCN 爬虫

从 redroomcn 地缘政治情报平台（localhost:3000 tRPC API）抓取数据。
"""

from pathlib import Path
from typing import List, Optional

import yaml
from loguru import logger

from core.base_scraper import BaseScraper
from scrapers.redroom.trpc_client import TRPCClient, TRPCError
from scrapers.redroom.parser import RedroomParser
from storage.models import DataItem


def _load_redroom_config() -> dict:
    """从 sources.yaml 加载 redroom 默认配置。"""
    search_paths = [
        Path(__file__).parent.parent.parent / "config" / "sources.yaml",
        Path.cwd() / "config" / "sources.yaml",
    ]
    for p in search_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                return config.get("redroom", {})
            except Exception:
                pass
    return {}


class RedroomScraper(BaseScraper):
    """从 redroomcn tRPC API 抓取数据。

    通过 scrape(**kwargs) 动态指定目标端点和查询参数。
    未显式指定的参数会从 config/sources.yaml 的 redroom 节读取默认值。

    scrape(**kwargs) 支持参数：
        endpoint: tRPC 过程名（默认 "articles.list"）
        region:   地区过滤，默认从 sources.yaml 读取（如 "MENA", "Europe", "Global"）
        limit:    返回数量限制（默认 20）
        topics:   主题过滤列表
        offset:   分页偏移
        search:   全文搜索关键词
        since:    ISO 日期字符串起始过滤
        types:    facility 类型过滤列表
        days:     timeline 天数（默认 7）
        isBreaking: 是否仅 breaking news
        agencyIds: 通讯社 ID 过滤列表
    """

    ENDPOINT_PARSERS = {
        "articles.list": "parse_articles",
        "articles.trending": "parse_articles",
        "articles.breaking": "parse_articles",
        "articles.timeline": "parse_timeline",
        "articles.networkGraph": "parse_network_graph",
        "articles.stats": "parse_stats",
        "agencies.list": "parse_agencies",
        "agencies.withStats": "parse_agencies",
        "facilities.list": "parse_facilities",
        "facilities.search": "parse_facilities",
    }

    def __init__(
        self,
        base_url: str = None,
        max_articles: int = 20,
        http_client=None,
        **kwargs,
    ):
        super().__init__(http_client=http_client)

        # 从 sources.yaml 加载默认配置
        config = _load_redroom_config()

        self.base_url = (base_url or config.get("base_url", "http://localhost:3000")).rstrip("/")
        self.max_articles = max_articles
        self.default_region = config.get("region")  # 配置的默认地区

        self.trpc = TRPCClient(base_url=self.base_url, http_client=self.http)
        self.parser = RedroomParser()
        self.logger = logger.bind(source=self.get_source_name())

    def get_source_name(self) -> str:
        return "redroom"

    def scrape(self, **kwargs) -> List[DataItem]:
        """执行爬取操作。

        根据 endpoint 参数调用对应的 tRPC 过程。
        未指定的参数自动使用 sources.yaml 中的默认值：
        - region: 使用配置的默认地区（如 "MENA"）

        Returns:
            DataItem 列表（主要为 NewsArticle）
        """
        endpoint = kwargs.pop("endpoint", "articles.list")
        limit = kwargs.pop("limit", self.max_articles)

        # 未显式传 region 时，使用配置的默认地区
        if "region" not in kwargs and self.default_region:
            kwargs["region"] = self.default_region

        # 构建查询参数（去除 None 值）
        input_data = {k: v for k, v in kwargs.items() if v is not None}
        if "limit" not in input_data:
            input_data["limit"] = limit

        self.logger.info(f"Scraping {endpoint} with {input_data}")

        # 调用 tRPC API
        try:
            raw_result = self.trpc.query(endpoint, input_data)
        except TRPCError as e:
            self.logger.error(f"tRPC error on {endpoint}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"HTTP error calling redroom API: {e}")
            return []

        if raw_result is None:
            self.logger.warning(f"Empty result from {endpoint}")
            return []

        # 确保结果是列表格式（供解析器处理）
        if not isinstance(raw_result, list):
            raw_result = [raw_result]

        # 选择解析器方法
        parser_method_name = self.ENDPOINT_PARSERS.get(endpoint, "parse_articles")
        parser_method = getattr(self.parser, parser_method_name, self.parser.parse_articles)

        parsed = parser_method(raw_result)
        self.logger.info(f"Parsed {len(parsed)} items from {endpoint}")

        return parsed

    def close(self):
        """清理资源。"""
        self.trpc.close()
        super().close()

    def __repr__(self):
        return f"RedroomScraper(base_url={self.base_url!r})"
