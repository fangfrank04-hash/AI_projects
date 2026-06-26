@echo off
chcp 65001 >nul
echo ========================================
echo 项目方案书AI助手 - Python主导版 v2.0
echo ========================================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 python，请先安装 Python 3.10+
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装依赖...
pip install -r requirements.txt

REM 启动MCP数据服务（独立进程，端口8001）
echo [2/3] 启动MCP数据服务 (端口8001)...
start "MCP-Data-Service" cmd /c "python -m mcp_server.http_server"

REM 等待MCP服务就绪
timeout /t 3 /nobreak >nul

REM 启动FastAPI主服务（端口8000）
echo [3/3] 启动FastAPI主服务 (端口8000)...
echo.
echo 服务启动后，请访问:
echo   API文档: http://localhost:8000/docs
echo   MCP服务: http://127.0.0.1:8001/mcp
echo   前端连接: http://localhost:5173
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
