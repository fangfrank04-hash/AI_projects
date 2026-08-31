"""业务编排层（Services）

负责协调 api 层和 ml 层之间的数据流转。
api 层只管"收请求、返响应"，具体的业务逻辑（读文件、转格式、调模型、异常处理）都在这里。
"""
import io
import logging
import os
import threading

import numpy as np
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.ml.image_proctor import FaceAngleThresholds, ProctorPool, ProctorResult
from app.schemas.proctor import ActionType, ApiResponse, DetectionData, StatusCode

logger = logging.getLogger(__name__)

# 上传图片大小上限（字节），默认 10MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
# 允许的图片 MIME 类型前缀
ALLOWED_CONTENT_PREFIX = "image/"
BLACK_SCREEN_EXCEPTION_CODE = 1001
BLACK_SCREEN_EXCEPTION_MESSAGE = "检测到黑屏"
BLACK_SCREEN_PIXEL_THRESHOLD = 16
BLACK_SCREEN_MIN_RATIO = 0.995
# 重复告警编码：同一用户同一种违规连续出现超过上报上限后，从第 4 次起返回该编码
REPEAT_EXCEPTION_CODE = 1002
REPEAT_EXCEPTION_MESSAGE = "重复告警"
# 同一用户同一种违规连续上报次数上限（第 4 次起视为重复，不再报错）
MAX_CONSECUTIVE_REPORTS = 3


def is_black_screen(image: Image.Image) -> bool:
    """判断截图是否几乎全黑，采用保守阈值避免把普通暗图误报为黑屏。"""
    grayscale = np.asarray(image.convert("L"), dtype=np.uint8)
    if grayscale.size == 0:
        return False
    near_black_ratio = float(
        np.count_nonzero(grayscale <= BLACK_SCREEN_PIXEL_THRESHOLD) / grayscale.size
    )
    return near_black_ratio >= BLACK_SCREEN_MIN_RATIO and float(grayscale.mean()) <= 16


class RepeatViolationState:
    """进程内连续违规去重状态（不依赖 Redis）。

    规则：同一用户同一种违规连续出现时，前 MAX_CONSECUTIVE_REPORTS 次正常上报，
    之后每次都标记为"重复"（由上游根据重复编码 1002 决定不再记为新报错）；
    出现不同违规类型或正常画面时，重新开始计数。
    """

    def __init__(self):
        # user_id -> (当前连续违规类型, 连续次数)
        self._states: dict[str, tuple[ActionType, int]] = {}
        self._lock = threading.Lock()

    def record(self, user_id: str, action_type: ActionType) -> bool:
        """记录一次违规，返回本次是否需要正常上报（False=已重复，仅返回重复编码）。"""
        with self._lock:
            current = self._states.get(user_id)
            if current and current[0] == action_type:
                count = current[1] + 1
            else:
                count = 1
            self._states[user_id] = (action_type, count)
            return count <= MAX_CONSECUTIVE_REPORTS

    def clear(self, user_id: str) -> None:
        """该用户出现正常画面（无违规）时清空连续计数。"""
        with self._lock:
            self._states.pop(user_id, None)

# 全局识别器池：预创建 N 个实例（模型只加载一次），多请求借不同实例真并行。
_proctor_pool = ProctorPool()
_repeat_violation_state = RepeatViolationState()


def pool_status() -> dict:
    """模型池就绪状态（供健康检查接口使用）。"""
    return {"pool_ready": _proctor_pool.size > 0, "pool_size": _proctor_pool.size}


def shutdown() -> None:
    """释放模型池资源（应用关闭时由 lifespan 调用）。"""
    _proctor_pool.close()
    logger.info("ProctorPool 已释放")


def _build_face_angles(
    max_left_angle: float | None = None,
    max_right_angle: float | None = None,
    max_up_angle: float | None = None,
    max_down_angle: float | None = None,
) -> FaceAngleThresholds | None:
    """把接口传来的 4 个可选角度参数组装成 FaceAngleThresholds。

    全部为 None（Java 未传任何参数）则返回 None，让 ml 层用默认值；
    只传了部分参数时，未传的字段自动用 dataclass 默认值。
    """
    overrides = {
        "max_left_angle": max_left_angle,
        "max_right_angle": max_right_angle,
        "max_up_angle": max_up_angle,
        "max_down_angle": max_down_angle,
    }
    provided = {k: v for k, v in overrides.items() if v is not None}
    if not provided:
        return None
    return FaceAngleThresholds(**provided)


def _to_detection_data(result: ProctorResult, user_id: str | None = None) -> DetectionData:
    """把 ml 层的 ProctorResult 映射为对外的结构化响应数据。"""
    return DetectionData(
        warning=result.warning,
        action_type=result.action_type,
        action_label=result.action_label,
        warning_count=result.warning_count,
        person_count=result.person_count,
        user_id=user_id,
    )


