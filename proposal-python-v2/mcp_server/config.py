"""
MCP Server 配置模块
通过环境变量控制运行参数
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件（从当前目录和父目录搜索）
load_dotenv()

# Java 服务地址
JAVA_BASE_URL = os.getenv("JAVA_SERVICE_URL", "http://localhost:8088")

# Mock 模式开关：true 时不调 Java，直接返回 mock 数据
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# MCP Server 监听配置
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")

# HTTP 请求超时（秒）
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "5.0"))

# Java 认证 Cookie（内网 SSO 登录后手动获取粘贴）
JAVA_COOKIE = os.getenv("JAVA_COOKIE", "")

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================================================
# Cookie 动态缓存（运行时通过 /api/auth/set-cookie 更新）
# 优先级：内存缓存 > .env 的 JAVA_COOKIE（降级兜底）
# ============================================================
_cookie_cache: str = ""


def set_cookie(cookie_str: str) -> None:
    """更新 Cookie 缓存（由 main.py 的 /api/auth/set-cookie 接口调用）"""
    global _cookie_cache
    _cookie_cache = cookie_str.strip()
    print(f"[Config] Cookie 已更新 (长度: {len(_cookie_cache)})")


def get_cookie() -> str:
    """
    获取当前有效的 Cookie
    优先级: 内存缓存 > .env JAVA_COOKIE（降级兜底）
    """
    global _cookie_cache
    cookie = _cookie_cache or JAVA_COOKIE
    if not cookie:
        print("[Config] 警告: Cookie 未设置，调 Java 可能失败")
    return cookie


def clear_cookie() -> None:
    """清空 Cookie 缓存（Java 返回 401 时调用）"""
    global _cookie_cache
    if _cookie_cache:
        print("[Config] Cookie 已清空（可能已过期）")
    _cookie_cache = ""
