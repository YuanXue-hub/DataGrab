"""CSS 选择器自动检测器

对未知网站自动分析 HTML 结构，找出文章列表、标题、链接、
正文、日期、标签的选择器。无需人工配置。

检测策略：
1. 找"文章链接"（URL 含日期/article 等特征、有足够长的标题文本）
2. 找包含这些链接最多的容器元素 → article_selector
3. 分析容器内标题位置 → title_selector
4. 抓取 1-2 个详情页，找文本量最大的元素 → content_selector
5. 找日期/标签元素 → date_selector / tags_selector
6. 试抓取验证：用检测出的 selectors 实际抓取前 3 条，校验有效性
7. JS 渲染检测：抓取 1 个详情页，正文过短或含 noscript 提示则标记 js_rendered
"""

import re
from collections import Counter
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ru;q=0.7",
}

# 详情页正文候选选择器（精确 + 通配）
_CONTENT_CANDIDATES = [
    "article",
    '[itemprop="articleBody"]',
    ".article-body", ".article-content", ".article__text", ".article__body",
    ".post-body", ".post-content", ".entry-content", ".story-body",
    "#content", ".content", ".main-content", ".detail-content",
    ".article", "#article", ".news-content",
    '[class*="article__text"]', '[class*="article-text"]',
    '[class*="article-body"]', '[class*="article-content"]',
    '[class*="story-body"]', '[class*="post-content"]',
    '[class*="entry-content"]', '[class*="news-content"]',
    '[class*="detail-content"]', '[id*="article"]',
]

# 正文评分时降权的噪音区域
_NOISE_PATTERN = re.compile(
    r"copyright|footer|nav|header|cookie|banner|sidebar|related|comment|share|social|advert",
    re.I,
)

_DATE_CANDIDATES = [
    "time[datetime]", "time", '[class*="date"]', '[class*="time"]',
    '[class*="Date"]', '[class*="Time"]', ".pubdate", ".published",
]

_TAG_CANDIDATES = [
    '[class*="tag"] a', '[class*="Tag"] a', '.tags a',
    '[class*="keyword"] a', '[rel="tag"]',
]


def _is_article_link(href: str, text: str, base_url: str) -> bool:
    """判断一个链接是否指向文章详情页。"""
    if not text or len(text) < 10:
        return False
    if href.startswith(("#", "javascript:", "mailto:")):
        return False

    full = urljoin(base_url, href)
    base_host = urlparse(base_url).hostname or ""
    link_host = urlparse(full).hostname or ""

    # 允许同域名或子域
    if base_host and link_host and not (
        link_host == base_host
        or link_host.endswith("." + base_host)
        or base_host.endswith("." + link_host)
    ):
        return False

    # URL 特征：含日期
    if re.search(r"/20\d{2}([-/]\d{1,2}){0,2}", href):
        return True
    # URL 特征：含文章关键词
    if re.search(r"/(article|news|story|stories|post|r\/|video|videos|show|program)", href, re.I):
        return True
    # 多级路径的 html 结尾
    if re.search(r"\.(html?|shtml)$", href) and href.count("/") >= 2:
        return True
    return False


def _find_article_links(soup: BeautifulSoup, base_url: str) -> list:
    """找出页面上的文章链接列表 [(a_element, absolute_url)]。"""
    results = []
    seen_urls = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not _is_article_link(href, text, base_url):
            continue
        full = urljoin(base_url, href)
        if full in seen_urls:
            continue
        seen_urls.add(full)
        results.append((a, full))
    return results


def _detect_container(soup: BeautifulSoup, links: list, base_url: str) -> Optional[str]:
    """找出包含最多文章链接的容器选择器。"""
    if not links:
        return None

    url_set = {u for _, u in links}

    # 收集候选选择器：链接祖先的 class（拒绝纯标签名如 div/li）
    candidates = set()
    for a, _ in links[:15]:
        node = a.parent
        depth = 0
        while node and node.name != "body" and depth < 6:
            # 拒绝纯标签名（div/li/article 都太泛）
            for c in (node.get("class") or []):
                if c and not re.match(
                    r"^(col|row|grid|span|flex|container|wrapper|clearfix|"
                    r"left|right|center|float|lfloat|rfloat|fl|fr)$", c
                ):
                    candidates.add("." + c)
            node = node.parent
            depth += 1

    def _score(sel: str):
        """容器得分 = (含文章链接数, 精度(匹配数/总数), 总文本量)。"""
        try:
            els = soup.select(sel)
        except Exception:
            return (0, 0, 0)
        total = len(els)
        if total < 3 or total > 300:
            return (0, 0, 0)
        matching = 0
        total_text = 0
        for el in els:
            for a in el.select("a[href]"):
                href = urljoin(base_url, a.get("href", ""))
                if href in url_set:
                    matching += 1
                    total_text += len(el.get_text(strip=True))
                    break
        precision = matching / max(total, 1)
        # 精度 < 20% → 太多噪音，降权
        if precision < 0.2:
            matching = max(matching, 1)  # 保留但排后面
        return (matching, int(precision * 100), total_text)

    best_sel, best_key = None, (0, 0, 0)
    for cand in candidates:
        key = _score(cand)
        if key > best_key:
            best_key = key
            best_sel = cand

    return best_sel if best_key[0] >= 3 else None