def _mark_repeat_status(data: DetectionData, user_id: str) -> None:
    """按"连续重复只报 3 次"规则刷新 data 的 exception_code/notify 字段。

    违规：前 3 次保留原编码、notify=True；第 4 次起编码改为重复(1002)、notify=False。
    正常：清空该用户的连续计数。
    """
    if not data.warning:
        _repeat_violation_state.clear(user_id)
        return
    should_report = _repeat_violation_state.record(user_id, data.action_type)
    data.notify = should_report
    if not should_report:
        data.exception_code = REPEAT_EXCEPTION_CODE
        data.exception_message = REPEAT_EXCEPTION_MESSAGE


def _black_screen_response(user_id: str) -> ApiResponse:
    data = DetectionData(
        user_id=user_id,
        warning=True,
        action_type=ActionType.BLACK_SCREEN,
        action_label=BLACK_SCREEN_EXCEPTION_MESSAGE,
        exception_code=BLACK_SCREEN_EXCEPTION_CODE,
        exception_message=BLACK_SCREEN_EXCEPTION_MESSAGE,
    )
    _mark_repeat_status(data, user_id)
    return ApiResponse.success(data=data, message="检测到黑屏！")


def analyze_test_image(
    max_left_angle: float | None = None,
    max_right_angle: float | None = None,
    max_up_angle: float | None = None,
    max_down_angle: float | None = None,
) -> ApiResponse:
    """分析内置测试图片（对应 GET /test 接口）。

    4 个面部角度阈值参数均可选：不传则用代码默认值。
    """
    test_image_path = os.path.join(settings.test_images_dir, "person2.jpg")
    if not os.path.exists(test_image_path):
        logger.warning("测试图片不存在: %s", test_image_path)
        return ApiResponse.error(
            code=StatusCode.NOT_FOUND,
            message=f"测试图片不存在（{test_image_path}），请放置一张人脸图片后重试",
        )

    face_angles = _build_face_angles(
        max_left_angle, max_right_angle, max_up_angle, max_down_angle
    )
    try:
        with Image.open(test_image_path) as image:
            result = _proctor_pool.analyze(image.convert("RGB"), face_angles=face_angles)
    except (UnidentifiedImageError, OSError) as exc:
        logger.exception("测试图片解析失败")
        return ApiResponse.error(
            code=StatusCode.INTERNAL_ERROR,
            message=f"测试图片解析失败: {exc}",
        )

    return ApiResponse.success(data=_to_detection_data(result), message="识别成功")


async def analyze_uploaded_face(
    file: UploadFile,
    user_id: str,
    max_left_angle: float | None = None,
    max_right_angle: float | None = None,
    max_up_angle: float | None = None,
    max_down_angle: float | None = None,
) -> ApiResponse:
    """分析上传的人脸图片（对应 POST /upload_face 接口）。

    4 个面部角度阈值参数均可选：不传则用代码默认值。
    """
    # 1. 校验用户标识和文件类型
    if not user_id.strip():
        return ApiResponse.error(
            code=StatusCode.BAD_REQUEST, message="user_id 不能为空"
        )
    if file.content_type and not file.content_type.startswith(ALLOWED_CONTENT_PREFIX):
        return ApiResponse.error(
            code=StatusCode.BAD_REQUEST,
            message=f"不支持的文件类型: {file.content_type}，请上传图片",
        )

    # 2. 读取二进制流并校验大小
    file_bytes = await file.read()
    if not file_bytes:
        return ApiResponse.error(code=StatusCode.BAD_REQUEST, message="上传文件为空")
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        return ApiResponse.error(
            code=StatusCode.PAYLOAD_TOO_LARGE,
            message=f"图片过大（>{MAX_UPLOAD_SIZE // (1024 * 1024)}MB）",
        )

    # 3. 解析为 PIL 图像并分析（上传接口是并发主力：把 CPU 密集的 analyze 丢到线程池，
    # 避免阻塞 async 事件循环；配合模型池实现多请求真并行）。
    face_angles = _build_face_angles(
        max_left_angle, max_right_angle, max_up_angle, max_down_angle
    )
    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            rgb_image = image.convert("RGB")
        if is_black_screen(rgb_image):
            return _black_screen_response(user_id)
        result = await run_in_threadpool(
            _proctor_pool.analyze, rgb_image, face_angles
        )
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning("上传图片解析失败: %s", exc)
        return ApiResponse.error(
            code=StatusCode.BAD_REQUEST,
            message="图片解析失败，请确认上传的是有效图片",
        )

    # 连续重复违规去重：同一用户同一种违规前 3 次正常报，第 4 次起返回重复编码 1002
    data = _to_detection_data(result, user_id=user_id)
    _mark_repeat_status(data, user_id)
    return ApiResponse.success(data=data, message="识别成功")
