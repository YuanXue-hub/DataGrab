"""爬虫引擎

负责：
1. 加载配置，初始化爬虫实例
2. 编排爬取任务（串行/并发控制）
3. 驱动数据处理管道
4. 收集结果到 Repository
5. 调用导出器
"""

import concurrent.futures
import os
from pathlib import Path
from typing import List, Optional, Dict, Type

import yaml
from loguru import logger

from core.base_scraper import BaseScraper
from core.pipeline import Pipeline
from storage.repository import Repository
from storage.models import DataItem
from utils.http_client import HTTPClient
from utils.rate_limiter import _global_limiter


def _load_config(config_path: str = None) -> dict:
    """加载 YAML 配置文件

    Args:
        config_path: 配置文件路径，None 则使用默认路径

    Returns:
        配置字典
    """
    if config_path is None:
        # 尝试从项目根目录加载
        search_paths = [
            Path(__file__).parent.parent / "config" / "config.yaml",
            Path.cwd() / "config" / "config.yaml",
        ]
        for p in search_paths:
            if p.exists():
                config_path = str(p)
                break

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            logger.debug(f"Loaded config from {config_path}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")

    logger.debug("No config file found, using defaults")
    return {}


def _load_sources_config(config_path: str = None) -> dict:
    """加载 sources.yaml 配置文件

    Args:
        config_path: 配置文件路径，None 则使用默认路径

    Returns:
        数据源配置字典
    """
    if config_path is None:
        search_paths = [
            Path(__file__).parent.parent / "config" / "sources.yaml",
            Path.cwd() / "config" / "sources.yaml",
        ]
        for p in search_paths:
            if p.exists():
                config_path = str(p)
                break

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            logger.debug(f"Loaded sources config from {config_path}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load sources config from {config_path}: {e}")

    return {}


