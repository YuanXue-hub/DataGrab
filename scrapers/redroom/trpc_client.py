"""tRPC HTTP 协议客户端

封装对 redroomcn tRPC API 的 HTTP 请求，处理：
- URL 构造：遵循 tRPC v11 httpBatchLink 格式
  GET /api/trpc/{procedure}?batch=1&input={superjson_encoded}
- 输入序列化：使用 superjson 格式 {"json": <input_data>}
- 响应解析：处理 tRPC 响应信封和 superjson 反序列化
- 错误处理：TRPCError 异常
"""

import json
from typing import Optional, Any
from urllib.parse import quote

from loguru import logger

from utils.http_client import HTTPClient


class TRPCError(Exception):
    """tRPC 协议错误"""

    def __init__(self, message: str, code: str = "INTERNAL_SERVER_ERROR"):
        self.code = code
        super().__init__(f"[{code}] {message}")


def _serialize_input(input_data: dict) -> dict:
    """将输入数据序列化为 superjson 格式。

    superjson 将普通对象包装为 {"json": <value>}。
    例如 {"limit": 2} → {"json": {"limit": 2}}

    Args:
        input_data: 原始输入字典

    Returns:
        superjson 包装后的字典
    """
    return {"json": input_data}


def _deserialize_superjson(obj: Any) -> Any:
    """递归解析 superjson 编码的数据。

    superjson 将特殊类型（Date, BigInt, Map, Set 等）编码为：
        {"json": <value>, "meta": {"values": [<type_hint>]}}

    对于普通 JSON 值，直接透传。在递归前会先处理外层的 {"json": ...} 包装。
    """
    import datetime as dt

    if isinstance(obj, dict):
        # 先处理 superjson 顶层包装：{"json": <actual_value>}
        # superjson 将普通对象包装成 {"json": {...}}
        if set(obj.keys()) == {"json"}:
            return _deserialize_superjson(obj["json"])

        # 检测 superjson 类型包装：{"json": X, "meta": {...}}
        if set(obj.keys()) == {"json", "meta"} and isinstance(obj.get("meta"), dict):
            meta_values = obj["meta"].get("values", [])
            json_value = obj["json"]

            # 提取类型提示（兼容 list 和 dict 两种格式）
            type_hint = None
            if isinstance(meta_values, list) and len(meta_values) > 0:
                type_hint = meta_values[0]
            elif isinstance(meta_values, dict) and len(meta_values) > 0:
                type_hint = list(meta_values.values())[0]

            if type_hint:
                if type_hint == "Date" and isinstance(json_value, str):
                    try:
                        return dt.datetime.fromisoformat(
                            json_value.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        return json_value
                elif type_hint == "bigint":
                    return int(json_value) if json_value is not None else None
                elif type_hint == "Set":
                    return set(json_value) if isinstance(json_value, list) else json_value
                elif type_hint == "Map":
                    return dict(json_value) if isinstance(json_value, (dict, list)) else json_value
                elif type_hint == "RegExp":
                    return str(json_value) if json_value is not None else None
                elif type_hint == "undefined":
                    return None

            # meta.values 为空或无法识别时，递归解析 json 值
            return _deserialize_superjson(json_value)

        # 递归处理嵌套对象
        return {k: _deserialize_superjson(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_deserialize_superjson(item) for item in obj]

    return obj


class TRPCClient:
    """tRPC HTTP 客户端

    封装对 redroomcn tRPC API 的低层 HTTP 请求。
    使用与 @trpc/client httpBatchLink 相同的请求格式。

    Usage:
        client = TRPCClient("http://localhost:3000")
        agencies = client.query("agencies.list", {"limit": 10})
        articles = client.query("articles.list", {"region": "MENA", "limit": 20})
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        http_client: Optional[HTTPClient] = None,
    ):
        """
        Args:
            base_url: redroomcn 服务的基 URL
            http_client: 共享的 HTTPClient 实例，None 则创建新实例
        """
        self.base_url = base_url.rstrip("/")
        if http_client is not None:
            self.http = http_client
            self._owns_client = False
        else:
            self.http = HTTPClient(timeout=30.0, max_retries=2)
            self._owns_client = True
        self.logger = logger.bind(module="TRPCClient")

    def query(self, procedure: str, input_data: Optional[dict] = None) -> Any:
        """调用 tRPC 查询过程（GET 请求）。

        使用 httpBatchLink 兼容格式：
        GET /api/trpc/{procedure}?batch=1&input={superjson_encoded_batch}

        Args:
            procedure: 过程路径，如 "agencies.list", "articles.list"
            input_data: 过程输入参数，None 则用空对象

        Returns:
            反序列化后的响应数据

        Raises:
            TRPCError: tRPC 协议错误
            httpx.HTTPError: HTTP 传输错误
        """
        url = self._build_query_url(procedure, input_data or {})
        self.logger.debug(f"tRPC query: GET {url}")

        response = self.http.get(url)
        body = response.json()

        return self._parse_response(body, procedure)

    def health_check(self) -> bool:
        """检查 redroomcn 服务是否可达。

        Returns:
            True 如果 /healthz 返回 200
        """
        try:
            url = f"{self.base_url}/healthz"
            response = self.http.get(url)
            return response.status_code == 200
        except Exception:
            return False

    def _build_query_url(self, procedure: str, input_data: dict) -> str:
        """构造 tRPC 查询 URL。

        遵循 tRPC v11 httpBatchLink 格式：
        - 始终使用 batch=1（单查询也走批处理路径）
        - 输入用 superjson 包装：{"0": {"json": <input_data>}}
        - 整体 JSON 字符串作为 input 查询参数

        示例：
            GET /api/trpc/agencies.list?batch=1&input=%7B%220%22%3A%7B%22json%22%3A%7B%22limit%22%3A2%7D%7D%7D
        """
        # superjson 序列化输入
        superjson_input = _serialize_input(input_data)

        # 批处理索引包装：{"0": superjson_encoded_input}
        batch_input = {"0": superjson_input}

        # 序列化并 URL 编码
        input_json = json.dumps(batch_input, separators=(",", ":"), ensure_ascii=False)
        input_encoded = quote(input_json, safe="")

        return (
            f"{self.base_url}/api/trpc/{procedure}"
            f"?batch=1&input={input_encoded}"
        )

    def _parse_response(self, body: Any, procedure: str) -> Any:
        """解析 tRPC 批处理响应信封。

        httpBatchLink 响应格式（批量数组）：
            [{"result": {"data": ...}}, ...]
        或错误：
            [{"error": {...}}, ...]

        注：单个查询也走批处理路径，响应是单元素数组。
        """
        # 批处理响应总是数组格式
        if isinstance(body, list):
            if len(body) == 0:
                return []

            # 单查询批处理：取第一个元素
            item = body[0]

            # 成功响应：{"result": {"data": ...}}
            if "result" in item and isinstance(item["result"], dict):
                result = item["result"]
                # 数据可能在 data 字段中，也可能直接是 result
                if "data" in result:
                    data = result["data"]
                else:
                    data = result
                if data is not None:
                    return _deserialize_superjson(data)
                return None

            # 错误响应
            if "error" in item:
                err = item["error"]
                # tRPC v11 错误嵌套在 json 字段中
                if isinstance(err, dict) and "json" in err:
                    err = err["json"]
                raise TRPCError(
                    message=err.get("message", "Unknown error"),
                    code=err.get("code", "UNKNOWN"),
                )

        # 非标准格式：直接反序列化返回
        return _deserialize_superjson(body)

    def close(self):
        """关闭 HTTP 客户端（仅在自建客户端时）。"""
        if self._owns_client:
            try:
                self.http.close()
            except Exception:
                pass

    def __repr__(self):
        return f"TRPCClient(base_url={self.base_url!r})"
