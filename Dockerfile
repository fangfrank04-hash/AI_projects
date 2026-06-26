FROM python:3.10.20
WORKDIR /app

# 1. 先复制依赖、安装python包（这一层缓存稳定，不改动就不用重下）
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --no-cache-dir -r requirements.txt

RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --no-cache-dir python-multipart

# 2. 再安装系统图形库（只改动这里，只会重新执行apt，不会重下所有python包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制业务代码
COPY main.py .
COPY AiProctor ./AiProctor

EXPOSE 8000
CMD ["python", "main.py"]