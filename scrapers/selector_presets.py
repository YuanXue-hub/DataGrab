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
    "www.ifeng.com": {
        "article_selector": ".news-stream .news-stream-news li, .news-list li",
        "title_selector": "h3 a, .title a, a",
        "link_selector": "a",
        "content_selector": ".main_content .article, .text_content, #artical_real",
        "date_selector": ".time, .date, [class*=time]",
    },
    "www.thepaper.cn": {
        "article_selector": ".news_li, .news-item, li",
        "title_selector": "a, h3 a",
        "link_selector": "a",
        "content_selector": ".news_txt, .article-content, [class*=content]",
        "date_selector": ".time, [class*=time]",
    },
    "www.jiemian.com": {
        "article_selector": ".news-list li, .card-list li, li",
        "title_selector": "h3 a, .title a, a",
        "link_selector": "a",
        "content_selector": ".article-content, .content, [class*=content]",
        "date_selector": ".date, .time, [class*=time]",
    },
    "www.yicai.com": {
        "article_selector": ".news-list li, .list li, li",
        "title_selector": "h3 a, .title a, a",
        "link_selector": "a",
        "content_selector": ".article-content, .content, .text-content",
        "date_selector": ".date, .time, [class*=time]",
    },
    "www.caixin.com": {
        "article_selector": ".list li, .news-list li, li",
        "title_selector": "h4 a, h3 a, .title a, a",
        "link_selector": "a",
        "content_selector": ".article-content, #Main_Content_Val, .text",
        "date_selector": ".date, .time, [class*=time]",
    },
    "www.81.cn": {
        "article_selector": ".list li, .news-list li, li",
        "title_selector": "h3 a, h4 a, .title a, a",
        "link_selector": "a",
        "link_filter": "/",
        "content_selector": ".article-content, .content, .text",
        "date_selector": ".date, .time, [class*=time]",
    },
    "ckxx.apdnews.com": {
        "article_selector": ".list li, .news-list li, li",
        "title_selector": "h3 a, .title a, a",
        "link_selector": "a",
        "content_selector": ".article-content, .content, .text",
        "date_selector": ".date, .time, [class*=time]",
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
    "www.cnn.com": {
        "article_selector": ".container__item--type-section, li",
        "title_selector": ".container__headline-text, h3, a",
        "link_selector": "a",
        "content_selector": ".article__content p, .articlebody p, [data-zn-id]",
        "date_selector": ".timestamp, time, [class*=time]",
    },
    "www.nytimes.com": {
        "article_selector": "li, .css-1l4spti",
        "title_selector": "h3 a, h2 a, .indicate-hover, a",
        "link_selector": "a",
        "content_selector": ".article-body p, [class*=story-content], article p",
        "date_selector": "time, [class*=date]",
    },
    "www.aljazeera.com": {
        "article_selector": ".gc__content, li",
        "title_selector": ".gc__title a, h3 a, a",
        "link_selector": "a",
        "content_selector": ".article__p, .wysiwyg p, [class*=article-content]",
        "date_selector": ".date, time, [class*=time]",
    },
    "www.ndtv.com": {
        "article_selector": ".news-list li, .lhs-card li, li",
        "title_selector": "h2 a, h3 a, a",
        "link_selector": "a",
        "content_selector": ".ins_storybody p, .article-content p, [class*=content]",
        "date_selector": ".date, .time, [class*=time]",
    },
    "www.reuters.com": {
        "article_selector": "[data-testid*=story], li, .story-card",
        "title_selector": "[data-testid*=heading], h3, h2",
        "link_selector": "a",
        "content_selector": "article p, [data-testid*=paragraph], .article-body p",
        "date_selector": "time, [class*=date]",
    },
    "apnews.com": {
        "article_selector": ".SearchResultsPage-results-list a, .PageList-items-item, li",
        "title_selector": ".PagePromo-title, h2, h3, a",
        "link_selector": "a",
        "content_selector": ".Article p, .RichTextStoryBody p, [class*=article-body]",
        "date_selector": "time, [class*=date]",
    },
    "www.bloomberg.com": {
        "article_selector": ".story-list__story, li",
        "title_selector": "h3 a, h2 a, a",
        "link_selector": "a",
        "content_selector": ".body-content p, .article-body p, [class*=content]",
        "date_selector": "time, [class*=date]",
    },

    # ==================== 科技 / 社区 ====================
    "techcrunch.com": {
        "article_selector": "article, .post-block, li",
        "title_selector": "h2 a, .article__title a, a",
        "link_selector": "a",
        "content_selector": ".article-content, .article__content, article p",
        "date_selector": "time, .full-date-time, [class*=time]",
    },
    "www.theverge.com": {
        "article_selector": ".duet--content-cards--content-card, li",
        "title_selector": "h2 a, h3 a, a",
        "link_selector": "a",
        "content_selector": ".article__body p, [class*=article-body], article p",
        "date_selector": "time, [class*=date]",
    },
    "news.ycombinator.com": {
        "article_selector": ".athing",
        "title_selector": ".titleline a, a",
        "link_selector": "a",
        "link_filter": "item?id=",
        "content_selector": "",
        "date_selector": ".age, [class*=time]",
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
