"""
FastAPI入口文件 - Python主导的AI项目助手服务
启动命令: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import asyncio
import json
import uuid
import os

from fastapi import FastAPI, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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

# 🆕 挂载静态文件目录（Swagger UI 本地文件，解决内网无 CDN 问题）
app.mount("/static", StaticFiles(directory="static"), name="static")

# Agent池: session_id -> ProjectAssistantAgent
agent_pool: dict[str, ProjectAssistantAgent] = {}

# SSE心跳间隔（秒）
HEARTBEAT_INTERVAL = 30


class ChatMessageRequest(BaseModel):
    """发送消息请求体"""
    sessionId: str
    message: str


class ChatRequest(BaseModel):
    """模式3 单次请求体（无需 session，每次请求独立创建 Agent）"""
    projectId: str
    userName: str
    isPM: bool = False
    message: str


class FillbackV3Request(BaseModel):
    """模式3 回填请求体（无 session，独立创建 Agent 完成持久化）"""
    projectId: str
    userName: str
    isPM: bool = False
    draftProjectData: dict = None
    draftTeamData: list = None


@app.get("/api/chat/stream")
async def chat_stream(
    request: Request,
    projectId: str = Query(..., description="项目编号"),
    userName: str = Query(..., description="当前用户姓名"),
    isPM: bool = Query(False, description="是否项目经理")
):
    """
    SSE流式端点
    前端通过EventSource连接此端点，建立持久化SSE连接
    连接断开时自动清理 Agent 资源，防止内存泄漏
    """
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()

    # 创建并初始化Agent
    agent = ProjectAssistantAgent(projectId, userName, isPM, queue)
    await agent.initialize()
    agent_pool[session_id] = agent

    print(f"[SSE] Connected: session_id={session_id}, project={projectId}, user={userName}, isPM={isPM}")

    async def event_generator():
        try:
            yield format_sse("connected", {"sessionId": session_id, "status": "ok"})
            last_activity = asyncio.get_event_loop().time()

            while True:
                # 防御性检查：客户端是否已主动断开（刷新页面、关闭标签页等）
                if await request.is_disconnected():
                    print(f"[SSE] Client disconnected: session_id={session_id}")
                    break

                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=5.0)

                    if msg.get("event") == "close":
                        print(f"[SSE] Connection closed: session_id={session_id}")
                        break

                    yield format_sse(msg["event"], msg["data"])
                    last_activity = asyncio.get_event_loop().time()

                except asyncio.TimeoutError:
                    now = asyncio.get_event_loop().time()
                    if now - last_activity >= HEARTBEAT_INTERVAL:
                        yield format_sse("ping", {"time": int(now)})
                        last_activity = now
        finally:
            # 无论何种原因退出（正常关闭、客户端断开、异常），必须清理 Agent 资源
            print(f"[SSE] Cleaning session: {session_id}")
            target_agent = agent_pool.pop(session_id, None)
            if target_agent:
                try:
                    await target_agent.close()
                except Exception as e:
                    print(f"[SSE] Agent close error ({session_id}): {e}")

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

    # 并发前置拦截：Agent 正在处理上一条指令时拒绝新请求
    if agent.is_busy:
        return {"error": "AI助手正在思考或执行操作中，请稍后再试", "code": "AGENT_BUSY"}

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

    # 并发前置拦截
    if agent.is_busy:
        return {"status": "error", "message": "AI助手正在处理中，请稍后再试", "code": "AGENT_BUSY"}

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


# ============================================================
# 🆕 模式3：POST /api/chat（单次请求流式返回，无 session）
# 每次请求独立创建 → 处理 → 销毁 Agent，不依赖 agent_pool
# ============================================================
@app.post("/api/chat")
async def chat_v3(request: ChatRequest):
    """
    模式3 流式聊天接口
    前端通过 fetch + ReadableStream 调用：
    - AI 对话回复 → 流式 text 事件（逐段推送）
    - 表格/数据查询 → 一次性 update_project / update_team 事件（整包推送）
    """
    queue = asyncio.Queue()
    agent = ProjectAssistantAgent(
        request.projectId, request.userName, request.isPM, queue
    )

    async def event_generator():
        try:
            await agent.initialize()
            yield format_sse("connected", {"status": "ok"})

            # __INIT__ 仅加载预览数据，不走消息处理（避免重复问候）
            if request.message == "__INIT__":
                # drain queue：清空 initialize 过程中积压的事件
                while not queue.empty():
                    msg = queue.get_nowait()
                    if msg.get("event") != "close":
                        yield format_sse(msg["event"], msg["data"])
                return

            # 后台启动消息处理，结果通过 queue 返回
            task = asyncio.create_task(agent.handle_message(request.message))

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    yield format_sse("error", {"message": "操作超时，请重试"})
                    break

                if msg.get("event") == "close":
                    break

                yield format_sse(msg["event"], msg["data"])

                # Agent 处理完毕 → 清空队列残余事件后结束
                if task.done():
                    while not queue.empty():
                        msg = queue.get_nowait()
                        if msg.get("event") != "close":
                            yield format_sse(msg["event"], msg["data"])
                    break
        finally:
            await agent.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================
# 🆕 模式3：POST /api/chat/fillback-v3（无 session 回填）
# 前端点"一键回填"时独立调用，不依赖 SSE 长连接
# ============================================================
@app.post("/api/chat/fillback-v3")
async def chat_fillback_v3(request: FillbackV3Request):
    """
    模式3 一键回填（无 session）
    独立创建 Agent → 执行持久化 → 销毁，不留在 agent_pool 中
    """
    if not request.isPM:
        return {"status": "error", "message": "权限拒绝：只有项目经理可以执行回填"}

    queue = asyncio.Queue()
    agent = ProjectAssistantAgent(
        request.projectId, request.userName, request.isPM, queue
    )

    try:
        await agent.initialize()
        await agent.handle_fillback_with_data(
            request.draftProjectData, request.draftTeamData
        )
        return {"status": "ok"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        await agent.close()


# ============================================================
# 🆕 Swagger UI（重定向到本地静态文件，内网可用）
# ============================================================
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return RedirectResponse(url="/static/swagger-ui.html")


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
