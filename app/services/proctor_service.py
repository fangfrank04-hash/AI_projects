"""业务编排层（Services）

负责协调 api 层和 ml 层之间的数据流转。
api 层只管"收请求、返响应"，具体的业务逻辑（读文件、转格式、调模型）都在这里。

这样分层的好处：以后要加"图片大小限制""格式校验""日志记录"，
都加在这里，不会把 api 路由搞乱。
"""
import io
import os

from PIL import Image
from fastapi import UploadFile

from app.core.config import settings
from app.ml.image_proctor import ImageProctor


def analyze_test_image() -> dict:
    """
    分析内置测试图片（对应原 GET /test 接口）。

    返回值与原接口完全一致：
        {"code": 0, "msg": "识别成功", "data": [...]}
    或图片不存在时：
        {"code": -1, "msg": "测试图片不存在（...）", "data": None}
    """
    test_image_path = os.path.join(settings.test_images_dir, "person2.jpg")
    if not os.path.exists(test_image_path):
        return {
            "code": -1,
            "msg": f"测试图片不存在（{test_image_path}），请放置一张人脸图片后重试",
            "data": None,
        }

    proctor = ImageProctor()
    resource = proctor.GetImageFaceAngle(test_image_path)
    return {"code": 0, "msg": "识别成功", "data": resource}


async def analyze_uploaded_face(file: UploadFile) -> dict:
    """
    分析上传的人脸图片（对应原 POST /upload_face 接口）。

    返回值与原接口完全一致：
        {"code": 0, "msg": "识别成功", "data": [...]}
    """
    proctor = ImageProctor()

    # 1. 读取上传二进制流
    file_bytes = await file.read()
    # 2. 二进制流转 PIL 图像（适配内部处理逻辑）
    img_stream = io.BytesIO(file_bytes)
    pil_img = Image.open(img_stream)

    # 3. 调用 ImageProctor 分析
    resource = proctor.GetImageFaceAngleByImg(pil_img)
    return {"code": 0, "msg": "识别成功", "data": resource}
