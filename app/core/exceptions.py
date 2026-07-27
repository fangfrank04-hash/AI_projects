"""全局异常处理

把未捕获的异常、参数校验错误统一包装成 {code, message, data} 响应体，
避免直接把 500 堆栈或 FastAPI 默认的校验错误结构暴露给前端。

用法（在 main.py 里调用）：
    from app.core.exceptions import register_exception_handlers
    register_exception_handlers(app)
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.proctor import ApiResponse, StatusCode

logger = logging.getLogger(__name__)


class AppException(Exception):
    """业务异常：service 层可主动抛出，携带业务码与提示信息。"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException):
        body = ApiResponse.error(code=exc.code, message=exc.message)
        return JSONResponse(status_code=200, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):
        body = ApiResponse.error(
            code=StatusCode.BAD_REQUEST,
            message="请求参数校验失败",
            data=exc.errors(),
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(Exception)
    async def _handle_uncaught_exception(request: Request, exc: Exception):
        logger.exception("未捕获的异常: %s %s", request.method, request.url.path)
        body = ApiResponse.error(
            code=StatusCode.INTERNAL_ERROR,
            message="服务内部错误",
        )
        return JSONResponse(status_code=500, content=body.model_dump())
