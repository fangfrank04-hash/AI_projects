"""数据模型模块（Schemas）

定义接口的请求体和响应体结构。所有接口返回统一格式：
    {"code": 0, "msg": "success", "data": ...}

这样前端不用猜每个接口返回什么格式，统一处理。
"""
from typing import Any, Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一响应格式。与重构前 main.py 的返回格式完全一致。"""
    code: int = 0
    msg: str = "success"
    data: Optional[Any] = None


class PingResponse(BaseModel):
    """健康检查响应。与重构前 /ping 返回格式一致。"""
    pong: bool = True
    msg: str = "server is alive"
