"""
Java HTTP Client 封装
统一调用 Java 后台的 RestAction.invoke.do 接口
"""
import json
import httpx
from typing import Any, Dict

from mcp_server.config import JAVA_BASE_URL, REQUEST_TIMEOUT, get_cookie, clear_cookie


class JavaClientError(Exception):
    """Java 调用异常，可转换为 MCP ErrorData"""

    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "data": {"source": "java_client", "detail": self.detail},
        }


class JavaHttpClient:
    """封装对 Java 后台的 HTTP 调用"""

    def __init__(self, base_url: str = JAVA_BASE_URL, timeout: float = REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        # 如果 base_url 本身已包含 RestAction 路径，不要重复拼接
        if "RestAction" in self.base_url:
            self.invoke_url = self.base_url
        else:
            self.invoke_url = f"{self.base_url}/portal/RestAction.invoke.do"
        self.timeout = httpx.Timeout(timeout, read=30.0, write=10.0, pool=5.0)

        # 不固定 headers，每次请求动态获取 Cookie
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def call(self, service_path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一调用 Java 接口（参数包装在 params 字段中）

        :param service_path: Java 服务路径，如 /itmp/pmProjectService/findProjectById
        :param params: 请求参数 dict，会被序列化为 JSON 字符串后作为 params= 发送
        :return: Java 返回的 JSON 数据
        """
        query_params = {"url": service_path}
        data = {"params": json.dumps(params, ensure_ascii=False)}

        print(f"[JavaClient] POST {self.invoke_url}?url={service_path}")
        print(f"[JavaClient] data: params={data['params'][:200]}")

        # 动态设置 Cookie
        cookie = get_cookie()
        if cookie:
            self.client.headers["Cookie"] = cookie
        elif "Cookie" in self.client.headers:
            del self.client.headers["Cookie"]

        response = await self.client.post(
            self.invoke_url, params=query_params, data=data
        )

        # 检测 401 → 清缓存抛异常
        if response.status_code == 401:
            clear_cookie()
            raise JavaClientError(
                code=401,
                message="Java 认证已过期，Cookie 已清空，等待 Java 重新推送",
                detail="HTTP 401 Unauthorized"
            )

        response.raise_for_status()

        text = response.text
        print(f"[JavaClient] response({response.status_code}): {text[:300]}")
        try:
            result = json.loads(text)
            # 如果 result 本身是字符串（双重 JSON 编码），再解析一次
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except json.JSONDecodeError:
            return {"raw": text}

    async def call_direct(self, service_path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        直接发送 form 数据（不包装在 params 中），适用于需要顶层字段的接口
        如 updatePmProject 需要 pmProject 作为顶层 form 字段

        :param service_path: Java 服务路径
        :param data: 顶层 form 字段 dict，值若为 dict 会自动 json.dumps
        :return: Java 返回的 JSON 数据
        """
        query_params = {"url": service_path}
        # 将 dict 值序列化为 JSON 字符串
        form_data = {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v
            for k, v in data.items()
        }
        print(f"[JavaClient] call_direct → {service_path}")
        print(f"[JavaClient] form keys: {list(form_data.keys())}, pmProject length: {len(form_data.get('pmProject', ''))}")

        # 动态设置 Cookie
        cookie = get_cookie()
        if cookie:
            self.client.headers["Cookie"] = cookie
        elif "Cookie" in self.client.headers:
            del self.client.headers["Cookie"]

        response = await self.client.post(
            self.invoke_url, params=query_params, data=form_data
        )

        # 检测 401 → 清缓存抛异常
        if response.status_code == 401:
            clear_cookie()
            raise JavaClientError(
                code=401,
                message="Java 认证已过期，Cookie 已清空，等待 Java 重新推送",
                detail="HTTP 401 Unauthorized"
            )

        response.raise_for_status()

        text = response.text
        try:
            result = json.loads(text)
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except json.JSONDecodeError:
            return {"raw": text}

    async def safe_call(self, service_path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        带异常处理的 Java 接口调用

        :raises JavaClientError: 网络异常、HTTP 异常、超时等
        """
        try:
            return await self.call(service_path, params)
        except JavaClientError:
            # 直接往上抛，让调用方感知到认证过期等问题
            raise
        except httpx.TimeoutException as e:
            raise JavaClientError(
                code=-32000,
                message="Java service timeout",
                detail=f"Request to {service_path} timed out: {e}",
            )
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 404:
                raise JavaClientError(
                    code=-32602,
                    message="Java interface not found",
                    detail=f"{service_path} returned 404",
                )
            elif status >= 500:
                raise JavaClientError(
                    code=-32603,
                    message="Java internal error",
                    detail=f"{service_path} returned {status}",
                )
            raise JavaClientError(
                code=-32001,
                message="Java service unavailable",
                detail=f"{service_path} returned {status}",
            )
        except httpx.RequestError as e:
            raise JavaClientError(
                code=-32001,
                message="Java service unreachable",
                detail=str(e),
            )
        except Exception as e:
            raise JavaClientError(
                code=-32002,
                message=f"Java client unexpected error: {str(e)}",
                detail=str(e),
            )

    async def close(self):
        await self.client.aclose()
