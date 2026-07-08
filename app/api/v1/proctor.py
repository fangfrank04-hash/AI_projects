"""路由层（API）

定义所有 HTTP 接口。这里只管"收请求、调 service、返响应"，
不写业务逻辑（业务逻辑在 services 层）。

注意：接口路径与重构前完全一致（/test, /ping, /upload_face），
保证现有调用方不用改。
"""
from fastapi import APIRouter, UploadFile, File

from app.schemas.proctor import ApiResponse, PingResponse
from app.services import proctor_service

router = APIRouter()


@router.get("/test")
def test():
    """测试人脸识别（使用内置测试图片）"""
    result = proctor_service.analyze_test_image()
    return result


@router.get("/ping")
def ping():
    """健康检查"""
    return {"pong": True, "msg": "server is alive"}


@router.post("/upload_face")
async def upload_face(file: UploadFile = File(...)):
    """上传图片识别人脸"""
    result = await proctor_service.analyze_uploaded_face(file)
    return result
