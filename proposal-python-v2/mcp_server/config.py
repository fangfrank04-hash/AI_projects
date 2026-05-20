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

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
