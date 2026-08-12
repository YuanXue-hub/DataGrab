"""新闻文章解析器

从新闻网站 HTML 中提取结构化新闻数据。
支持中英俄乌等多语言新闻网站。
"""

from typing import List, Optional
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from core.base_parser import BaseParser
from storage.models import RawData, DataItem, NewsArticle
from utils.text_cleaner import clean_text, extract_date_from_text
from utils.language_detector import detect_language


class NewsParser(BaseParser):
    """新闻文章通用解析器

    支持从常见新闻网站提取标题、正文、日期、摘要等信息。
    """

    def __init__(self, source_language: str = None):
        """
        Args:
            source_language: 数据源配置的语言代码（'zh'|'en'|'ru'|'uk'），
                             作为语言检测的提示
        """
        self.source_language = source_language

    # 常见新闻内容容器选择器（按优先级排序）
    CONTENT_SELECTORS = [
        "article",
        '[role="main"]',
        ".article-body",
        ".article-content",
        ".story-body",
        ".post-content",
        ".entry-content",
        ".news-content",
        "#article-content",
        "#content-body",
        ".content",
        "main",
        '[itemprop="articleBody"]',
    ]

    # 需要移除的非内容元素
    REMOVE_SELECTORS = [
        "script", "style", "nav", "footer", "header",
        ".advertisement", ".ad", ".social-share",
        ".related-articles", ".related-posts",
        ".comments", "#comments",
        ".sidebar", ".aside",
        ".newsletter-signup", ".subscription",
        '[role="complementary"]',
    ]

    def parse(self, raw_data: RawData) -> List[DataItem]:
        """解析新闻原始数据

        Args:
            raw_data: 包含新闻 HTML 的原始数据

        Returns:
            NewsArticle 列表
        """
        if not raw_data.raw_html:
            return []

        soup = self.make_soup(raw_data)

        # 提取标题
        title = self._extract_title(soup)

        # 提取正文
        content = self._extract_content(soup)

        # 提取摘要
        summary = self._extract_summary(soup, content)

        # 提取发布日期
        published_at = self._extract_date(soup, raw_data.raw_html)

        # 提取标签
        tags = self._extract_tags(soup)

        # 检测语言
        language = self._detect_language(title, content)

        if not title or not content:
            logger.debug(f"No title or content found for {raw_data.source_url}")
            return []

        article = NewsArticle(
            title=clean_text(title),
            content=clean_text(content),
            summary=clean_text(summary),
            source_name=raw_data.source_name,
            source_url=raw_data.source_url,
            language=language,
            published_at=published_at,
            scraped_at=raw_data.fetched_at,
            tags=tags,
        )
        return [article]

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取文章标题"""
        # 按优先级尝试常见标题选择器
        title_selectors = [
            "h1",
            '[property="og:title"]',
            '[name="twitter:title"]',
            ".article-title",
            ".entry-title",
            ".post-title",
            ".story-title",
            "title",
        ]
        for selector in title_selectors:
            el = soup.select_one(selector)
            if el:
                if el.name in ("meta",):
                    return el.get("content", "")
                return el.get_text(strip=True)
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """提取文章正文"""
        # 移除无用元素
        for selector in self.REMOVE_SELECTORS:
            for el in soup.select(selector):
                el.decompose()

        # 尝试找到主要内容容器
        content_el = None
        for selector in self.CONTENT_SELECTORS:
            content_el = soup.select_one(selector)
            if content_el:
                break

        if content_el:
            text = content_el.get_text(separator="\n", strip=True)
        else:
            # 回退：取 body 全文
            body = soup.find("body")
            text = body.get_text(separator="\n", strip=True) if body else ""

        return text

    def _extract_summary(self, soup: BeautifulSoup, content: str) -> str:
        """提取文章摘要"""
        # 尝试 meta description
        for selector in [
            '[name="description"]',
            '[property="og:description"]',
            '[name="twitter:description"]',
        ]:
            el = soup.select_one(selector)
            if el and el.get("content"):
                return el["content"]

        # 回退：取正文前 200 字
        if content:
            return content[:200]
        return ""

    def _extract_date(self, soup: BeautifulSoup, raw_html: str) -> datetime | None:
        """提取发布日期"""
        # 尝试 meta 标签
        for selector in [
            '[property="article:published_time"]',
            '[name="pubdate"]',
            '[name="publish_date"]',
            '[name="date"]',
            'time[datetime]',
        ]:
            el = soup.select_one(selector)
            if el:
                date_str = el.get("content") or el.get("datetime") or el.get_text(strip=True)
                if date_str:
                    try:
                        return self._parse_datetime(date_str)
                    except (ValueError, Exception):
                        pass

        # 尝试从 URL 中提取日期 (如 /2024/06/08/)
        date_match = extract_date_from_text(raw_html[:2000])
        if date_match:
            try:
                return datetime.strptime(date_match, "%Y-%m-%d")
            except ValueError:
                pass

        return None

    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """提取文章标签/关键词"""
        tags = []
        # meta keywords
        el = soup.select_one('[name="keywords"]')
        if el and el.get("content"):
            tags = [t.strip() for t in el["content"].split(",") if t.strip()]

        # 显式标签元素
        if not tags:
            for el in soup.select(".tags a, .tag, .article-tag a, .category a"):
                tag = el.get_text(strip=True)
                if tag and len(tag) < 30:
                    tags.append(tag)

        return tags[:10]

    def _detect_language(self, title: str, content: str) -> str:
        """检测文本语言

        委托给 language_detector 模块，支持中/英/俄/乌克兰语。

        Args:
            title: 文章标题
            content: 文章正文

        Returns:
            语言代码 ('zh', 'en', 'ru', 'uk')
        """
        text = (title + " " + content)[:2000]
        return detect_language(text, hint=self.source_language)

    @staticmethod
    def _parse_datetime(date_str: str) -> datetime:
        """尝试多种日期格式解析"""
        from dateutil.parser import parse as dateutil_parse
        try:
            return dateutil_parse(date_str)
        except Exception:
            pass

        # 尝试常见格式
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        raise ValueError(f"Cannot parse date: {date_str}")
