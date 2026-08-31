#!/bin/sh
# ============================================================
# AiProctor 启动脚本（内网 Docker 容器内执行）
# 用法：被 Dockerfile 的 CMD 调用，或手动执行：
#   sh /app/AiProctor0623/entrypoint.sh
#
# 功能：
#   1. 打印环境信息（方便排查）
#   2. 用 venv 里的 uvicorn 启动 FastAPI
#   3. WORKERS 环境变量可覆盖进程数（默认 1）
# ============================================================

set -e

echo "=============================================="
echo "  AiProctor 启动中..."
echo "=============================================="
echo "  工作目录:   $(pwd)"
echo "  Python:     $(python --version 2>&1)"
echo "  Python路径: $(which python)"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  监听端口:   ${PORT:-8000}"
echo "  Worker数:   ${WORKERS:-1}"
echo "  日志级别:   ${LOG_LEVEL:-INFO}"
echo "=============================================="

# 进入项目目录
cd /app/AiProctor0623

# 启动服务（用 venv 内的 python，确保 import 都能找到）
# --workers 控制多进程数，服务器核多可以调大（如 2、4）
exec /opt/venv/bin/python -m uvicorn \
    app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers ${WORKERS:-1} \
    --log-level ${LOG_LEVEL:-INFO}
