"""
SSE消息格式化工具
"""
import json


def format_sse(event: str, data: dict) -> str:
    """将事件和数据格式化为SSE消息格式"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_event(event_type: str, payload: dict) -> dict:
    """创建标准SSE事件对象"""
    return {
        "event": event_type,
        "data": payload
    }
