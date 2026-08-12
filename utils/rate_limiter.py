"""速率限制器

基于令牌桶算法实现域名级别的请求速率控制。
"""

import time
import threading
from collections import defaultdict


class RateLimiter:
    """令牌桶限速器

    按域名控制请求频率，避免对目标服务器造成过大压力。
    """

    def __init__(self, default_delay: float = 2.0):
        """
        Args:
            default_delay: 默认请求间隔（秒）
        """
        self._default_delay = default_delay
        self._last_request: dict[str, float] = defaultdict(float)
        self._domain_delays: dict[str, float] = {}
        self._lock = threading.Lock()

    def set_domain_delay(self, domain: str, delay: float):
        """为特定域名设置请求间隔

        Args:
            domain: 域名（如 bbc.com）
            delay: 请求间隔（秒）
        """
        self._domain_delays[domain] = delay

    def wait(self, domain: str):
        """等待直到可以发起下一次请求

        Args:
            domain: 目标域名
        """
        delay = self._domain_delays.get(domain, self._default_delay)

        with self._lock:
            elapsed = time.time() - self._last_request.get(domain, 0)
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_request[domain] = time.time()

    def get_domain(self, url: str) -> str:
        """从 URL 中提取域名

        Args:
            url: 完整 URL

        Returns:
            域名部分
        """
        from urllib.parse import urlparse
        return urlparse(url).netloc or url


# 全局限速器实例
_global_limiter = RateLimiter()
