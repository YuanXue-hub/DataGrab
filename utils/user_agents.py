"""User-Agent 池

提供随机 User-Agent 轮换功能，模拟不同浏览器和设备。
支持根据目标语言动态设置 Accept-Language 请求头。
"""

import random

from utils.language_detector import get_accept_language

# 桌面端 Chrome/Edge/Firefox (Windows + Mac)
_DESKTOP_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

# 移动端 UA
_MOBILE_AGENTS = [
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    # Android Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.53 Mobile Safari/537.36",
]

# 爬虫友好的通用 UA
_GENERIC_AGENTS = [
    "Mozilla/5.0 (compatible; DataGrab/0.1; +https://github.com/datagrab)",
    "Mozilla/5.0 (compatible; ResearchBot/1.0; +https://datagrab.example.com/bot)",
]


class UserAgentPool:
    """User-Agent 池，支持随机轮换"""

    def __init__(self, include_mobile: bool = False, include_generic: bool = False):
        self._pool = list(_DESKTOP_AGENTS)
        if include_mobile:
            self._pool.extend(_MOBILE_AGENTS)
        if include_generic:
            self._pool.extend(_GENERIC_AGENTS)

    def get_random(self) -> str:
        """随机获取一个 User-Agent"""
        return random.choice(self._pool)

    def get_headers(self, extra_headers: dict = None, language: str = None) -> dict:
        """获取带随机 UA 的请求头

        注意：不设置 Accept-Encoding 和 Connection，
        由 httpx 自动管理，避免干扰服务器的内容协商。

        Args:
            extra_headers: 额外的请求头
            language: 目标语言代码 ('zh'|'en'|'ru'|'uk')，
                      用于动态设置 Accept-Language 请求头

        Returns:
            包含 User-Agent 的请求头字典
        """
        accept_language = get_accept_language(language) if language else "en-US,en;q=0.9,zh-CN;q=0.8,ru;q=0.5,uk;q=0.3"
        headers = {
            "User-Agent": self.get_random(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": accept_language,
            "DNT": "1",  # Do Not Track
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers


# 全局默认 UA 池
_default_pool = UserAgentPool()
get_random_ua = _default_pool.get_random
get_headers = _default_pool.get_headers
