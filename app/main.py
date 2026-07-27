"""FastAPI 应用入口

这里负责"组装"：创建 app 实例、注册路由、启动服务。
业务逻辑在 services 层，AI 模型在 ml 层。

启动方式（在项目根目录执行）：
    uv run python -m app.main
    或
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import asyncio

import uvicorn
from fastapi import FastAPI

from app.api.v1 import proctor
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.offline_docs import setup_offline_docs

# 初始化日志（尽早，保证后续模块都能拿到配置好的 logger）
setup_logging()

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    docs_url=None,       # 禁用默认 docs（从CDN加载），改用离线版
    redoc_url=None,      # 禁用默认 redoc（也从CDN加载）
)

# 配置离线 Swagger UI（内网也能访问 /docs 调试页面）
setup_offline_docs(app)

# 注册全局异常处理器（统一返回 {code, message, data}）
register_exception_handlers(app)

# 注册路由（标准 FastAPI APIRouter 写法）
app.include_router(proctor.router)


if __name__ == "__main__":
    # Windows Git Bash 下 uvicorn.run() 有兼容性问题，用 asyncio 方式启动
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
