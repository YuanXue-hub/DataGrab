"""网页正文自动提取器（Readability 算法）

不依赖 CSS 选择器，对任意详情页自动识别正文内容。
参考 Mozilla Readability.js 的核心思想：
1. 移除非内容元素（script/style/nav/footer/header）
2. 对每个元素打分（文本密度 × class/id 权重）
3. 返回得分最高的元素内容
"""

import re
from bs4 import BeautifulSoup, Tag, NavigableString

# 高分标签（内容容器）
_HIGH_SCORE_TAGS = {"article", "main", "section"}

# 低分/排除的 class/id 关键词
_BAD_KEYWORDS = re.compile(
    r"nav|footer|header|sidebar|comment|share|social|advert|banner|"
    r"cookie|menu|widget|related|recommend|promo|popup|modal|"
    r"breadcrumb|copyright|pagination|toolbar",
    re.I,
)

# 高分的 class/id 关键词（正文容器）
_GOOD_KEYWORDS = re.compile(
    r"article|content|body|text|post|entry|story|detail|main",
    re.I,
)


def _score_node(el: Tag) -> float:
    """给 DOM 节点打分——越高越可能是正文容器。"""
    if not isinstance(el, Tag):
        return -100

    tag = el.name.lower()
    cls = " ".join(el.get("class") or []) + " " + (el.get("id") or "")

    score = 0

    # 标签基础分
    if tag in _HIGH_SCORE_TAGS:
        score += 20
    elif tag in ("div", "p"):
        score += 5
    elif tag in ("li", "td", "span", "a"):
        score -= 3

    # class/id 加权
    if _GOOD_KEYWORDS.search(cls):
        score += 25
    if _BAD_KEYWORDS.search(cls):
        score -= 50

    # 文本密度
    text = el.get_text(separator=" ", strip=True)
    text_len = len(text)
    if text_len < 100:
        return -100

    # 逗号/句号密度 → 自然语言信号
    sentence_count = text.count("。") + text.count(". ") + text.count("，") + text.count(", ")
    link_text_len = sum(len(a.get_text(strip=True)) for a in el.select("a"))
    link_ratio = link_text_len / max(text_len, 1)

    # 段落数
    p_count = len(el.select("p"))
    if p_count >= 2:
        score += 15

    # 文本量分
    score += min(text_len / 50, 60)  # 最多加60分（3000字打满）

    # 句子密度分
    score += min(sentence_count * 5, 25)

    # 链接密度惩罚
    if link_ratio > 0.5:
        score -= 30
    elif link_ratio < 0.2:
        score += 10

    return score


def extract_content(html: str) -> str:
    """从 HTML 中提取正文文本。

    提取顺序：
    1. textarea 数据容器（JS 渲染页面常见模式，如环球网把正文 HTML 实体编码存放在
       <textarea class="article-content"> 里，由前端 JS 渲染）：
       若 textarea 的 class/id 含 content/article/body/text/post/entry/story/detail
       且内容疑似 HTML（含 '<'），二次解析提取正文。
    2. Readability 打分算法（移除干扰元素后对候选节点打分取最高）。

    Args:
        html: 详情页原始 HTML

    Returns:
        提取的正文文本，失败返回空字符串
    """
    soup = BeautifulSoup(html, "lxml")

    # ── Step 1: textarea 数据容器提取（JS 渲染页面）──
    # 环球网等站点把正文 HTML 实体编码后放在 textarea 里供前端渲染，
    # Readability 算法无法识别这类容器，需特殊处理。
    for ta in soup.select("textarea"):
        cls = " ".join(ta.get("class") or []) + " " + (ta.get("id") or "")
        if not _GOOD_KEYWORDS.search(cls):
            continue
        raw = ta.get_text()
        # 疑似 HTML 内容（含标签且足够长）才二次解析
        if "<" not in raw or len(raw) < 200:
            continue
        try:
            inner = BeautifulSoup(raw, "lxml")
            # 移除内部 script/style/nav 等干扰
            for bad in inner.select("script, style, nav, footer, iframe"):
                bad.decompose()
            text = inner.get_text(separator="\n", strip=True)
            if len(text) >= 100:
                return text
        except Exception:
            continue

    # ── Step 2: Readability 打分算法 ──
    # 移除干扰元素
    for bad in soup.select(
        "script, style, nav, footer, iframe, noscript, "
        "form, button, input, select, textarea, "
        '[class*=nav], [class*=footer], [class*=header], [class*=sidebar], '
        '[class*=comment], [class*=share], [class*=advert], [class*=menu], '
        '[class*=breadcrumb], [class*=related], [class*=recommend], '
        '[id*=nav], [id*=footer], [id*=header], [id*=sidebar]'
    ):
        bad.decompose()

    # 找 body 下所有候选节点，打分
    best_el, best_score = None, 0
    for el in soup.select("article, div, section, main, [class], [id]"):
        score = _score_node(el)
        if score > best_score:
            best_score = score
            best_el = el

    if best_el:
        # 移除内部的链接列表等
        for ul in best_el.select("ul, ol"):
            link_count = len(ul.select("a"))
            text_count = len(ul.get_text(strip=True))
            # 链接密度高的列表 → 移除
            if link_count > 0 and text_count / max(link_count, 1) < 30:
                ul.decompose()

        return best_el.get_text(separator="\n", strip=True)

    return ""


def extract_summary(html: str, max_chars: int = 300) -> str:
    """从 HTML 提取摘要（正文前 N 字符）。"""
    content = extract_content(html)
    return content[:max_chars] if content else ""


def extract_date(html: str) -> str | None:
    """从 meta 标签提取发布日期。"""
    soup = BeautifulSoup(html, "lxml")
    for m in soup.select(
        'meta[property="article:published_time"], '
        'meta[name="pubdate"], meta[name="publish_date"], '
        'meta[name="date"], meta[property="og:article:published_time"]'
    ):
        val = m.get("content", "")
        if val:
            # 提取 ISO 日期部分
            match = re.search(r"\d{4}-\d{2}-\d{2}", val)
            if match:
                return match.group()
    return None


def extract_tags(html: str) -> list[str]:
    """提取标签/关键词。"""
    soup = BeautifulSoup(html, "lxml")
    tags = set()

    # meta keywords
    m = soup.select_one('meta[name="keywords"], meta[property="article:tag"]')
    if m and m.get("content"):
        tags.update(t.strip() for t in m["content"].split(",") if t.strip())

    # 显式标签链接
    for a in soup.select(
        '[class*=tag] a, [class*=Tag] a, [class*=keyword] a, '
        '[class*=category] a, [rel="tag"]'
    ):
        t = a.get_text(strip=True)
        if t and len(t) < 30:
            tags.add(t)

    return list(tags)[:15]
