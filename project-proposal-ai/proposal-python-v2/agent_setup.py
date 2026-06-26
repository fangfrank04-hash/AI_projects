"""
Agent初始化模块 — v3.0 意图路由 + 多Agent架构
Router: 千问轻量模型做意图分类 → 分发给专职 Worker Agent
ProjectAgent: 项目基本信息查看/编辑
TeamAgent: 团队职责维护
"""
import os
import asyncio
import json
from typing import Optional, Literal

from pydantic import BaseModel

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg, TextBlock
from agentscope.mcp import HttpStatefulClient

from config import Config


# ============================================================
# 意图路由 Schema（AgentScope structured_model 规范）
# ============================================================
class IntentRoute(BaseModel):
    intent: Literal["project_info", "team_management", "chat", "fillback"] = "chat"


class ProjectAssistantAgent:
    """
    项目助手Agent — v3.0 多Agent架构
    Router → Worker 分发，每个 Worker 只绑定自己领域的工具
    """

    _WRITE_TOOLS = [
        "update_project_info",
        "add_team_member",
        "update_member_duty",
    ]

    def __init__(self, project_id: str, user_name: str, is_pm: bool, queue: asyncio.Queue):
        self.project_id = project_id
        self.user_name = user_name
        self.is_pm = is_pm
        self.queue = queue
        self.draft_project: Optional[dict] = None
        self.draft_team: Optional[list] = None
        self._mcp_client: Optional[HttpStatefulClient] = None
        self._mcp_update_project = None
        self._mcp_add_member = None
        self._mcp_update_duty = None
        self._mcp_get_team = None
        # 多 Agent 实例
        self._router: Optional[ReActAgent] = None
        self._project_agent: Optional[ReActAgent] = None
        self._team_agent: Optional[ReActAgent] = None
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def is_busy(self) -> bool:
        return self._lock.locked()

    # ============================================================
    # 初始化
    # ============================================================
    async def initialize(self):
        """初始化 MCP 客户端、Router、Worker Agent，加载预览数据"""
        # 1. MCP 客户端
        self._mcp_client = HttpStatefulClient(
            name="zhongzhai_java_gateway",
            url=Config.MCP_SERVER_URL,
            transport="streamable_http",
        )
        await self._mcp_client.connect()

        # 2. 缓存 MCP 工具函数（fillback + write wrapper 复用）
        self._mcp_update_project = await self._mcp_client.get_callable_function("update_project_info")
        self._mcp_add_member = await self._mcp_client.get_callable_function("add_team_member")
        self._mcp_update_duty = await self._mcp_client.get_callable_function("update_member_duty")
        self._mcp_get_team = await self._mcp_client.get_callable_function("get_team_members_list")

        # 3. 创建 Router（千问轻量模型，只做分类，stream=False）
        self._router = ReActAgent(
            name="IntentRouter",
            sys_prompt=(
                "你是意图路由器。分析用户输入，返回以下分类之一:\n"
                "- project_info: 查看/修改项目基本信息（产品编号、产品名称、项目名称、部门、级别等）\n"
                "- team_management: 查看/修改团队成员、职责勾选、新增成员\n"
                "- fillback: 一键回填、保存、提交、持久化\n"
                "- chat: 日常聊天、问候、自我介绍、询问功能\n"
                "只输出分类标签，不要回答用户问题。"
            ),
            model=DashScopeChatModel(
                model_name="qwen-plus",
                api_key=Config.DASHSCOPE_API_KEY,
                stream=False,
            ),
            formatter=DashScopeChatFormatter(),
            max_iters=1,
        )
        print("[Agent] Router initialized (qwen-turbo)")

        # 4. 创建 ProjectAgent（项目信息专属工具）
        await self._init_project_agent()

        # 5. 创建 TeamAgent（团队职责专属工具）
        await self._init_team_agent()

        print(f"[Agent] Multi-Agent initialized: project={self.project_id}, user={self.user_name}")

        # 6. 加载预览数据
        await self._load_and_push_preview()

    # ============================================================
    # Worker Agent 初始化
    # ============================================================
    async def _init_project_agent(self):
        """初始化项目信息专职 Agent"""
        ptk = Toolkit()
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        skill_path = os.path.join(skills_dir, "project_info_manager")
        if os.path.exists(os.path.join(skill_path, "SKILL.md")):
            ptk.register_agent_skill(skill_path)

        # MCP 读工具：排除团队写工具，保留项目相关的读+写
        await ptk.register_mcp_client(
            self._mcp_client,
            disable_funcs=["add_team_member", "update_member_duty"],
            namesake_strategy="skip",
        )

        # 写工具包装：update_project_info（带权限）
        _update_func = self._mcp_update_project

        async def _tool_update_project(project_id: str, productCode: str = "", productName: str = ""):
            if not self.is_pm:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": "权限拒绝：只有项目经理可以修改项目信息"}, ensure_ascii=False))])
            try:
                result = await _update_func(project_id=project_id, productCode=productCode, productName=productName)
                await self._on_write_success(result, "update_project", "projectData")
                return result
            except Exception as e:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": f"操作失败: {str(e)}"}, ensure_ascii=False))])

        ptk.register_tool_function(_tool_update_project)

        self._project_agent = ReActAgent(
            name="ProjectAgent",
            sys_prompt=(
                f"你是项目基本信息维护助手。当前项目: {self.project_id}，操作用户: {self.user_name}，"
                f"{'项目经理' if self.is_pm else '普通成员'}。\n"
                "职责: 查看/编辑项目基本信息。只有 productCode 和 productName 可修改。\n"
                "规则: 项目名称、部门、级别等字段不可修改，如用户要求修改请礼貌拒绝。\n"
                "非项目经理只能查看，任何修改请求都拒绝。"
            ),
            model=DashScopeChatModel(
                model_name=Config.LLM_MODEL,
                api_key=Config.DASHSCOPE_API_KEY,
                stream=True,
            ),
            formatter=DashScopeChatFormatter(),
            toolkit=ptk,
            memory=InMemoryMemory(),
            max_iters=10,
        )
        print("[Agent] ProjectAgent initialized")

    async def _init_team_agent(self):
        """初始化团队职责专职 Agent"""
        ttk = Toolkit()
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        skill_path = os.path.join(skills_dir, "team_duty_manager")
        if os.path.exists(os.path.join(skill_path, "SKILL.md")):
            ttk.register_agent_skill(skill_path)

        # MCP 读工具：排除项目写工具，保留团队相关的读+写
        await ttk.register_mcp_client(
            self._mcp_client,
            disable_funcs=["update_project_info"],
            namesake_strategy="skip",
        )

        # 写工具包装（带权限）
        _add_func = self._mcp_add_member
        _duty_func = self._mcp_update_duty

        async def _tool_add_member(project_id: str, name: str, role: str):
            if not self.is_pm:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": "权限拒绝：只有项目经理可以添加成员"}, ensure_ascii=False))])
            try:
                result = await _add_func(project_id=project_id, name=name, role=role)
                await self._on_write_success(result, "update_team", "teamData")
                return result
            except Exception as e:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": f"操作失败: {str(e)}"}, ensure_ascii=False))])

        async def _tool_update_duty(project_id: str, name: str, duty_name: str, checked: bool):
            if not self.is_pm:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": "权限拒绝：只有项目经理可以修改职责"}, ensure_ascii=False))])
            try:
                result = await _duty_func(project_id=project_id, name=name, duty_name=duty_name, checked=checked)
                await self._on_write_success(result, "update_team", "teamData")
                return result
            except Exception as e:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": f"操作失败: {str(e)}"}, ensure_ascii=False))])

        async def _tool_delete_member(project_id: str, name: str):
            return ToolResponse([TextBlock(type="text", text=json.dumps(
                {"success": False, "message": "团队成员不可删除，只能通过勾选/取消职责来管理。"}, ensure_ascii=False))])

        async def _tool_update_role(project_id: str, name: str, new_role: str):
            return ToolResponse([TextBlock(type="text", text=json.dumps(
                {"success": False, "message": "团队角色由系统维护，不可在此修改。"}, ensure_ascii=False))])

        ttk.register_tool_function(_tool_add_member)
        ttk.register_tool_function(_tool_update_duty)
        ttk.register_tool_function(_tool_delete_member)
        ttk.register_tool_function(_tool_update_role)

        self._team_agent = ReActAgent(
            name="TeamAgent",
            sys_prompt=(
                f"你是团队职责维护助手。当前项目: {self.project_id}，操作用户: {self.user_name}，"
                f"{'项目经理' if self.is_pm else '普通成员'}。\n"
                "职责: 查看团队成员、添加成员、勾选/取消职责。\n"
                "规则: 成员角色和姓名不可修改或删除，只有职责可勾选。\n"
                "非项目经理只能查看，任何修改请求都拒绝。"
            ),
            model=DashScopeChatModel(
                model_name=Config.LLM_MODEL,
                api_key=Config.DASHSCOPE_API_KEY,
                stream=True,
            ),
            formatter=DashScopeChatFormatter(),
            toolkit=ttk,
            memory=InMemoryMemory(),
            max_iters=10,
        )
        print("[Agent] TeamAgent initialized")

    # ============================================================
    # 意图路由 → Worker 分发
    # ============================================================
    async def _route(self, message: str) -> str:
        """意图分类（兼容千问模型，structured_model 优先，关键词+文本解析兜底）"""
        # 快速关键词匹配（零延迟，不消耗 Token）
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["回填", "保存", "提交", "持久化"]):
            return "fillback"
        # 日常聊天关键词
        if any(w in msg_lower for w in ["你好", "谢谢", "你是谁", "介绍一下", "帮助", "能做什么"]):
            return "chat"

        # structured_model 路由
        msg = Msg(name="user", content=message, role="user")
        try:
            res = await self._router(msg, structured_model=IntentRoute)
            if hasattr(res, "metadata") and res.metadata:
                intent = res.metadata.get("intent")
                if intent:
                    print(f"[Router] structured_model → {intent}")
                    return intent
        except Exception as e:
            print(f"[Router] structured_model failed: {e}")

        # 文本解析回退
        try:
            text = self._extract_text_from_response(res) if 'res' in dir() else ""
            t = text.lower()
            if "project_info" in t or "项目信息" in t:
                return "project_info"
            if "team_management" in t or "团队" in t:
                return "team_management"
            if "fillback" in t:
                return "fillback"
            # 最后用消息内容兜底
            ml = message.lower()
            if any(w in ml for w in ["项目信息", "项目基本", "产品编号", "产品名称", "项目级别", "项目名称"]):
                return "project_info"
            if any(w in ml for w in ["成员", "团队", "职责", "添加", "勾选", "取消"]):
                return "team_management"
            print(f"[Router] text fallback: '{text[:80]}'")
        except Exception:
            pass
        return "chat"

    # ============================================================
    # 消息处理（加锁 + 路由分发）
    # ============================================================
    async def handle_message(self, message: str):
        """处理用户消息（加锁 + 意图路由 + Agent 分发）"""
        if message == "__FILLBACK__":
            await self._handle_fillback()
            return

        async with self._lock:
            if self._closed:
                await self._push_event("error", {"message": "会话已关闭，请刷新页面重新连接"})
                return

            try:
                # 1. 意图路由
                intent = await self._route(message)
                print(f"[Agent] Intent: {intent} | message: {message[:50]}...")

                # 2. 分发
                user_msg = Msg(name="user", content=message, role="user")

                if intent == "project_info":
                    response = await self._project_agent(user_msg)
                elif intent == "team_management":
                    response = await self._team_agent(user_msg)
                elif intent == "fillback":
                    await self._handle_fillback()
                    return
                else:
                    # chat: 直接返回友好回复，不调 Agent
                    await self._push_event("text", {
                        "content": f"您好，{self.user_name}！我是项目AI助手。您可以对我说：查看项目信息、修改产品编号、添加团队成员、勾选职责等。"
                    })
                    return

                # 3. 推送 Worker 的回复
                if response:
                    text = self._extract_text_from_response(response)
                    if text:
                        await self._push_event("text", {"content": text})

            except Exception as e:
                import traceback
                print(f"[Agent] Error: {e}")
                traceback.print_exc()
                await self._push_event("error", {"message": f"处理失败: {str(e)}"})

    # ============================================================
    # 写操作回调 + 解析工具（保持原样）
    # ============================================================
    async def _on_write_success(self, tool_response, event_type: str, data_key: str):
        text = self._extract_text_from_response(tool_response)
        parsed = self._parse_result(text)
        if parsed.get("success"):
            data = parsed.get("data", {})
            if data_key == "projectData":
                self.draft_project = data
                push_data = data
            else:
                self.draft_team = data if isinstance(data, list) else data.get("content", data)
                push_data = self.draft_team
            asyncio.create_task(self._push_event(event_type, {data_key: push_data}))
        else:
            print(f"[Agent] _on_write_success failed: {text[:200]}")

    @staticmethod
    def _extract_text_from_response(response) -> str:
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        if hasattr(response, "content") and response.content:
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
        return ""

    @staticmethod
    def _parse_result(text) -> dict:
        if not text:
            return {"success": False, "message": "空数据"}
        if isinstance(text, dict):
            return text
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                try:
                    return json.loads(text.replace("'", '"'))
                except json.JSONDecodeError:
                    return {"success": False, "message": f"数据格式异常: {text[:100]}"}
        return {}

    # ============================================================
    # 预览加载 + 回填（保持原样）
    # ============================================================
    async def _load_and_push_preview(self):
        get_project = await self._mcp_client.get_callable_function("get_project_info")
        project_result = await get_project(project_id=self.project_id)
        text = self._extract_text_from_response(project_result)
        self.draft_project = self._parse_result(text).get("data", {})

        get_team = await self._mcp_client.get_callable_function("get_team_members_list")
        team_result = await get_team(project_id=self.project_id)
        text = self._extract_text_from_response(team_result)
        team_data = self._parse_result(text).get("data", {})
        self.draft_team = team_data.get("content", team_data) if isinstance(team_data, dict) else team_data

        await self._push_event("preview", {"projectData": self.draft_project, "teamData": self.draft_team})

        greeting = f"您好，{self.user_name}！我是您的项目AI助手。"
        if not self.is_pm:
            greeting += "（您当前以项目成员身份查看，无编辑权限）"
        else:
            greeting += "目前支持为您自动解析与填写【项目基本信息】及【团队职责】。"
        await self._push_event("text", {"content": greeting})

    async def handle_fillback_with_data(self, draft_project_data: dict = None, draft_team_data: list = None):
        async with self._lock:
            if self._closed:
                await self._push_event("error", {"message": "会话已关闭，请刷新页面重新连接"})
                return
            if not self.is_pm:
                await self._push_event("error", {"message": "权限拒绝：只有项目经理可以执行回填"})
                return
            if draft_project_data is not None:
                self.draft_project = draft_project_data
            if draft_team_data is not None:
                self.draft_team = draft_team_data
            await self._do_fillback()

    async def _handle_fillback(self):
        if not self.is_pm:
            await self._push_event("error", {"message": "权限拒绝：只有项目经理可以执行回填"})
            return
        await self._do_fillback()

    async def _do_fillback(self):
        errors = []
        if self.draft_project and self._mcp_update_project:
            try:
                result = await self._mcp_update_project(
                    project_id=self.project_id,
                    productCode=self.draft_project.get("productCode", ""),
                    productName=self.draft_project.get("productName", ""),
                )
                parsed = self._parse_result(self._extract_text_from_response(result))
                if not parsed.get("success"):
                    errors.append(f"项目信息保存失败: {parsed.get('message', '未知错误')}")
            except Exception as e:
                errors.append(f"项目信息保存异常: {str(e)}")

        if self.draft_team and self._mcp_client:
            try:
                batch_func = await self._mcp_client.get_callable_function("batch_sync_team_data")
                payload = json.dumps(self.draft_team, ensure_ascii=False)
                result = await batch_func(project_id=self.project_id, team_layout=payload)
                parsed = self._parse_result(self._extract_text_from_response(result))
                if not parsed.get("success"):
                    errors.append(f"团队批量同步失败: {parsed.get('message', '未知错误')}")
                elif parsed.get("errors"):
                    errors.extend(parsed["errors"])
            except Exception as e:
                errors.append(f"团队批量同步异常: {str(e)}")

        if errors:
            await self._push_event("error", {"message": "回填部分失败: " + "; ".join(errors)})
        else:
            await self._push_event("fillback_complete", {
                "success": True,
                "message": "回填成功！项目基本信息与团队数据已同步至左侧表单，并已持久化保存。"
            })

    async def _push_event(self, event_type: str, data: dict):
        await self.queue.put({"event": event_type, "data": data})

    async def close(self):
        self._closed = True
        if self._mcp_client:
            try:
                await self._mcp_client.close()
                print("[Agent] MCP client closed")
            except Exception as e:
                print(f"[Agent] Error closing MCP client: {e}")
            self._mcp_client = None
