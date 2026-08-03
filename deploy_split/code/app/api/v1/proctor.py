"""路由层（API）

定义所有 HTTP 接口。这里只管"收请求、调 service、返响应"，
不写业务逻辑（业务逻辑在 services 层）。

提供三个接口：/test、/ping、/upload_face，
所有业务接口统一返回 {code, message, data}。
"""
from typing import Optional

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.schemas.proctor import ApiResponse, PingResponse
from app.services import proctor_service

router = APIRouter()


@router.get("/test", response_model=ApiResponse)
def test(
    max_left_angle: Optional[float] = Query(None, description="左右角 > 该值→向左看，不传用默认 6"),
    max_right_angle: Optional[float] = Query(None, description="左右角 < 该值→向右看，不传用默认 -6"),
    max_up_angle: Optional[float] = Query(None, description="上下角 > 该值→向上看，不传用默认 6"),
    max_down_angle: Optional[float] = Query(None, description="上下角 < 该值→向下看，不传用默认 -1"),
):
    """测试人脸识别（使用内置测试图片）。

    4 个面部角度阈值均为可选：不传任何参数时行为与改造前完全一致。
    """
    return proctor_service.analyze_test_image(
        max_left_angle=max_left_angle,
        max_right_angle=max_right_angle,
        max_up_angle=max_up_angle,
        max_down_angle=max_down_angle,
    )


@router.get("/ping", response_model=PingResponse)
def ping():
    """健康检查（含模型池就绪状态）"""
    return PingResponse(**proctor_service.pool_status())


@router.post("/upload_face", response_model=ApiResponse)
async def upload_face(
    file: UploadFile = File(...),
    max_left_angle: Optional[float] = Form(None, description="左右角 > 该值→向左看，不传用默认 6"),
    max_right_angle: Optional[float] = Form(None, description="左右角 < 该值→向右看，不传用默认 -6"),
    max_up_angle: Optional[float] = Form(None, description="上下角 > 该值→向上看，不传用默认 6"),
    max_down_angle: Optional[float] = Form(None, description="上下角 < 该值→向下看，不传用默认 -1"),
):
    """上传图片识别监考动作。

    4 个面部角度阈值均为可选：不传任何参数时行为与改造前完全一致。
    """
    return await proctor_service.analyze_uploaded_face(
        file,
        max_left_angle=max_left_angle,
        max_right_angle=max_right_angle,
        max_up_angle=max_up_angle,
        max_down_angle=max_down_angle,
    )
