"""
配置加载模块
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """应用配置"""
    # DashScope API Key
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

    # MCP Server配置（独立HTTP服务）
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")

    # LLM配置
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen-max")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # 开发模式
    DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

    @classmethod
    def validate(cls):
        """验证必要配置"""
        if not cls.DASHSCOPE_API_KEY:
            print("警告: DASHSCOPE_API_KEY 未设置，AI功能将不可用")
            return False
        return True
