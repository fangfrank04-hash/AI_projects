#!/bin/bash
# 启动脚本 - 同时启动MCP Server和FastAPI主服务

echo "========================================"
echo "项目方案书AI助手 - Python主导版 v2.0"
echo "========================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

# 安装依赖
echo "[1/3] 安装依赖..."
pip install -r requirements.txt

# 启动MCP Server（后台）
echo "[2/3] 启动MCP Server (端口8001)..."
cd mcp_server
python3 server.py &
MCP_PID=$!
cd ..

echo "MCP Server PID: $MCP_PID"

# 等待MCP Server启动
sleep 2

# 启动FastAPI主服务
echo "[3/3] 启动FastAPI主服务 (端口8000)..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 清理
echo "停止MCP Server..."
kill $MCP_PID 2>/dev/null
