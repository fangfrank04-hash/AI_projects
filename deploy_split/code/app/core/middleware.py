"""请求日志中间件

记录每个 HTTP 请求的方法、路径、状态码、耗时，便于生产环境排查问题
（哪个请求慢、哪个报错，docker logs 里一目了然）。
"""
import logging
import time

from fastapi import FastAPI, Request

logger = logging.getLogger("access")


def register_request_logging(app: FastAPI) -> None:
    """注册请求日志中间件。"""

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