class ScraperEngine:
    """爬虫引擎

    统一管理所有爬虫的生命周期和执行。
    """

    def __init__(
        self,
        config: dict = None,
        http_client: HTTPClient = None,
        max_concurrent: int = 3,
        proxy: str = None,
    ):
        """
        Args:
            config: 全局配置字典
            http_client: HTTP 客户端实例
            max_concurrent: 最大并发爬虫数
            proxy: 代理地址（如 http://127.0.0.1:7890），
                   优先级：参数 > 环境变量 HTTP_PROXY > config.yaml
        """
        # 加载配置文件
        self.config = config or _load_config()
        self.sources_config = _load_sources_config()

        # 确定代理地址：参数 > 环境变量 > 配置文件
        effective_proxy = proxy
        if not effective_proxy:
            effective_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        if not effective_proxy:
            proxy_cfg = self.config.get("global", {}).get("proxy", {})
            if proxy_cfg and proxy_cfg.get("enabled", False):
                effective_proxy = proxy_cfg.get("url", "") or None

        # 创建 HTTP 客户端
        if http_client:
            self.http_client = http_client
        else:
            client_kwargs = {}
            if effective_proxy:
                client_kwargs["proxy"] = effective_proxy
                logger.info(f"Using proxy: {effective_proxy}")
            self.http_client = HTTPClient(**client_kwargs)

        # 读取配置
        global_cfg = self.config.get("global", {})
        self.max_concurrent = max_concurrent if max_concurrent != 3 else global_cfg.get("max_concurrent", 3)

        # 配置速率限制
        request_delay = global_cfg.get("request_delay", 2.0)
        if request_delay:
            _global_limiter._default_delay = request_delay

        self.repository = Repository()
        self.pipeline = Pipeline()
        self._scrapers: Dict[str, BaseScraper] = {}
        self._scraper_registry: Dict[str, Type[BaseScraper]] = {}

    def register_scraper(self, name: str, scraper_cls: Type[BaseScraper]):
        """注册爬虫类型

        Args:
            name: 爬虫名称
            scraper_cls: 爬虫类
        """
        self._scraper_registry[name] = scraper_cls
        logger.debug(f"Registered scraper: {name}")

    def register_scrapers(self, scrapers: Dict[str, Type[BaseScraper]]):
        """批量注册爬虫类型"""
        for name, cls in scrapers.items():
            self.register_scraper(name, cls)

    def create_scraper(self, name: str, **kwargs) -> Optional[BaseScraper]:
        """根据注册名创建爬虫实例

        Args:
            name: 爬虫注册名
            **kwargs: 传递给爬虫构造函数的参数

        Returns:
            BaseScraper 实例或 None
        """
        cls = self._scraper_registry.get(name)
        if cls is None:
            logger.error(f"Unknown scraper: {name}")
            return None

        kwargs.setdefault("http_client", self.http_client)
        try:
            scraper = cls(**kwargs)
            self._scrapers[name] = scraper
            return scraper
        except Exception as e:
            logger.error(f"Failed to create scraper '{name}': {e}")
            return None

    def run(
        self,
        sources: List[str] = None,
        data_types: List[str] = None,
        max_per_source: int = 20,
        parallel: bool = False,
        languages: List[str] = None,
    ) -> List[DataItem]:
        """执行爬取任务

        Args:
            sources: 要运行的爬虫名称列表，None 则运行全部已注册爬虫
            data_types: 数据类型过滤（暂未实现）
            max_per_source: 每个数据源的最大爬取条数
            parallel: 是否并行运行多个爬虫
            languages: 按语言过滤数据源（如 ['ru', 'uk']），None 则不过滤

        Returns:
            所有爬取结果的列表
        """
        source_names = sources or list(self._scraper_registry.keys())

        # 按语言过滤数据源
        if languages:
            filtered = []
            for name in source_names:
                lang = self._get_source_language(name)
                if lang and lang in languages:
                    filtered.append(name)
            if not filtered:
                logger.warning(
                    f"No sources match languages={languages}. "
                    f"Available language tags are in config/sources.yaml"
                )
            source_names = filtered

        logger.info(f"Engine starting: {len(source_names)} sources")

        all_results: List[DataItem] = []

        if parallel and len(source_names) > 1:
            # 并行模式
            all_results = self._run_parallel(source_names, max_per_source)
        else:
            # 串行模式
            for name in source_names:
                try:
                    results = self._run_single(name, max_per_source)
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Scraper '{name}' failed: {e}")

        # 存入仓库
        self.repository.add_all(all_results)

        logger.info(
            f"Engine done: {len(all_results)} total items "
            f"from {len(source_names)} sources\n"
            f"  Summary: {self.repository.summary()}"
        )
        return all_results

    def _get_source_language(self, name: str) -> str:
        """从 sources.yaml 获取数据源配置的语言

        遍历 sources.yaml 的所有分类（news, social, military, economic），
        查找指定名称的数据源并返回其 language 字段。

        Args:
            name: 数据源名称

        Returns:
            语言代码字符串，找不到时返回 None
        """
        for category, sources in self.sources_config.items():
            if isinstance(sources, dict) and name in sources:
                return sources[name].get("language", None)
        return None

    def get_keywords(self, language: str) -> list[str]:
        """获取指定语言的关键词列表

        Args:
            language: 语言代码 ('zh'|'en'|'ru'|'uk')

        Returns:
            关键词字符串列表
        """
        keywords_config = self.config.get("scraping", {}).get("keywords", {})
        return keywords_config.get(language, [])

    def _run_single(self, name: str, max_per_source: int) -> List[DataItem]:
        """运行单个爬虫"""
        source_language = self._get_source_language(name)
        logger.debug(f"  [{name}] source_language={source_language}")
        scraper = self.create_scraper(
            name, max_articles=max_per_source,
            source_language=source_language,
        )
        if scraper is None:
            return []

        try:
            results = scraper.scrape()
            logger.info(f"  [{name}] {len(results)} items")
            return results
        finally:
            scraper.close()

    def _run_parallel(
        self, source_names: List[str], max_per_source: int
    ) -> List[DataItem]:
        """并行运行多个爬虫"""
        all_results: List[DataItem] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.max_concurrent, len(source_names))
        ) as executor:
            futures = {}
            for name in source_names:
                future = executor.submit(self._run_single, name, max_per_source)
                futures[future] = name

            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Scraper '{name}' raised: {e}")

        return all_results

    def get_repository(self) -> Repository:
        """获取数据仓库"""
        return self.repository

    def get_scraper(self, name: str) -> Optional[BaseScraper]:
        """获取已创建的爬虫实例"""
        return self._scrapers.get(name)

    def list_sources(self) -> List[str]:
        """列出所有已注册的数据源"""
        return list(self._scraper_registry.keys())

    def cleanup(self):
        """清理所有爬虫资源和共享 HTTP 客户端"""
        for scraper in self._scrapers.values():
            try:
                scraper.close()
            except Exception:
                pass
        self._scrapers.clear()
        # 关闭共享 HTTP 客户端
        try:
            self.http_client.close()
        except Exception:
            pass
        logger.debug("Engine cleanup complete")
