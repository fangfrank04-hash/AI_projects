"""Validated runtime configuration loaded from environment variables and `.env`."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application and recognition settings.

    Process environment variables override values in the project-root `.env` file.
    Invalid values fail during startup instead of silently reaching recognition code.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service
    app_name: str = "AiProctor 智能监考"
    app_description: str = "AI智能体中心API服务"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Paths
    font_path: str = str(BASE_DIR / "assets" / "fonts" / "YeZiGongChangAoYeHei-2.ttf")
    test_images_dir: str = str(BASE_DIR / "assets" / "test_images")
    yolo_model_path: str = str(BASE_DIR / "models" / "weights" / "yolo11n.pt")
    face_landmarker_path: str = str(BASE_DIR / "models" / "face_landmarker.task")
    pose_landmarker_path: str = str(BASE_DIR / "models" / "pose_landmarker_lite.task")

    # Face direction
    max_left_angle: float = 6
    max_right_angle: float = -6
    max_up_angle: float = 6
    max_down_angle: float = -1

    # Phone and pose actions. Defaults match the values previously used by ImageProctor.
    phone_wrist_ear_dist: float = Field(default=0.55, ge=0)
    phone_arm_angle: float = Field(default=30, ge=0, le=180)
    stretch_arm_angle: float = Field(default=140, ge=0, le=180)
    horizontal_stretch_arm_angle: float = Field(default=155, ge=0, le=180)
    horizontal_stretch_visibility: float = Field(default=0.4, ge=0, le=1)
    horizontal_stretch_arm_length: float = Field(default=1.05, ge=0)
    horizontal_stretch_wrist_ear_dist: float = Field(default=1.6, ge=0)
    elbow_stretch_visibility: float = Field(default=0.25, ge=0, le=1)
    elbow_stretch_max_dy: float = Field(default=0.5, ge=0)
    elbow_stretch_min_reach: float = Field(default=0.7, ge=0)
    turn_body_shoulder_dist: float = Field(default=0.25, ge=0)
    seated_turn_max_hip_visibility: float = Field(default=0.05, ge=0, le=1)
    visibility_threshold: float = Field(default=0.5, ge=0, le=1)

    # Multi-person fallback
    multi_person_pose_confidence: float = Field(default=0.2, ge=0, le=1)
    multi_person_max_poses: int = Field(default=3, ge=1)
    multi_person_min_separation: float = Field(default=0.15, ge=0, le=1)

    # Concurrency
    proctor_pool_size: int = Field(default=2, ge=1)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value):
        return value.upper() if isinstance(value, str) else value


settings = Settings()
