"""HTTP 客户端封装

基于 httpx 封装，提供：
- 自动重试（指数退避）
- User-Agent 轮换
- 速率限制
- 超时控制
- 代理支持
"""

from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

from utils.rate_limiter import _global_limiter
from utils.user_agents import get_headers


class HTTPClient:
    """HTTP 客户端封装"""

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        proxy: Optional[str] = None,
        verify_ssl: bool = True,
        follow_redirects: bool = True,
    ):
        """
        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_backoff: 重试退避因子（指数增长）
            proxy: 代理地址（如 http://127.0.0.1:7890）
            verify_ssl: 是否验证 SSL 证书
            follow_redirects: 是否跟随重定向
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.follow_redirects = follow_redirects

        # 构建客户端
        client_kwargs = {
            "timeout": httpx.Timeout(timeout),
            "verify": verify_ssl,
            "follow_redirects": follow_redirects,
        }
        if proxy:
            client_kwargs["proxy"] = proxy

        self._client = httpx.Client(**client_kwargs)

    def get(self, url: str, headers: dict = None, language: str = None, **kwargs) -> httpx.Response:
        """发送 GET 请求（带重试和限速）

        Args:
            url: 请求 URL
            headers: 自定义请求头（会与默认 UA 合并）
            language: 目标语言代码，用于设置 Accept-Language 请求头
            **kwargs: 传递给 httpx 的额外参数

        Returns:
            httpx.Response 对象

        Raises:
            httpx.RequestError: 所有重试失败后抛出
        """
        domain = urlparse(url).netloc

        # 合并请求头
        if headers:
            base_headers = get_headers(language=language)
            base_headers.update(headers)
            req_headers = base_headers
        else:
            req_headers = get_headers(language=language)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # 速率限制等待
                _global_limiter.wait(domain)

                logger.debug(f"GET {url} (attempt {attempt + 1}/{self.max_retries + 1})")
                response = self._client.get(url, headers=req_headers, **kwargs)

                # 检查 HTTP 错误状态码
                if response.status_code >= 500:
                    logger.warning(
                        f"Server error {response.status_code} from {url}"
                    )
                    if attempt < self.max_retries:
                        wait_time = self.retry_backoff ** attempt
                        logger.info(f"Retrying in {wait_time:.1f}s...")
                        import time
                        time.sleep(wait_time)
                        continue

                response.raise_for_status()
                return response

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                logger.warning(f"Request to {url} failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff ** attempt
                    logger.info(f"Retrying in {wait_time:.1f}s...")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed for {url}")

            except httpx.HTTPStatusError as e:
                # 4xx 错误不重试（客户端错误）
                logger.error(f"Client error for {url}: {e.response.status_code}")
                raise

        raise last_error if last_error else httpx.RequestError(
            f"Request to {url} failed after {self.max_retries + 1} attempts"
        )

    def post(self, url: str, headers: dict = None, **kwargs) -> httpx.Response:
        """发送 POST 请求"""
        domain = urlparse(url).netloc
        req_headers = get_headers()
        if headers:
            req_headers.update(headers)

        _global_limiter.wait(domain)
        return self._client.post(url, headers=req_headers, **kwargs)

    def close(self):
        """关闭客户端"""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
