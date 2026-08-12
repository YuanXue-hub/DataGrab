"""数据源爬虫模块"""

# 惰性导入，避免缺少可选依赖时无法加载模块

def _lazy_import(module_path: str, class_name: str):
    """惰性导入工厂"""
    import importlib
    def _import():
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    return _import


# 注册表：爬虫名称 -> (导入函数, 描述)
SCRAPER_REGISTRY = {
    "bbc": ("scrapers.news.bbc_scraper", "BBCScraper", "BBC News 英文新闻"),
    "xinhua": ("scrapers.news.xinhua_scraper", "XinhuaScraper", "新华网中文新闻"),
    "ifeng": ("scrapers.news.ifeng_scraper", "IfengScraper", "凤凰网军事中文新闻"),
    "isw": ("scrapers.military.isw_scraper", "ISWScraper", "ISW 战争研究所每日战报"),
    "reddit": ("scrapers.social.reddit_scraper", "RedditScraper", "Reddit 社交媒体讨论"),
    "tass": ("scrapers.news.tass_scraper", "TassScraper", "TASS 俄通社俄语新闻"),
    "ria": ("scrapers.news.ria_scraper", "RiaScraper", "RIA Novosti 俄新社俄语新闻"),
    "pravda": ("scrapers.news.pravda_scraper", "PravdaScraper", "Ukrainska Pravda 乌克兰真理报（403封锁）"),
    "unian": ("scrapers.news.unian_scraper", "UnianScraper", "UNIAN 乌克兰独立新闻社乌语新闻"),
    "ukrinform": ("scrapers.news.ukrinform_scraper", "UkrinformScraper", "Ukrinform 乌克兰国家通讯社乌语新闻"),
    "redroom": ("scrapers.redroom.redroom_scraper", "RedroomScraper", "RedroomCN 地缘政治情报平台 (tRPC API)"),
}


def get_scraper_class(name: str):
    """根据名称获取爬虫类

    Args:
        name: 爬虫注册名

    Returns:
        爬虫类或 None
    """
    import importlib

    info = SCRAPER_REGISTRY.get(name)
    if not info:
        return None

    module_path, class_name, _ = info
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    except ImportError as e:
        raise ImportError(
            f"Cannot import scraper '{name}': {e}. "
            f"Please install required dependencies."
        )


def list_scrapers() -> dict:
    """列出所有可用爬虫"""
    return {name: desc for name, (_, _, desc) in SCRAPER_REGISTRY.items()}
