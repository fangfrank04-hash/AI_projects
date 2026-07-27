@echo off
chcp 65001 >nul
title 项目方案书AI助手 - 一键启动

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   项目方案书AI助手 - 一键启动 v2.0   ║
echo  ╚══════════════════════════════════════╝
echo.
echo  将依次启动 3 个服务（每个在独立窗口运行）：
echo    1. MCP 数据服务     → 端口 8001
echo    2. FastAPI 主服务   → 端口 8000 (SSE)
echo    3. React 前端       → 端口 5173
echo.

REM ==== 1. MCP 数据服务 ====
echo [1/3] 启动 MCP 数据服务 (端口8001)...
start "MCP-8001" cmd /c "cd /d D:\AI_projects\zhongzhai_pro\project-proposal-ai\proposal-python-v2 && python -m mcp_server.http_server"

REM 等待 MCP 就绪
echo 等待 MCP 服务启动... (5秒)
timeout /t 5 /nobreak >nul

REM ==== 2. FastAPI 主服务 ====
echo [2/3] 启动 FastAPI 主服务 (端口8000)...
start "FastAPI-8000" cmd /c "cd /d D:\AI_projects\zhongzhai_pro\project-proposal-ai\proposal-python-v2 && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

REM 等待 FastAPI 就绪
echo 等待 FastAPI 服务启动... (8秒)
timeout /t 8 /nobreak >nul

REM ==== 3. React 前端 ====
echo [3/3] 启动 React 前端 (端口5173)...
start "React-5173" cmd /c "cd /d D:\AI_projects\zhongzhai_pro\project-proposal-ai\react-frontend && npx vite --host 0.0.0.0 --port 5173"

echo.
echo ╔═══════════════════════════════════════════════╗
echo ║  3 个服务已启动，各在独立 CMD 窗口中运行。  ║
echo ║                                             ║
echo ║  前端地址:  http://localhost:5173            ║
echo ║  API 文档:  http://localhost:8000/docs       ║
echo ║  健康检查:  http://localhost:8000/health     ║
echo ║                                             ║
echo ║  ⚠ 不要关闭这 3 个 CMD 窗口，否则服务停止  ║
echo ║  用完后分别关闭即可。                       ║
echo ╚═══════════════════════════════════════════════╝
echo.
pause
