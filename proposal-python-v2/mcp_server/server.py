"""
MCP Server - 本地Mock版本
模拟Java数据服务，暴露MCP工具接口
启动命令: python mcp_server/server.py
"""
import json
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from mock_data import (
    get_project, update_project, get_team_members,
    add_member, update_duty
)

server = Server("java-data-mock")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_project_info",
            description="获取项目基本信息（项目编号、名称、部门、级别、产品编号、产品名称等）",
            inputSchema={
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "项目编号"}},
                "required": ["project_id"]
            }
        ),
        types.Tool(
            name="update_project",
            description="更新项目基本信息（仅限productNo和productName）",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "productNo": {"type": "string"},
                    "productName": {"type": "string"}
                },
                "required": ["project_id"]
            }
        ),
        types.Tool(
            name="get_team_members",
            description="获取项目团队成员列表（含角色、姓名、职责）",
            inputSchema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"]
            }
        ),
        types.Tool(
            name="add_member",
            description="在项目中新增一名成员",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "name": {"type": "string", "description": "人员姓名"},
                    "role": {"type": "string", "description": "项目角色"},
                    "responsibilities": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["project_id", "name", "role"]
            }
        ),
        types.Tool(
            name="update_duty",
            description="为团队成员勾选或取消勾选职责",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "name": {"type": "string", "description": "成员姓名"},
                    "duty_name": {"type": "string", "description": "职责名称"},
                    "checked": {"type": "boolean", "description": "是否勾选"}
                },
                "required": ["project_id", "name", "duty_name", "checked"]
            }
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    project_id = arguments.get("project_id", "")

    if name == "get_project_info":
        result = get_project(project_id)
    elif name == "update_project":
        result = update_project(arguments)
    elif name == "get_team_members":
        result = get_team_members(project_id)
    elif name == "add_member":
        result = add_member(
            project_id,
            arguments.get("name", ""),
            arguments.get("role", ""),
            arguments.get("responsibilities")
        )
    elif name == "update_duty":
        result = update_duty(
            project_id,
            arguments.get("name", ""),
            arguments.get("duty_name", ""),
            arguments.get("checked", False)
        )
    else:
        result = {"error": f"未知工具: {name}"}

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def main():
    print("=" * 50)
    print("MCP Server (Java Data Mock) 启动中...")
    print("通过 stdio 传输协议运行")
    print("=" * 50)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