def _detect_title_selector(soup: BeautifulSoup, container_sel: str) -> str:
    """在容器内确定标题选择器。"""
    try:
        containers = soup.select(container_sel)
    except Exception:
        return "a"

    for cand in ["h3 a", "h2 a", "h4 a", ".title a", '[class*="title"] a']:
        hits = 0
        for el in containers[:20]:
            if el.select_one(cand):
                hits += 1
        if hits >= max(2, len(containers[:20]) // 2):
            return cand
    return "a"


def _score_content_element(el) -> float:
    """给候选正文元素打分：文本量 × 段落密度，噪音区域降权。"""
    text = el.get_text(strip=True)
    text_len = len(text)
    if text_len < 150:
        return 0
    p_count = len(el.select("p"))
    score = text_len * (1.0 if p_count >= 2 else 0.3)
    cls = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
    if _NOISE_PATTERN.search(cls):
        score *= 0.05
    return score


def _detect_detail_selectors(detail_url: str) -> dict:
    """抓取详情页，检测正文/日期/标签选择器。"""
    result = {}
    try:
        resp = httpx.get(detail_url, headers=_HEADERS, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return result
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logger.warning(f"Detail fetch failed for detection: {e}")
        return result

    # 正文：得分最高的候选（文本量 × 段落密度，噪音降权）
    best_sel, best_score = None, 300  # 最低有效分数
    for sel in _CONTENT_CANDIDATES:
        try:
            for el in soup.select(sel)[:5]:
                score = _score_content_element(el)
                if score > best_score:
                    best_score = score
                    best_sel = sel
        except Exception:
            continue
    if best_sel:
        result["content_selector"] = best_sel

    # 兜底：找 <p> 最密集且文本量足够的父元素
    if not best_sel:
        from collections import Counter
        p_parents = Counter()
        parent_text = {}
        for p in soup.select("p"):
            if len(p.get_text(strip=True)) > 40:
                parent = p.parent
                if parent and parent.name not in ("body", "html") and parent.get("class"):
                    sel = "." + parent["class"][0]
                    if _NOISE_PATTERN.search(sel):
                        continue
                    p_parents[sel] += 1
                    parent_text[sel] = parent_text.get(sel, 0) + len(p.get_text(strip=True))
        # 要求至少 2 个段落且总文本 > 200
        valid = [s for s, c in p_parents.items() if c >= 2 and parent_text.get(s, 0) > 200]
        if valid:
            result["content_selector"] = max(valid, key=lambda s: parent_text[s])

    # 日期
    for sel in _DATE_CANDIDATES:
        try:
            if soup.select_one(sel):
                result["date_selector"] = sel
                break
        except Exception:
            continue

    # 标签
    for sel in _TAG_CANDIDATES:
        try:
            if len(soup.select(sel)) >= 2:
                result["tags_selector"] = sel
                break
        except Exception:
            continue

    return result


def detect_selectors(url: str) -> Optional[dict]:
    """对任意网址自动检测选择器。

    Args:
        url: 列表页网址

    Returns:
        selectors 字典；检测失败返回 None
    """
    logger.info(f"Auto-detecting selectors for {url}")
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logger.warning(f"Detection fetch failed: {e}")
        return None

    # 1. 找文章链接
    links = _find_article_links(soup, url)
    if len(links) < 3:
        logger.warning(f"Only found {len(links)} article links, detection failed")
        return None

    # 2. 找容器
    container = _detect_container(soup, links, url)
    if not container:
        logger.warning("No suitable container found")
        return None

    # 3. 标题选择器
    title_sel = _detect_title_selector(soup, container)

    selectors = {
        "article_selector": container,
        "title_selector": title_sel,
        "link_selector": title_sel if " a" in title_sel else "a",
        "link_filter": "",
    }

    # 4. 详情页检测：优先选日期型 URL（更像文章页），取前 2 个合并结果
    dated_links = [(a, u) for a, u in links if re.search(r"/20\d{2}", u)]
    other_links = [(a, u) for a, u in links if u not in {x[1] for x in dated_links}]
    detail_candidates = (dated_links + other_links)[:2]

    for _, detail_url in detail_candidates:
        detail = _detect_detail_selectors(detail_url)
        for k, v in detail.items():
            if k not in selectors:
                selectors[k] = v

    logger.info(f"Detected selectors for {url}: {selectors}")

    # 5. 试抓取验证：用检测出的 selectors 实际抓取前 3 条，校验有效性
    validation = validate_selectors(url, selectors, sample_size=3, html=resp.text)
    if not validation["passed"]:
        logger.info(
            f"Selectors validation failed: valid={validation['valid_count']}/"
            f"{validation['total_count']}, fallback to None"
        )
        return None

    # 6. JS 渲染检测：抓取首个样本详情页，正文过短或 noscript 提示则标记
    if validation["samples"]:
        first_detail = validation["samples"][0].get("url")
        if first_detail:
            selectors["js_rendered"] = _detect_js_rendered(first_detail)
        else:
            selectors["js_rendered"] = False
    else:
        selectors["js_rendered"] = False

    logger.info(
        f"Selectors validated: valid={validation['valid_count']}/"
        f"{validation['total_count']}, js_rendered={selectors['js_rendered']}"
    )
    return selectors


def validate_selectors(
    url: str,
    selectors: dict,
    sample_size: int = 3,
    html: Optional[str] = None,
) -> dict:
    """用传入 selectors 实际抓取列表页前 N 条，校验有效性。

    校验规则（每条样本需全部满足）：
    - 标题长度 ≥ 6
    - 链接同域（与列表页 base_url 比较）
    - 链接含日期或文章特征（复用 _is_article_link 逻辑）

    Args:
        url: 列表页网址
        selectors: 待验证的选择器字典
        sample_size: 校验前 N 条，默认 3
        html: 已抓取的列表页 HTML（避免重复请求），None 则内部抓取

    Returns:
        {
            "valid_count": int,      # 通过校验的条数
            "total_count": int,      # 实际抓取到的条数
            "samples": [{"title", "url", "summary"}],
            "passed": bool,          # total>=2 且 valid/total >= 0.6
        }
    """
    result = {"valid_count": 0, "total_count": 0, "samples": [], "passed": False}

    if not selectors or not selectors.get("article_selector"):
        return result

    # 抓取列表页 HTML（如未提供）
    if html is None:
        try:
            r = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
            if r.status_code != 200:
                return result
            html = r.text
        except Exception as e:
            logger.warning(f"validate_selectors fetch failed: {e}")
            return result

    soup = BeautifulSoup(html, "lxml")

    article_sel = selectors.get("article_selector", "")
    title_sel = selectors.get("title_selector", "a")
    link_sel = selectors.get("link_selector", title_sel)
    summary_sel = selectors.get("summary_selector", "")
    link_filter = selectors.get("link_filter", "")

    containers = soup.select(article_sel)
    if not containers:
        return result

    samples = []
    valid_count = 0

    for container in containers:
        if len(samples) >= sample_size:
            break

        try:
            title_el = container.select_one(title_sel)
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 6:
                continue

            link = ""
            link_el = container.select_one(link_sel)
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if link_filter and link_filter not in href:
                    continue
                link = urljoin(url, href) if href.startswith("/") else href

            summary = ""
            if summary_sel:
                s_el = container.select_one(summary_sel)
                if s_el:
                    summary = s_el.get_text(strip=True)[:300]

            # 校验：标题长度、链接同域、链接特征
            is_valid = False
            if link:
                full = urljoin(url, link)
                # _is_article_link 同时校验同域 + URL 特征
                if _is_article_link(link, title, url):
                    is_valid = True

            samples.append({"title": title, "url": link, "summary": summary})
            if is_valid:
                valid_count += 1
        except Exception:
            continue

    total = len(samples)
    passed = total >= 2 and valid_count / max(total, 1) >= 0.6

    return {
        "valid_count": valid_count,
        "total_count": total,
        "samples": samples,
        "passed": passed,
    }


def _detect_js_rendered(detail_url: str) -> bool:
    """抓取详情页，判断是否为 JS 渲染页面。

    判定规则（满足任一即视为 JS 渲染）：
    - 正文文本 < 150 字（Readability 提取失败，可能正文由 JS 注入）
    - 页面含 <noscript> 提示 "enable JavaScript"

    Args:
        detail_url: 详情页 URL

    Returns:
        True 表示疑似 JS 渲染页面
    """
    try:
        r = httpx.get(detail_url, headers=_HEADERS, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            return False
        html = r.text
    except Exception as e:
        logger.warning(f"JS render check fetch failed: {e}")
        return False

    # 检查 noscript 提示
    soup = BeautifulSoup(html, "lxml")
    for ns in soup.select("noscript"):
        text = ns.get_text(" ", strip=True).lower()
        if "enable javascript" in text or ("javascript" in text and "enable" in text):
            return True

    # 检查正文长度
    try:
        from scrapers.content_extractor import extract_content
        content = extract_content(html)
        if len(content) < 150:
            return True
    except Exception:
        pass

    return False