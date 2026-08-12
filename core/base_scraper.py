"""爬虫抽象基类

定义所有爬虫的统一接口，提供：
- HTTP 请求封装
- 速率限制
- 数据解析模板方法
- 错误处理
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from loguru import logger

from utils.http_client import HTTPClient
from storage.models import RawData, DataItem


class BaseScraper(ABC):
    """爬虫抽象基类

    子类只需实现：
    - get_source_name() -> str
    - scrape(**kwargs) -> List[DataItem]
    - 可选的 parse(raw_data: RawData) -> List[DataItem]
    """

    def __init__(self, http_client: Optional[HTTPClient] = None, source_language: str = None):
        """
        Args:
            http_client: HTTP 客户端实例，None 则创建默认客户端
            source_language: 数据源配置的语言代码 ('zh'|'en'|'ru'|'uk')，
                             用于设置正确的 Accept-Language 请求头
        """
        self.source_language = source_language
        if http_client is not None:
            self.http = http_client
            self._owns_http_client = False  # 共享客户端，不负责关闭
        else:
            self.http = HTTPClient()
            self._owns_http_client = True   # 自建客户端，负责关闭
        self.logger = logger.bind(source=self.get_source_name())

    @abstractmethod
    def get_source_name(self) -> str:
        """返回数据源名称（唯一标识符）"""
        ...

    @abstractmethod
    def scrape(self, **kwargs) -> List[DataItem]:
        """执行爬取操作

        Args:
            **kwargs: 爬取参数（如关键词、日期范围、最大条数等）

        Returns:
            解析后的数据列表
        """
        ...

    def parse(self, raw_data: RawData) -> List[DataItem]:
        """将原始数据解析为结构化数据

        子类可重写此方法实现自定义解析逻辑。
        默认返回空列表。

        Args:
            raw_data: 原始 HTTP 响应数据

        Returns:
            结构化数据列表
        """
        return []

    def fetch(self, url: str, headers: dict = None) -> RawData:
        """抓取单个 URL

        Args:
            url: 目标 URL
            headers: 自定义请求头

        Returns:
            RawData 原始数据对象
        """
        self.logger.info(f"Fetching: {url}")
        try:
            response = self.http.get(url, headers=headers, language=self.source_language)
            return RawData(
                source_name=self.get_source_name(),
                source_url=url,
                raw_html=response.text,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
        except Exception as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            return RawData(
                source_name=self.get_source_name(),
                source_url=url,
                status_code=0,
            )

    def close(self):
        """清理资源

        只有在自建 HTTPClient 时才关闭连接。
        共享客户端由 Engine 统一管理生命周期。
        """
        if self._owns_http_client:
            try:
                self.http.close()
            except Exception:
                pass

    def __repr__(self):
        return f"{self.__class__.__name__}(source={self.get_source_name()})"
