"""
Java HTTP Client 封装
统一调用 Java 后台的 RestAction.invoke.do 接口
"""
import json
import httpx
from typing import Any, Dict

from mcp_server.config import JAVA_BASE_URL, REQUEST_TIMEOUT


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
        self.invoke_url = f"{self.base_url}/portal/RestAction.invoke.do"
        self.timeout = httpx.Timeout(timeout, read=30.0, write=10.0, pool=5.0)
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def call(self, service_path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一调用 Java 接口

        :param service_path: Java 服务路径，如 /itmp/pmProjectService/findProjectById
        :param params: 请求参数 dict，会被序列化为 JSON 字符串后作为 param= 发送
        :return: Java 返回的 JSON 数据
        """
        query_params = {"url": service_path}
        data = {"param": json.dumps(params, ensure_ascii=False)}

        response = await self.client.post(
            self.invoke_url, params=query_params, data=data
        )
        response.raise_for_status()

        text = response.text
        try:
            result = json.loads(text)
            # 如果 result 本身是字符串（双重 JSON 编码），再解析一次
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
