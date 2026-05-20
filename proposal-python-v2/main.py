"""
FastAPI入口文件 - Python主导的AI项目助手服务
启动命令: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import asyncio
import json
import uuid
import os

from fastapi import FastAPI, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent_setup import ProjectAssistantAgent
from config import Config
from utils.sse_helper import format_sse

# 创建FastAPI应用
app = FastAPI(
    title="项目方案书AI助手 - Python主导版",
    description="基于agentscope + FastAPI的AI项目助手服务",
    version="2.0.0"
)

# CORS配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent池: session_id -> ProjectAssistantAgent
agent_pool: dict[str, ProjectAssistantAgent] = {}

# SSE心跳间隔（秒）
HEARTBEAT_INTERVAL = 30


class ChatMessageRequest(BaseModel):
    """发送消息请求体"""
    sessionId: str
    message: str


@app.get("/api/chat/stream")
async def chat_stream(
    projectId: str = Query(..., description="项目编号"),
    userName: str = Query(..., description="当前用户姓名"),
    isPM: bool = Query(False, description="是否项目经理")
):
    """
    SSE流式端点
    前端通过EventSource连接此端点，建立持久化SSE连接
    """
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()

    # 创建并初始化Agent
    agent = ProjectAssistantAgent(projectId, userName, isPM, queue)
    await agent.initialize()
    agent_pool[session_id] = agent

    print(f"[SSE] New connection: session_id={session_id}, project={projectId}, user={userName}, isPM={isPM}")

    async def event_generator():
        """SSE事件生成器"""
        # 发送connected事件
        yield format_sse("connected", {"sessionId": session_id, "status": "ok"})

        last_activity = asyncio.get_event_loop().time()

        while True:
            try:
                # 等待队列消息，带超时（用于心跳检测）
                msg = await asyncio.wait_for(queue.get(), timeout=5.0)

                if msg.get("event") == "close":
                    print(f"[SSE] Connection closed: session_id={session_id}")
                    break

                # 发送SSE事件
                yield format_sse(msg["event"], msg["data"])
                last_activity = asyncio.get_event_loop().time()

            except asyncio.TimeoutError:
                # 检查是否需要发送心跳
                now = asyncio.get_event_loop().time()
                if now - last_activity >= HEARTBEAT_INTERVAL:
                    yield format_sse("ping", {"time": int(now)})
                    last_activity = now

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/chat/message")
async def chat_message(request: ChatMessageRequest, background_tasks: BackgroundTasks):
    """
    接收用户指令
    前端通过POST发送用户消息，由Agent处理并通过SSE返回结果
    """
    session_id = request.sessionId
    message = request.message

    agent = agent_pool.get(session_id)
    if not agent:
        return {"error": "会话不存在或已过期，请刷新页面重新连接", "code": "SESSION_NOT_FOUND"}

    print(f"[API] Received message: session={session_id}, message={message[:50]}...")

    # 使用FastAPI BackgroundTasks异步处理消息（不阻塞API响应）
    background_tasks.add_task(agent.handle_message, message)

    return {"status": "ok", "message": "消息已接收，正在处理中..."}


@app.post("/api/chat/fillback")
async def chat_fillback(request: Request):
    """
    一键回填（携带前端预览面板的最新数据）
    直接解析 JSON body，兼容新旧前端格式
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "无效的请求格式"}

    session_id = body.get("sessionId")
    if not session_id:
        return {"status": "error", "message": "缺少 sessionId"}

    agent = agent_pool.get(session_id)
    if not agent:
        return {"status": "error", "message": "会话不存在", "code": "SESSION_NOT_FOUND"}

    # 兼容新旧格式：前端发送 draftProjectData/draftTeamData 时使用前端数据
    # 否则回退到后端缓存的 self.draft_project/self.draft_team
    draft_project = body.get("draftProjectData")
    draft_team = body.get("draftTeamData")

    try:
        await agent.handle_fillback_with_data(draft_project, draft_team)
        return {"status": "ok"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "proposal-ai-python-v2",
        "version": "2.0.0",
        "active_sessions": len(agent_pool)
    }


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    print("=" * 60)
    print("项目方案书AI助手服务启动 (Python主导 v2.0)")
    print(f"API文档: http://localhost:8000/docs")
    print(f"环境: {'开发模式(mock)' if Config.DEV_MODE else '生产模式(Java)'}")
    print(f"LLM模型: {Config.LLM_MODEL}")
    print(f"MCP数据服务: {Config.MCP_SERVER_URL}")
    print("=" * 60)

    # 验证配置
    Config.validate()


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    print("[Shutdown] 清理Agent会话...")
    for session_id, agent in list(agent_pool.items()):
        try:
            await agent.close()
        except Exception as e:
            print(f"[Shutdown] Agent关闭异常 ({session_id}): {e}")
    agent_pool.clear()

    print("[Shutdown] 服务已停止")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
