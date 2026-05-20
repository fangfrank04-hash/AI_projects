"""
Agent初始化模块
创建并配置ReActAgent，使用 AgentScope 原生 MCP 集成连接独立 MCP HTTP 服务
"""
import os
import asyncio
import json
from typing import Optional

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg, TextBlock
from agentscope.mcp import HttpStatefulClient

from config import Config


class ProjectAssistantAgent:
    """
    项目助手Agent
    负责处理项目基本信息和团队职责维护的所有AI交互
    读操作 → AgentScope 原生 MCP 工具（自动发现）
    写操作 → 带权限校验 + SSE推送的包装函数
    """

    # MCP 写工具名称列表（需权限校验，不由原生MCP自动注册）
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
        self.agent: Optional[ReActAgent] = None
        self.draft_project: Optional[dict] = None
        self.draft_team: Optional[list] = None
        self._mcp_client: Optional[HttpStatefulClient] = None
        # MCP 工具函数引用（初始化时缓存，fillback 时复用）
        self._mcp_update_project = None
        self._mcp_add_member = None
        self._mcp_update_duty = None
        self._mcp_get_team = None

    async def initialize(self):
        """初始化Agent：加载Skills、注册MCP工具、创建ReActAgent"""
        toolkit = Toolkit()

        # 1. 加载Skills（步骤1-5 + 团队职责，V1启用步骤1+团队职责，其余为V2占位）
        skill_names = [
            "project_info_manager",
            "team_duty_manager",
            "control_plan_manager",
            "schedule_manager",
            "resource_plan_manager",
            "quality_plan_manager",
        ]
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        for name in skill_names:
            skill_path = os.path.join(skills_dir, name)
            if os.path.exists(os.path.join(skill_path, "SKILL.md")):
                toolkit.register_agent_skill(skill_path)
                print(f"[Agent] Skill loaded: {name}")
            else:
                print(f"[Agent] Warning: Skill not found: {name}")

        # 2. 创建 AgentScope 原生 MCP 客户端（Streamable HTTP）
        self._mcp_client = HttpStatefulClient(
            name="zhongzhai_java_gateway",
            url=Config.MCP_SERVER_URL,
            transport="streamable_http",
        )

        # 3. 注册 MCP 读工具（自动发现，写工具禁用后用包装函数替代）
        await self._mcp_client.connect()
        await toolkit.register_mcp_client(
            self._mcp_client,
            disable_funcs=list(self._WRITE_TOOLS),
            namesake_strategy="skip",
        )
        print(f"[Agent] MCP read tools registered (auto-discovered)")

        # 4. 注册写工具包装函数（权限校验 + SSE推送）
        await self._register_write_tools(toolkit)

        # 5. 创建ReActAgent
        sys_prompt = self._build_system_prompt()

        self.agent = ReActAgent(
            name="project_assistant",
            sys_prompt=sys_prompt,
            model=DashScopeChatModel(
                model_name=Config.LLM_MODEL,
                api_key=Config.DASHSCOPE_API_KEY,
                stream=True,
            ),
            formatter=DashScopeChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=10,
        )

        print(f"[Agent] ReActAgent initialized for project={self.project_id}, user={self.user_name}")

        # 6. 加载初始数据并推送预览
        await self._load_and_push_preview()

    async def _register_write_tools(self, toolkit: Toolkit):
        """注册写工具包装函数——通过 AgentScope MCP 客户端调用，附带权限校验和SSE推送"""

        # 获取 MCP 工具的可调用函数，同时缓存到实例变量供 fillback 复用
        self._mcp_update_project = await self._mcp_client.get_callable_function("update_project_info")
        self._mcp_add_member = await self._mcp_client.get_callable_function("add_team_member")
        self._mcp_update_duty = await self._mcp_client.get_callable_function("update_member_duty")
        self._mcp_get_team = await self._mcp_client.get_callable_function("get_team_members_list")

        update_project_func = self._mcp_update_project
        add_member_func = self._mcp_add_member
        update_duty_func = self._mcp_update_duty

        async def tool_update_project_info(project_id: str, productNo: str = "", productName: str = ""):
            """更新项目基本信息（仅限productNo和productName，其余字段不可修改）"""
            if not self.is_pm:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": "权限拒绝：只有项目经理可以修改项目信息"}, ensure_ascii=False))])
            try:
                result = await update_project_func(project_id=project_id, productNo=productNo, productName=productName)
                await self._on_write_success(result, "update_project", "projectData")
                return result
            except Exception as e:
                import traceback
                print(f"[Agent] tool_update_project_info 调用失败: {e}")
                traceback.print_exc()
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": f"操作失败: {str(e)}"}, ensure_ascii=False))])

        async def tool_add_team_member(project_id: str, name: str, role: str):
            """添加团队成员"""
            if not self.is_pm:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": "权限拒绝：只有项目经理可以添加成员"}, ensure_ascii=False))])
            try:
                result = await add_member_func(project_id=project_id, name=name, role=role)
                await self._on_write_success(result, "update_team", "teamData")
                return result
            except Exception as e:
                import traceback
                print(f"[Agent] tool_add_team_member 调用失败: {e}")
                traceback.print_exc()
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": f"操作失败: {str(e)}"}, ensure_ascii=False))])

        async def tool_delete_team_member(project_id: str, name: str):
            """删除团队成员（已禁用：团队成员不可删除）"""
            return ToolResponse([TextBlock(type="text", text=json.dumps(
                {"success": False, "message": "团队成员不可删除，只能通过勾选/取消职责来管理。如需调整人员，请联系管理员。"}, ensure_ascii=False))])

        async def tool_update_member_role(project_id: str, name: str, new_role: str):
            """更新团队成员角色名称（已禁用：角色不可修改）"""
            return ToolResponse([TextBlock(type="text", text=json.dumps(
                {"success": False, "message": "团队角色由系统维护，不可在此修改。"}, ensure_ascii=False))])

        async def tool_update_member_duty(project_id: str, name: str, duty_name: str, checked: bool):
            """为团队成员勾选或取消勾选职责"""
            if not self.is_pm:
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": "权限拒绝：只有项目经理可以修改职责"}, ensure_ascii=False))])
            try:
                result = await update_duty_func(project_id=project_id, name=name, duty_name=duty_name, checked=checked)
                await self._on_write_success(result, "update_team", "teamData")
                return result
            except Exception as e:
                import traceback
                print(f"[Agent] tool_update_member_duty 调用失败: {e}")
                traceback.print_exc()
                return ToolResponse([TextBlock(type="text", text=json.dumps(
                    {"success": False, "message": f"操作失败: {str(e)}"}, ensure_ascii=False))])

        # 注册到Toolkit（使用与 MCP Server 一致的名称）
        toolkit.register_tool_function(tool_update_project_info)
        toolkit.register_tool_function(tool_add_team_member)
        toolkit.register_tool_function(tool_delete_team_member)
        toolkit.register_tool_function(tool_update_member_role)
        toolkit.register_tool_function(tool_update_member_duty)

    async def _on_write_success(self, tool_response: ToolResponse, event_type: str, data_key: str):
        """写操作成功后：解析结果、更新本地缓存、推送SSE事件"""
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
            print(f"[Agent] _on_write_success: 操作失败, event={event_type}, response={text[:300]}")

    @staticmethod
    def _extract_text_from_response(response: ToolResponse) -> str:
        """从 ToolResponse 中提取文本内容"""
        if response and response.content:
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
        return ""

    @staticmethod
    def _parse_result(text) -> dict:
        """解析工具返回的文本（JSON 或 Python repr 格式）"""
        if isinstance(text, dict):
            return text
        if isinstance(text, str):
            import ast
            for parser in [
                lambda s: json.loads(s),
                lambda s: json.loads(s.replace("'", '"')),
                lambda s: ast.literal_eval(s),
            ]:
                try:
                    result = parser(text)
                    if isinstance(result, dict):
                        return result
                except (json.JSONDecodeError, ValueError, SyntaxError):
                    continue
        return {}

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return f"""你是一位专业的项目管理AI助手，帮助项目经理维护项目基本信息和团队职责。

## 当前上下文
- 项目编号: {self.project_id}
- 当前用户: {self.user_name}
- 是否项目经理: {"是" if self.is_pm else "否"}

## 可用工具
1. get_project_info(project_id) — 获取项目基本信息
2. update_project_info(project_id, productNo, productName) — 更新项目信息（仅限productNo和productName）
3. get_team_members_list(project_id) — 获取团队成员列表
4. add_team_member(project_id, name, role) — 添加团队成员
5. update_member_duty(project_id, name, duty_name, checked) — 勾选/取消职责

## 权限规则
- 只有项目经理（isPM=true）可以修改数据
- 项目基本信息中只有productNo（产品编号）和productName（产品名称）可修改
- 不要修改项目名称、立项部门、项目级别等不可编辑字段——如果用户要求修改这些，请礼貌拒绝
- 非项目经理只能查看数据，任何修改请求都拒绝
- 团队成员不可删除，角色和姓名不可修改，只有职责（responsibilities）可以勾选/取消勾选

## 工作方式
1. 先分析用户意图（修改项目信息？修改团队？日常聊天？查看数据？）
2. 获取最新数据（如需要）
3. 执行对应工具操作
4. 向用户报告操作结果
5. 如果是日常聊天（打招呼、自我介绍、问问题），用自然语言回复，不调用工具

## 回复风格
- 专业、简洁、友好
- 操作成功：明确告知修改了什么
- 权限拒绝：礼貌说明原因
- 字段拦截：解释只有产品编号和产品名称可修改
"""

    async def _load_and_push_preview(self):
        """加载初始数据并通过SSE推送预览事件"""
        # 使用 AgentScope MCP 客户端获取数据
        get_project = await self._mcp_client.get_callable_function("get_project_info")
        project_result = await get_project(project_id=self.project_id)
        text = self._extract_text_from_response(project_result)
        project_parsed = self._parse_result(text)
        self.draft_project = project_parsed.get("data", {})

        get_team = await self._mcp_client.get_callable_function("get_team_members_list")
        team_result = await get_team(project_id=self.project_id)
        text = self._extract_text_from_response(team_result)
        team_parsed = self._parse_result(text)
        team_data = team_parsed.get("data", {})
        self.draft_team = team_data.get("content", team_data) if isinstance(team_data, dict) else team_data

        # 推送预览事件
        await self._push_event("preview", {
            "projectData": self.draft_project,
            "teamData": self.draft_team
        })

        # 推送问候语
        greeting = f"您好，{self.user_name}！我是您的项目AI助手。"
        if not self.is_pm:
            greeting += "（您当前以项目成员身份查看，无编辑权限）"
        else:
            greeting += "目前支持为您自动解析与填写【项目基本信息】及【团队职责】。"

        await self._push_event("text", {"content": greeting})

    async def handle_message(self, message: str):
        """处理用户消息"""
        if message == "__FILLBACK__":
            await self._handle_fillback()
            return

        try:
            msg = Msg(name="user", content=message, role="user")
            response = await self.agent(msg)

            if response and response.content:
                text = self._extract_text_from_response(response)
                if text:
                    await self._push_event("text", {"content": text})
        except Exception as e:
            import traceback
            print(f"[Agent] Error handling message: {e}")
            traceback.print_exc()
            await self._push_event("error", {"message": f"处理失败: {str(e)}"})

    async def handle_fillback_with_data(self, draft_project_data: dict = None, draft_team_data: list = None):
        """接收前端预览面板数据并执行持久化（由 /api/chat/fillback 调用）"""
        if not self.is_pm:
            await self._push_event("error", {"message": "权限拒绝：只有项目经理可以执行回填"})
            return

        # 用前端传来的最新数据更新本地缓存
        if draft_project_data is not None:
            self.draft_project = draft_project_data
        if draft_team_data is not None:
            self.draft_team = draft_team_data

        await self._do_fillback()

    async def _handle_fillback(self):
        """处理一键回填指令（旧版兼容：直接用后端缓存的数据）"""
        if not self.is_pm:
            await self._push_event("error", {"message": "权限拒绝：只有项目经理可以执行回填"})
            return
        await self._do_fillback()

    async def _do_fillback(self):
        """将 self.draft_project / self.draft_team 持久化到 MCP/Java 后端"""
        errors = []

        # 持久化项目基本信息（productNo, productName）
        if self.draft_project and self._mcp_update_project:
            try:
                result = await self._mcp_update_project(
                    project_id=self.project_id,
                    productNo=self.draft_project.get("productNo", ""),
                    productName=self.draft_project.get("productName", "")
                )
                text = self._extract_text_from_response(result)
                parsed = self._parse_result(text)
                if not parsed.get("success"):
                    errors.append(f"项目信息保存失败: {parsed.get('message', '未知错误')}")
            except Exception as e:
                import traceback
                print(f"[Agent] _do_fillback update_project error: {e}")
                traceback.print_exc()
                errors.append(f"项目信息保存异常: {str(e)}")

        # 持久化团队成员数据（逐个对比并同步）
        if self.draft_team and self._mcp_get_team:
            try:
                # 获取当前已持久化的团队数据
                team_result = await self._mcp_get_team(project_id=self.project_id)
                team_text = self._extract_text_from_response(team_result)
                team_parsed = self._parse_result(team_text)
                current_team = []
                if team_parsed.get("success"):
                    team_data = team_parsed.get("data", {})
                    current_team = team_data.get("content", team_data) if isinstance(team_data, dict) else team_data

                # 构建当前成员姓名集合
                current_names = {m.get("name", m.get("userName", "")) for m in current_team}

                # 团队成员不可删除、不可改角色，只新增 + 同步职责
                for draft_member in self.draft_team:
                    dname = draft_member.get("name", "")
                    drole = draft_member.get("role", "")

                    if dname not in current_names:
                        # 新成员：直接添加
                        if self._mcp_add_member:
                            await self._mcp_add_member(project_id=self.project_id, name=dname, role=drole)

                    # 同步职责（唯一允许的修改）
                    if self._mcp_update_duty:
                        dresp = draft_member.get("responsibilities", [])
                        for r in dresp:
                            rname = r.get("name", r) if isinstance(r, dict) else r
                            checked = r.get("checked", True) if isinstance(r, dict) else True
                            await self._mcp_update_duty(project_id=self.project_id, name=dname, duty_name=rname, checked=checked)
            except Exception as e:
                import traceback
                print(f"[Agent] _do_fillback team error: {e}")
                traceback.print_exc()
                errors.append(f"团队数据保存异常: {str(e)}")

        if errors:
            await self._push_event("error", {"message": "回填部分失败: " + "; ".join(errors)})
        else:
            await self._push_event("fillback_complete", {
                "success": True,
                "message": "回填成功！项目基本信息与团队数据已同步至左侧表单，并已持久化保存。"
            })

    async def _push_event(self, event_type: str, data: dict):
        """推送SSE事件到队列"""
        await self.queue.put({
            "event": event_type,
            "data": data
        })

    async def close(self):
        """关闭 MCP 客户端连接"""
        if self._mcp_client:
            try:
                await self._mcp_client.close()
                print("[Agent] MCP client closed")
            except Exception as e:
                print(f"[Agent] Error closing MCP client: {e}")
            self._mcp_client = None
