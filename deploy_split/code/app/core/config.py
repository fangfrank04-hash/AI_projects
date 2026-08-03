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
    """全局配置。所有默认值与代码中的标定值一致，保证行为稳定。"""

    # ===== 服务配置 =====
    app_name: str = _get_str("APP_NAME", "AiProctor 智能监考")
    app_description: str = _get_str("APP_DESCRIPTION", "AI智能体中心API服务")
    app_version: str = _get_str("APP_VERSION", "1.0.0")
    host: str = _get_str("HOST", "0.0.0.0")
    port: int = _get_int("PORT", 8000)
    # 日志级别（DEBUG/INFO/WARNING/ERROR）
    log_level: str = _get_str("LOG_LEVEL", "INFO")

    # ===== 路径配置 =====
    # 字体文件
    font_path: str = str(BASE_DIR / "assets" / "fonts" / "YeZiGongChangAoYeHei-2.ttf")
    # 测试图片目录
    test_images_dir: str = str(BASE_DIR / "assets" / "test_images")
    # 模型文件
    yolo_model_path: str = str(BASE_DIR / "models" / "weights" / "yolo11n.pt")
    face_landmarker_path: str = str(BASE_DIR / "models" / "face_landmarker.task")
    # 多人兜底用的姿态模型（MediaPipe Tasks PoseLandmarker，检测“身体”补人脸漏检的背影/边缘人）
    pose_landmarker_path: str = str(BASE_DIR / "models" / "pose_landmarker_lite.task")

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

    # ===== 多人姿态兜底（PoseLandmarker）=====
    # 检测置信度 0.2 是标定甜点：多人检出率最高且正常单人图 0 误判（0.1 会让正常图大量误判）。
    multi_person_pose_confidence: float = _get_float("MULTI_PERSON_POSE_CONFIDENCE", 0.2)
    multi_person_max_poses: int = _get_int("MULTI_PERSON_MAX_POSES", 3)
    # 两个身体的水平间距（肩中点 x，归一化）≥此值才算多人：
    # 真·多人左右分开（≥0.19），单人被误拆成两个时两体重叠（≤0.08），0.15 在空隙中。
    multi_person_min_separation: float = _get_float("MULTI_PERSON_MIN_SEPARATION", 0.15)

    # ===== 并发模型池 =====
    # 单进程内预创建几个识别器实例，让多请求真正并行（MediaPipe 推理释放 GIL）。
    # 默认 2：4核机器稳健值；内存充足可调大（每实例约 300~500MB）。部署时用环境变量 PROCTOR_POOL_SIZE 调。
    proctor_pool_size: int = _get_int("PROCTOR_POOL_SIZE", 2)


settings = Settings()
