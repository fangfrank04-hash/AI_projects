FROM python:3.10.20

WORKDIR /app

# 1. 安装系统图形库（OpenCV/MediaPipe 依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装 uv（比 pip 快 10-100 倍，且能利用 lock 文件保证版本一致）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 3. 先复制依赖文件（这一层缓存稳定，不改动依赖就不用重装）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 4. 复制业务代码
COPY app ./app
COPY assets ./assets
COPY models ./models

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
