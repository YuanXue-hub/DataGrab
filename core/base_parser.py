"""解析器基类

定义数据解析的统一接口，不同数据类型使用不同的解析策略。
"""

from abc import ABC, abstractmethod
from typing import List
from bs4 import BeautifulSoup

from storage.models import RawData, DataItem


class BaseParser(ABC):
    """解析器抽象基类

    每种数据类型（新闻、军事、经济、社交媒体）对应一个 Parser 子类。
    """

    @abstractmethod
    def parse(self, raw_data: RawData) -> List[DataItem]:
        """解析原始数据为结构化数据

        Args:
            raw_data: 原始数据

        Returns:
            结构化数据列表
        """
        ...

    def make_soup(self, raw_data: RawData) -> BeautifulSoup:
        """将 raw_data 转换为 BeautifulSoup 对象

        Args:
            raw_data: 原始数据

        Returns:
            BeautifulSoup 实例
        """
        return BeautifulSoup(raw_data.raw_html, "lxml")

    def get_text(self, soup: BeautifulSoup, selector: str, default: str = "") -> str:
        """从 soup 中提取文本

        Args:
            soup: BeautifulSoup 对象
            selector: CSS 选择器
            default: 默认值

        Returns:
            提取的文本
        """
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else default

    def get_attr(self, soup: BeautifulSoup, selector: str, attr: str, default: str = "") -> str:
        """从 soup 中提取属性值

        Args:
            soup: BeautifulSoup 对象
            selector: CSS 选择器
            attr: 属性名
            default: 默认值

        Returns:
            属性值
        """
        el = soup.select_one(selector)
        return el.get(attr, default) if el else default
