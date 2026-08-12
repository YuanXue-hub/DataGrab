"""网站 CSS 选择器预设

按域名自动匹配选择器，用户创建数据源时无需手动填写 selectors。
只要填 name + url，系统自动找到对应的提取规则。
"""

PRESETS = {
    # ==================== 中文新闻 ====================
    "www.news.cn": {
        "article_selector": "li",
        "title_selector": "div.tit a",
        "link_selector": "div.tit a",
        "content_selector": "#detailContent",
        "date_selector": ".info",
    },
    "xinhuanet.com": {
        "article_selector": "li",
        "title_selector": "div.tit a",
        "link_selector": "div.tit a",
        "content_selector": "#detailContent",
        "date_selector": ".info",
    },
    "www.people.com.cn": {
        "article_selector": ".news-item, li",
        "title_selector": "h3 a, .title a",
        "link_selector": "a",
        "content_selector": ".rm_txt, .article, #p_content",
        "date_selector": ".time, .date",
    },
    "world.people.com.cn": {
        "article_selector": ".gray",
        "title_selector": "a",
        "link_selector": "a",
        "link_filter": "/n1/",
    },
    "www.cctv.com": {
        "article_selector": "li",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": ".cnt_bd, .article, #content_area",
        "date_selector": ".info, .time",
    },
    "www.chinanews.com": {
        "article_selector": "li",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": ".left_zw, .content, #cont_1_1_2",
        "date_selector": ".left_t, .time",
    },
    "www.163.com": {
        "article_selector": "ul li, [class*=news] li",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": ".post_body, .article-body, article p",
        "date_selector": ".post_time, .time, .date",
    },
    "www.qq.com": {
        "article_selector": "li",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": ".content-article, #ArticleContent, article",
        "date_selector": ".a_time, .time, .article-time",
    },
    "www.sohu.com": {
        "article_selector": "li, .news-item",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": ".article, #article-container, .text",
        "date_selector": ".time, .date",
    },
    "www.sina.com.cn": {
        "article_selector": "li",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": ".article, #artibody, .blk_detail",
        "date_selector": ".date, .time-source",
    },

    # ==================== 英文新闻 ====================
    "www.bbc.com": {
        "article_selector": "[data-testid*=card], li",
        "title_selector": "h2, h3",
        "link_selector": "a",
        "content_selector": "[data-component=text-block], article p",
        "date_selector": "time",
    },
    "www.reuters.com": {
        "article_selector": "[data-testid*=story], li",
        "title_selector": "[data-testid*=heading], h3",
        "link_selector": "a",
        "content_selector": "article p, [data-testid*=paragraph]",
        "date_selector": "time",
    },
    "www.theguardian.com": {
        "article_selector": "li",
        "title_selector": "h3 a, .fc-item__title",
        "link_selector": "a",
        "content_selector": "#maincontent p, .article-body-commercial-selector p",
        "date_selector": "time, .fc-item__timestamp",
    },

    # ==================== 俄罗斯卫星通讯社 ====================
    "sputniknews.cn": {
        "article_selector": ".cell-main-photo, .cell-list__item",
        "title_selector": ".cell-main-photo__title, .cell-list__item-title",
        "link_selector": "a",
        "summary_selector": ".cell-list__item-desc",
        "content_selector": ".article__body, .article__text",
        "date_selector": ".article__info-date",
        "tags_selector": ".tag__text",
        "link_filter": "/202",    # 只抓真实文章（链接含 /202）
    },

    # ==================== 本地/内网服务 ====================
    "localhost": {
        "article_selector": "li, article, .news-item, .post",
        "title_selector": "h1 a, h2 a, h3 a, .title a",
        "link_selector": "a",
        "content_selector": ".content, .body, article, #content",
        "date_selector": ".date, .time, time",
    },
    "127.0.0.1": {
        "article_selector": "li, article, .news-item, .post",
        "title_selector": "h1 a, h2 a, h3 a, .title a",
        "link_selector": "a",
        "content_selector": ".content, .body, article, #content",
        "date_selector": ".date, .time, time",
    },
}

# ==================== 通用兜底 ====================
FALLBACK_SELECTORS = {
    "article_selector": "li, article, .post, .news-item, .entry",
    "title_selector": "h1 a, h2 a, h3 a, .title a, a[href]",
    "link_selector": "a",
    "content_selector": ".content, .body, article, #content, .post-body",
    "date_selector": ".date, .time, time, [datetime]",
}


def get_selectors(url: str) -> dict:
    """根据 URL 自动匹配选择器。

    Args:
        url: 目标网址（如 https://www.news.cn）

    Returns:
        selectors 字典
    """
    from urllib.parse import urlparse

    hostname = urlparse(url).hostname or ""

    # 精确匹配
    if hostname in PRESETS:
        return dict(PRESETS[hostname])

    # 后缀匹配（如 subdomain.news.cn → *.news.cn）
    for domain, selectors in PRESETS.items():
        if hostname.endswith("." + domain):
            return dict(selectors)

    # 通用兜底
    return dict(FALLBACK_SELECTORS)
