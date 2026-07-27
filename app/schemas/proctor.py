"""数据模型模块（Schemas）

定义接口的请求体和响应体结构。所有接口返回统一格式：
    {"code": 200, "message": "success", "data": ...}

参考大厂后台规范：code 复用 HTTP 状态码语义（200 成功，4xx 客户端错误，5xx 服务端错误）。
这样前端不用猜每个接口返回什么格式，统一按 code 判断成功/失败。
"""
from enum import Enum, IntEnum
from typing import Any, Optional

from pydantic import BaseModel


class StatusCode(IntEnum):
    """业务状态码（复用 HTTP 状态码语义）。

    约定：200 表示成功，4xx 表示客户端/输入相关错误，5xx 表示服务端错误。
    """

    SUCCESS = 200
    BAD_REQUEST = 400          # 文件类型不支持 / 文件为空 / 图片无法解析
    NOT_FOUND = 404            # 资源不存在（如测试图片缺失）
    PAYLOAD_TOO_LARGE = 413    # 上传文件超过大小限制
    INTERNAL_ERROR = 500       # 服务内部错误


class ActionType(str, Enum):
    """检测出的动作类型（机器可读，前端据此做展示/统计）。"""

    NORMAL = "normal"            # 正常考试
    GAZE_AWAY = "gaze_away"      # 视线偏移
    LEAVE_SEAT = "leave_seat"    # 离开座位
    TURN_HEAD = "turn_head"      # 转头
    TURN_BODY = "turn_body"      # 转身
    PHONE_CALL = "phone_call"    # 疑似打电话
    STRETCH_ARM = "stretch_arm"  # 伸展胳膊
    MULTI_PERSON = "multi_person"  # 多人出现


class DetectionData(BaseModel):
    """单张图片的结构化检测结果（放在统一响应体的 data 字段里）。

    颜色等展示信息不进入 API，由前端根据 action_type/warning 自行决定。
    """

    warning: bool = False              # 是否命中违规
    action_type: ActionType = ActionType.NORMAL
    action_label: str = "正常考试中"    # 中文可读描述
    warning_count: int = 0             # 累计告警次数
    person_count: int = 1              # 检测到的人数


class ApiResponse(BaseModel):
    """统一响应格式。code=200 表示成功，非 200 表示业务错误。"""

    code: int = StatusCode.SUCCESS
    message: str = "success"
    data: Optional[Any] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        """构造成功响应。"""
        return cls(code=StatusCode.SUCCESS, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str, data: Any = None) -> "ApiResponse":
        """构造错误响应。"""
        return cls(code=code, message=message, data=data)


class PingResponse(BaseModel):
    """健康检查响应。"""

    pong: bool = True
    message: str = "server is alive"
