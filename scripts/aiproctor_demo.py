"""前置/后置摄像头实时监考演示脚本

运行方式（在项目根目录执行）：
    uv run python scripts/aiproctor_demo.py
"""
from app.ml.front_camera import FrontCamera
from app.ml.back_camera import BackCamera


# 前置摄像头演示
stCamara = FrontCamera()

# 后置摄像头演示
# stCamara = BackCamera()

stCamara.Start(in_isShowMesh=False)
