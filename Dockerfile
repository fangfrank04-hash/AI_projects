# ============ 阶段 1：builder —— 只负责装依赖，产物是 /app/.venv ============
# 基础镜像与内网 Python 版本严格一致（3.12.9）
FROM python:3.12.9 AS builder

# 钉死 uv 版本（与本地开发一致），保证构建可复现；latest 会漂移导致"莫名失败"
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

# 构建期编译字节码：换取容器启动更快（uv 官方推荐，FastAPI 官方模板同款）
ENV UV_COMPILE_BYTECODE=1
# 跨文件系统 COPY 到最终镜像时用 copy 模式，避免硬链接问题
ENV UV_LINK_MODE=copy

WORKDIR /app

# 国内构建提速/避坑：Debian 源换阿里云镜像（只影响构建时下载，不影响运行）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 先只复制依赖清单（这一层缓存稳定，不改依赖就不重装）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ============ 阶段 2：runtime —— 最终镜像，不含 uv/构建缓存 ============
FROM python:3.12.9-slim AS runtime

# 日志不缓冲：docker logs 实时可见（生产排查必备）
ENV PYTHONUNBUFFERED=1

# slim 基础镜像同样需要 OpenCV/MediaPipe 的系统图形库
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    # 非 root 运行（安全基线）：创建专用用户
    && useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# 从 builder 拷贝装好的虚拟环境（路径保持一致，venv 内解释器引用才有效）
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# 复制业务代码与资源
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser assets ./assets
COPY --chown=appuser:appuser models ./models

USER appuser

EXPOSE 8000
# 直接用 venv 启动（不经 uv，内网离线可跑）；生产建议 --workers 2~3（见 高并发部署指南）
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
