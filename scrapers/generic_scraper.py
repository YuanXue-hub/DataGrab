"""通用 HTML 爬虫

根据数据库 source 表中的 CSS 选择器配置，从任意网页抓取内容。
支持列表页 + 详情页两步抓取（获取完整正文）。
"""

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from core.base_scraper import BaseScraper
from storage.models import NewsArticle, DataItem
from storage.database import source_get
from utils.language_detector import detect_language


def _extract_date(text: str) -> Optional[datetime]:
    """尝试从文本中提取日期。"""
    if not text:
        return None

    patterns = [
        (r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', 'iso'),
        (r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', 'iso'),
        (r'\d{4}-\d{2}-\d{2}', 'date'),
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', 'cn'),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, text)
        if m:
            try:
                if fmt == 'cn':
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif fmt == 'date':
                    return datetime.strptime(m.group(), '%Y-%m-%d')
                else:
                    return datetime.fromisoformat(m.group())
            except (ValueError, IndexError):
                pass
    return None


class GenericScraper(BaseScraper):
    """通用 HTML 爬虫

    selectors 配置（JSON）：
    {
        // 列表页选择器
        "article_selector": "li",           // 文章容器 CSS
        "title_selector": "div.tit a",      // 标题
        "link_selector": "a",               // 链接（默认用 title_selector 的链接）
        "summary_selector": ".des",         // 列表页摘要（可选）

        // 详情页选择器（配置后自动进详情页抓取正文）
        "content_selector": "#detailContent", // 详情页正文
        "date_selector": ".info"              // 详情页日期（可选）
    }
    """

    def __init__(self, source_name: str = None, http_client=None, **kwargs):
        self.source_name = source_name or "generic"
        self.source_config = None
        self.selectors = {}
        self.target_url = ""

        if source_name:
            cfg = source_get(source_name)
            if cfg:
                self.source_config = cfg
                self.source_name = cfg["name"]
                import json
                raw = cfg.get("selectors")
                self.selectors = json.loads(raw) if isinstance(raw, str) else (raw or {})
                self.target_url = cfg["url"]

        super().__init__(http_client=http_client)
        self.logger = logger.bind(source=self.get_source_name())

    def get_source_name(self) -> str:
        return self.source_name

    def _ensure_selectors(self, url: str) -> str:
        """选择器兜底链：self.selectors → detect_selectors(url) → get_selectors(url)

        当 self.selectors 缺少 article_selector 时，自动调用 detector；
        detector 失败再回退到 preset。返回最终生效的来源标记：
        "manual" / "detector" / "preset" / "fallback"
        """
        if self.selectors.get("article_selector"):
            return "manual"

        from scrapers.selector_detector import detect_selectors
        from scrapers.selector_presets import get_selectors

        # 尝试自动检测
        try:
            detected = detect_selectors(url)
        except Exception as e:
            self.logger.warning(f"detect_selectors error: {e}")
            detected = None

        if detected:
            self.selectors = detected
            self.logger.info(f"Selectors auto-detected: {detected}")
            return "detector"

        # 回退到 preset
        preset = get_selectors(url)
        # 判断是否命中 PRESETS（非 FALLBACK）
        from scrapers.selector_presets import PRESETS, FALLBACK_SELECTORS
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname or ""
        is_preset = any(
            hostname == d or hostname.endswith("." + d) for d in PRESETS
        )
        self.selectors = preset
        source = "preset" if is_preset else "fallback"
        self.logger.info(f"Selectors from {source}: {preset}")
        return source

    def _extract_list(self, url: str, soup: BeautifulSoup, limit: int) -> List[NewsArticle]:
        """从列表页 soup 提取文章列表（Step 2 的独立方法，便于重试复用）。"""
        article_sel = self.selectors.get("article_selector", "")
        # 默认标题选择器：优先 h1/h2/h3 内的 a，回退到容器内首个有文本的 a
        title_sel = self.selectors.get("title_selector", "h1 a, h2 a, h3 a, h4 a, a")
        link_sel = self.selectors.get("link_selector", title_sel)
        summary_sel = self.selectors.get("summary_selector", "")
        link_filter = self.selectors.get("link_filter", "")

        if article_sel:
            containers = soup.select(article_sel)
        else:
            containers = [soup]

        self.logger.info(f"Found {len(containers)} containers, limit={limit}")

        articles: List[NewsArticle] = []

        for container in containers:
            if len(articles) >= limit:
                break

            try:
                # 标题
                title_el = container.select_one(title_sel)
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 6:
                    continue
                # 跳过明显的导航链接
                nav_patterns = [
                    '首页', '上一页', '下一页', '登录', '注册', '更多',
                    'Home', 'Login', 'Next', 'Prev', 'More', 'Back',
                ]
                if title.strip() in nav_patterns:
                    continue

                # 链接
                link = ""
                link_el = container.select_one(link_sel)
                if link_el and link_el.get("href"):
                    href = link_el["href"]
                    # 链接过滤：只保留匹配的链接（如含 /202）
                    if link_filter and link_filter not in href:
                        continue
                    link = urljoin(url, href) if href.startswith("/") else href

                # 列表页摘要（无选择器或未匹配到时留空，等详情页补充）
                summary = ""
                if summary_sel:
                    s_el = container.select_one(summary_sel)
                    if s_el:
                        summary = s_el.get_text(strip=True)[:300]

                article = NewsArticle(
                    title=title,
                    summary=summary,
                    content="",
                    source_name=self.source_name,
                    source_url=link or url,
                )
                articles.append(article)

            except Exception as e:
                self.logger.warning(f"Parse error: {e}")
                continue

        return articles

    def scrape(self, **kwargs) -> List[DataItem]:
        """两步抓取：列表页提取标题+链接 → 详情页提取正文+日期。

        选择器兜底链：self.selectors → detect_selectors(url) → get_selectors(url)
        抓取 0 条时自动重新检测一次并重试。

        Returns:
            NewsArticle 列表（含完整正文）
        """
        url = kwargs.get("url") or self.target_url
        limit = kwargs.get("limit", 20)

        if not url:
            self.logger.error("No URL configured")
            return []

        # ── 选择器兜底：article_selector 缺失时自动检测/回退 ──
        selector_source = self._ensure_selectors(url)

        self.logger.info(f"Scraping list: {url} (selectors={selector_source})")

        # ── Step 1: 列表页 ──
        raw_data = self.fetch(url)
        if raw_data.status_code == 0:
            self.logger.error(f"Failed to fetch {url}")
            return []

        soup = BeautifulSoup(raw_data.raw_html, "lxml")

        # ── Step 2: 提取列表项 ──
        articles = self._extract_list(url, soup, limit)
        self.logger.info(f"List extracted: {len(articles)} items")

        # ── P0-6: 抓取 0 条时自动重新检测并重试一次 ──
        if not articles and selector_source != "detector":
            self.logger.warning(
                f"Got 0 articles with {selector_source} selectors, "
                f"retrying with detect_selectors..."
            )
            try:
                from scrapers.selector_detector import detect_selectors
                detected = detect_selectors(url)
            except Exception as e:
                self.logger.warning(f"Retry detect_selectors error: {e}")
                detected = None

            if detected and detected.get("article_selector"):
                self.selectors = detected
                self.logger.info(f"Retry with detected selectors: {detected}")
                articles = self._extract_list(url, soup, limit)
                self.logger.info(f"Retry list extracted: {len(articles)} items")

        # ── Step 3: 详情页提取正文（Readability 算法，不依赖选择器）──
        if articles and articles[0].source_url and articles[0].source_url != url:
            self.logger.info(f"Fetching detail pages for content...")
            from scrapers.content_extractor import (
                extract_content, extract_summary, extract_date, extract_tags,
            )

            for i, article in enumerate(articles):
                if not article.source_url:
                    continue

                try:
                    detail_raw = self.fetch(article.source_url)
                    if detail_raw.status_code == 0:
                        self.logger.warning(
                            f"Detail fetch failed ({i+1}): {article.source_url}"
                        )
                        # content 留空，不用标题兜底
                        continue

                    html = detail_raw.raw_html

                    # 正文（Readability 算法自动提取）
                    content = extract_content(html)
                    if content and len(content) >= 50:
                        article.content = content
                        # 详情页成功时更新摘要（列表页摘要为空或过短时）
                        detail_summary = extract_summary(html)
                        if detail_summary and (
                            not article.summary or len(article.summary) < 20
                        ):
                            article.summary = detail_summary
                    else:
                        # Readability 提取失败（可能 JS 渲染页面），记录警告，content 留空
                        self.logger.warning(
                            f"Content extraction failed or too short ({i+1}): "
                            f"{article.source_url} (len={len(content) if content else 0})"
                        )

                    # 日期（meta 标签）
                    date_str = extract_date(html)
                    if date_str:
                        article.published_at = _extract_date(date_str)

                    # 标签
                    tags = extract_tags(html)
                    if tags:
                        article.tags = tags
                        # category 独立提取（暂用首个标签，后续可从 article:section 提取）
                        if not article.category:
                            article.category = tags[0] if tags else ""

                except Exception as e:
                    self.logger.warning(f"Detail parse error ({i+1}): {e}")
                    # content 留空，不用标题兜底

        # ── Step 4: 语言检测 + 摘要兜底 ──
        for article in articles:
            # 语言检测：基于正文或标题（正文优先）
            text_for_lang = article.content or article.summary or article.title
            article.language = detect_language(text_for_lang)

            # 摘要兜底：详情页成功时用正文前 300 字
            if not article.summary and article.content:
                article.summary = article.content[:300]
            # content 留空就留空，不用标题填充

        self.logger.info(f"Done: {len(articles)} articles")
        return articles

    def __repr__(self):
        return f"GenericScraper(source={self.source_name})"
