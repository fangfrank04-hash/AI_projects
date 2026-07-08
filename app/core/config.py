"""配置管理模块

集中管理所有配置项。阈值、端口、路径等不再硬编码在代码里，
而是从 .env 文件或环境变量读取。改配置不用动代码。

用法：
    from app.core.config import settings
    print(settings.max_left_angle)
"""
import os
from pathlib import Path

# 项目根目录（app/core/config.py 往上两级 = 项目根）
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _get_int(key: str, default: int) -> int:
    """从环境变量读取整数，读不到用默认值"""
    val = os.getenv(key)
    return int(val) if val is not None else default


def _get_float(key: str, default: float) -> float:
    """从环境变量读取浮点数，读不到用默认值"""
    val = os.getenv(key)
    return float(val) if val is not None else default


def _get_str(key: str, default: str) -> str:
    """从环境变量读取字符串，读不到用默认值"""
    return os.getenv(key, default)


class Settings:
    """全局配置。所有默认值与重构前硬编码的值完全一致，保证行为不变。"""

    # ===== 服务配置 =====
    app_name: str = _get_str("APP_NAME", "AiProctor 智能监考")
    app_description: str = _get_str("APP_DESCRIPTION", "AI智能体中心API服务")
    app_version: str = _get_str("APP_VERSION", "1.0.0")
    host: str = _get_str("HOST", "0.0.0.0")
    port: int = _get_int("PORT", 8000)

    # ===== 路径配置 =====
    # 字体文件
    font_path: str = str(BASE_DIR / "assets" / "fonts" / "YeZiGongChangAoYeHei-2.ttf")
    # 测试图片目录
    test_images_dir: str = str(BASE_DIR / "assets" / "test_images")
    # 模型文件
    yolo_model_path: str = str(BASE_DIR / "models" / "weights" / "yolo11n.pt")
    face_landmarker_path: str = str(BASE_DIR / "models" / "face_landmarker.task")

    # ===== 人脸角度阈值（与原 ImageProctor.__init__ 完全一致）=====
    max_left_angle: int = _get_int("MAX_LEFT_ANGLE", 6)
    max_right_angle: int = _get_int("MAX_RIGHT_ANGLE", -6)
    max_up_angle: int = _get_int("MAX_UP_ANGLE", 6)
    max_down_angle: int = _get_int("MAX_DOWN_ANGLE", -1)

    # ===== Pose 动作检测阈值（与原 ImageProctor.__init__ 完全一致）=====
    phone_wrist_ear_dist: float = _get_float("PHONE_WRIST_EAR_DIST", 0.35)
    phone_wrist_ear_y_diff: float = _get_float("PHONE_WRIST_EAR_Y_DIFF", 0.25)
    stand_torso_height: float = _get_float("STAND_TORSO_HEIGHT", 1.20)
    stand_shoulder_dist: float = _get_float("STAND_SHOULDER_DIST", 0.48)
    stand_shoulder_y: float = _get_float("STAND_SHOULDER_Y", 0.5)
    stretch_arm_angle: float = _get_float("STRETCH_ARM_ANGLE", 150)
    turn_body_shoulder_dist: float = _get_float("TURN_BODY_SHOULDER_DIST", 0.25)
    visibility_threshold: float = _get_float("VISIBILITY_THRESHOLD", 0.5)


settings = Settings()
