"""
SSE消息格式化工具
"""
import json


def format_sse(data: dict) -> str:
    """将数据格式化为SSE消息格式（type 字段放在 data 内部）"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
