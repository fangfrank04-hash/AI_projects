"""
MCP Client — Agent 通过此模块连接独立 MCP HTTP 服务
使用 MCP Streamable HTTP 协议 (JSON-RPC over SSE)

架构:
  Agent工具函数 → MCPClient.call_tool() → HTTP POST → MCP Server (port 8001)

参考: MCP 2025-06-18 Streamable HTTP 规范
"""
import json
import ast
import httpx
from config import Config


class MCPClientError(Exception):
    """MCP 调用异常"""

    def __init__(self, message: str, code: int = -1):
        self.message = message
        self.code = code
        super().__init__(message)


class MCPClient:
    """
    MCP Streamable HTTP 客户端
    封装会话初始化 (initialize → initialized) 和工具调用 (tools/call)
    """

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or Config.MCP_SERVER_URL).rstrip("/")
        self.session_id: str | None = None
        self._request_id = 0
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    @property
    def _headers(self) -> dict:
        """构建请求头（含 Accept 和可选的 Session ID）"""
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))

    async def _ensure_initialized(self):
        """确保 MCP 会话已初始化"""
        if self._initialized:
            return
        await self._ensure_client()

        # Step 1: 发送 initialize 请求（不带 Session ID）
        init_result = await self._send_request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "proposal-ai-agent", "version": "2.0.0"}
        }, include_session=False)

        # Step 2: 发送 initialized 通知（带 Session ID）
        await self._send_notification("notifications/initialized", {})

        self._initialized = True
        print(f"[MCPClient] Session initialized ({self.session_id[:12]}...)")

    async def _send_request(self, method: str, params: dict, include_session: bool = True) -> dict:
        """发送 JSON-RPC 请求，解析 SSE/JSON 响应"""
        self._request_id += 1
        body = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id
        }
        headers = self._headers.copy()
        if not include_session:
            headers.pop("Mcp-Session-Id", None)

        response = await self._client.post(self.base_url, json=body, headers=headers)

        # 记录服务器返回的 session id
        sid = response.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid

        if response.status_code == 204:
            return {}

        # 解析响应：可能是 JSON 或 SSE (text/event-stream)
        content_type = response.headers.get("content-type", "")
        text = response.text

        if "text/event-stream" in content_type or text.startswith("event:"):
            return self._parse_sse_response(text)

        try:
            result = response.json()
        except Exception:
            raise MCPClientError(f"Invalid JSON response: {text[:300]}")

        if "error" in result:
            err = result["error"]
            raise MCPClientError(err.get("message", str(err)), err.get("code", -1))

        return result.get("result", result)

    def _parse_sse_response(self, text: str) -> dict:
        """解析 SSE 格式响应: event: message\ndata: <json>\n\n"""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError:
                    return {"_raw": data_str}

                if "error" in payload:
                    err = payload["error"]
                    raise MCPClientError(err.get("message", str(err)), err.get("code", -1))
                return payload.get("result", payload)
        return {"_raw": text}

    async def _send_notification(self, method: str, params: dict):
        """发送 JSON-RPC 通知（无 id 字段，无响应体）"""
        body = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        try:
            await self._client.post(self.base_url, json=body, headers=self._headers)
        except Exception:
            pass

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        调用 MCP 工具

        :param tool_name: 工具名称（如 get_project_info）
        :param arguments: 工具参数字典
        :return: 工具返回结果（已解析为 dict）
        """
        await self._ensure_initialized()

        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

        # MCP tools/call 返回: {"content": [{"type": "text", "text": "..."}]}
        content = result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            return self._parse_tool_text(text)

        return result

    @staticmethod
    def _parse_tool_text(text: str) -> dict:
        """解析工具返回的文本为 dict（处理 Python repr 格式）"""
        if not text:
            return {}
        # 尝试各种解析方式
        for parser in [
            lambda s: json.loads(s),                          # 纯 JSON
            lambda s: json.loads(s.replace("'", '"')),        # 单引号 → 双引号
            lambda s: ast.literal_eval(s),                     # Python literal
        ]:
            try:
                result = parser(text)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError, SyntaxError):
                continue
        return {"_raw": text}

    async def close(self):
        """关闭客户端，释放会话"""
        if self._client:
            try:
                await self._send_notification("session/close", {})
            except Exception:
                pass
            await self._client.aclose()
            self._client = None
            self._initialized = False
            self.session_id = None


# 全局单例（Agent 复用同一会话）
_mcp_client: MCPClient | None = None


async def get_mcp_client() -> MCPClient:
    """获取全局 MCP 客户端单例"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """快捷方法：调用 MCP 工具"""
    client = await get_mcp_client()
    return await client.call_tool(tool_name, arguments)


async def close_mcp_client():
    """关闭全局 MCP 客户端"""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None
