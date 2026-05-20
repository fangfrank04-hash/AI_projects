"""
独立 MCP HTTP 服务（Streamable HTTP 协议）
启动命令: python -m mcp_server.http_server
端口: 8001, 路径: /mcp

dev模式(DEV_MODE=true): 使用 Python mock_data 内存操作
prod模式(DEV_MODE=false, 默认): 调用 Java HTTP API → H2 database
"""
import os
import sys
import json

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp_server.config import DEV_MODE, MCP_HOST, MCP_PORT, MCP_PATH
from mcp_server.java_client import JavaHttpClient, JavaClientError

# 仅在 DEV_MODE 下使用 mock_data
if DEV_MODE:
    from mcp_server.mock_data import (
        get_project, update_project, get_team_members,
        add_member, update_duty, get_user_by_id
    )

mcp = FastMCP(
    "zhongzhai_java_gateway",
    host=MCP_HOST,
    port=MCP_PORT,
    streamable_http_path=MCP_PATH
)

# Java HTTP 客户端（非 DEV_MODE 时使用）
_java_client: JavaHttpClient = None


def _get_java_client() -> JavaHttpClient:
    global _java_client
    if _java_client is None:
        _java_client = JavaHttpClient()
    return _java_client


def _wrap_read_response(java_result: dict) -> str:
    """包装 Java 读操作的返回值为 {'success': True, 'data': ...} 格式"""
    if "success" in java_result:
        return json.dumps(java_result, ensure_ascii=False)
    return json.dumps({"success": True, "data": java_result}, ensure_ascii=False)


def _normalize_project(project: dict) -> dict:
    """标准化 Java 项目数据格式（null → ""）"""
    for key in ("productNo", "productName", "changeReq", "proposalBackground", "proposalScope"):
        if project.get(key) is None:
            project[key] = ""
    return project


def _normalize_team_member(member: dict) -> dict:
    """标准化 Java TeamMember 格式，保持前端的 {role, name, responsibilities: [{name, checked}]} 格式

    Java 返回: {id, role, name, userId, nickname, roleIds, responsibilities: [{name, checked}, ...]}
    前端期望: {id, role, name, userId, roleIds, responsibilities: [{name, checked}, ...]}
    """
    resp = member.get("responsibilities", [])
    # 确保 responsibilities 是 [{name, checked}] 格式
    if resp and isinstance(resp, list):
        if len(resp) > 0 and isinstance(resp[0], str):
            # 字符串列表 → 对象列表
            resp = [{"name": r, "checked": True} for r in resp]
        # 已是对象列表，保持原样（Java 原生格式）
    else:
        resp = []

    return {
        "id": str(member.get("id", "")),
        "userId": member.get("userId", member.get("user_id", "")),
        "name": member.get("nickname", member.get("name", member.get("userName", ""))),
        "role": member.get("role", member.get("roleName", "")),
        "roleIds": member.get("roleIds", member.get("role_ids", [])),
        "responsibilities": resp,
    }


# ============================================================
# Tool 1: 查询项目基本信息
# ============================================================
@mcp.tool()
async def get_project_info(project_id: str) -> str:
    """
    根据项目ID查询项目基本信息。
    返回项目名称、立项部门、项目级别、产品编号、产品名称、基准需求编号、
    需求相关部门、变更需求编号、项目经理等字段。
    参数: project_id - 项目编号，例如 PJ-202603-S-068
    """
    if DEV_MODE:
        result = get_project(project_id)
        return json.dumps(result, ensure_ascii=False)

    try:
        client = _get_java_client()
        java_result = await client.safe_call(
            "/itmp/pmProjectService/findProjectById",
            {"id": project_id}
        )
        java_result = _normalize_project(java_result)
        return _wrap_read_response(java_result)
    except JavaClientError as e:
        return json.dumps({"success": False, "message": e.message, "detail": e.detail}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] get_project_info 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)


# ============================================================
# Tool 2: 更新项目基本信息
# ============================================================
@mcp.tool()
async def update_project_info(project_id: str, productNo: str = "", productName: str = "") -> str:
    """
    更新项目基本信息。当前仅允许编辑 productNo（产品编号）和 productName（产品名称）。
    参数:
      project_id - 项目编号
      productNo  - 新的产品编号（可选）
      productName - 新的产品名称（可选）
    """
    if DEV_MODE:
        # 始终传递两个字段（包括空值），允许用户清空产品编号/名称
        data = {"id": project_id, "productNo": productNo, "productName": productName}
        result = update_project(data)
        return json.dumps(result, ensure_ascii=False)

    try:
        client = _get_java_client()
        java_params = {"id": project_id, "productNo": productNo, "productName": productName}

        java_result = await client.safe_call(
            "/itmp/pmProjectService/updatePmProject",
            java_params
        )

        # 写操作成功后，重新获取最新数据并附加到结果
        if java_result.get("success"):
            updated = await client.safe_call(
                "/itmp/pmProjectService/findProjectById",
                {"id": project_id}
            )
            java_result["data"] = _normalize_project(updated)

        return json.dumps(java_result, ensure_ascii=False)
    except JavaClientError as e:
        return json.dumps({"success": False, "message": e.message, "detail": e.detail}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)


# ============================================================
# Tool 3: 查询团队成员
# ============================================================
@mcp.tool()
async def get_team_members_list(project_id: str) -> str:
    """
    查询项目团队成员列表（含角色、姓名、职责）。
    参数: project_id - 项目编号
    返回分页格式的团队成员数据。
    """
    if DEV_MODE:
        result = get_team_members(project_id)
        # DEV模式下也要归一化 mock 数据，对齐前端需要的字段格式
        if result.get("success") and "data" in result and "content" in result["data"]:
            result["data"]["content"] = [_normalize_team_member(m) for m in result["data"]["content"]]
        return json.dumps(result, ensure_ascii=False)

    try:
        client = _get_java_client()
        java_result = await client.safe_call(
            "/itmp/pmProjectMemberService/findPmProjectMemberList",
            {"pmProjectId": project_id, "page": 0, "size": 100}
        )

        # 标准化团队成员格式
        if "content" in java_result:
            java_result["content"] = [_normalize_team_member(m) for m in java_result["content"]]

        return _wrap_read_response(java_result)
    except JavaClientError as e:
        return json.dumps({"success": False, "message": e.message, "detail": e.detail}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)


# ============================================================
# Tool 4: 新增团队成员
# ============================================================
@mcp.tool()
async def add_team_member(project_id: str, name: str, role: str) -> str:
    """
    向项目添加一名新成员。
    参数:
      project_id - 项目编号
      name       - 成员姓名（同时作为 userId）
      role       - 项目角色（如：产品经理、架构师、开发工程师）
    """
    if DEV_MODE:
        result = add_member(project_id, name, role)
        if result.get("success") and "data" in result:
            result["data"] = [_normalize_team_member(m) for m in result["data"]]
        return json.dumps(result, ensure_ascii=False)

    try:
        client = _get_java_client()
        java_result = await client.safe_call(
            "/itmp/pmProjectMemberService/createPmProjectMembers",
            {"pmProjectId": project_id, "userIds": [name]}
        )

        # 写操作成功后重新获取团队列表
        if java_result.get("success"):
            updated = await client.safe_call(
                "/itmp/pmProjectMemberService/findPmProjectMemberList",
                {"pmProjectId": project_id, "page": 0, "size": 100}
            )
            if "content" in updated:
                updated["content"] = [_normalize_team_member(m) for m in updated["content"]]
            java_result["data"] = updated

        return json.dumps(java_result, ensure_ascii=False)
    except JavaClientError as e:
        return json.dumps({"success": False, "message": e.message, "detail": e.detail}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)


# ============================================================
# Tool 5: 删除团队成员（已禁用）
# ============================================================
@mcp.tool()
async def delete_team_member(project_id: str, name: str) -> str:
    """
    从项目中删除指定成员（已禁用：团队成员不可删除）。
    """
    return json.dumps({
        "success": False,
        "message": "团队成员不可删除，只能通过勾选/取消职责来管理。如需调整人员，请联系管理员。"
    }, ensure_ascii=False)


# ============================================================
# Tool 6: 更新成员角色（已禁用）
# ============================================================
@mcp.tool()
async def update_member_role(project_id: str, name: str, new_role: str) -> str:
    """
    更新团队成员的项目角色（已禁用：角色不可修改）。
    """
    return json.dumps({
        "success": False,
        "message": "团队角色由系统维护，不可在此修改。"
    }, ensure_ascii=False)


# ============================================================
# Tool 9: 批量同步团队数据（消灭 N+1）
# ============================================================
@mcp.tool()
async def batch_sync_team_data(project_id: str, team_layout: str) -> str:
    """
    一次性批量同步整个团队的成员和职责数据，替代多次单条更新。
    参数:
      project_id   - 项目编号
      team_layout  - JSON字符串，格式: [{"name":"张三","role":"开发","responsibilities":[{"name":"编码","checked":true},...]}, ...]
    """
    try:
        layout = json.loads(team_layout) if isinstance(team_layout, str) else team_layout
    except json.JSONDecodeError:
        return json.dumps({"success": False, "message": "team_layout 不是合法的 JSON"}, ensure_ascii=False)

    if DEV_MODE:
        from mcp_server.mock_data import batch_sync_team
        result = batch_sync_team(project_id, layout)
        if result.get("success") and "data" in result:
            result["data"] = [_normalize_team_member(m) for m in result["data"]]
        return json.dumps(result, ensure_ascii=False)

    try:
        client = _get_java_client()
        # 先获取当前团队
        current = await client.safe_call(
            "/itmp/pmProjectMemberService/findPmProjectMemberList",
            {"pmProjectId": project_id, "page": 0, "size": 100}
        )
        current_names = {m.get("name", m.get("nickname", "")) for m in current.get("content", [])}

        errors = []
        for member in layout:
            name = member.get("name", "")
            role = member.get("role", "")

            # 新成员：添加
            if name not in current_names and name:
                try:
                    await client.safe_call(
                        "/itmp/pmProjectMemberService/createPmProjectMembers",
                        {"pmProjectId": project_id, "userIds": [name]}
                    )
                    current_names.add(name)
                except Exception as e:
                    errors.append(f"添加成员 {name} 失败: {e}")
                    continue

            # 同步职责
            duties = member.get("responsibilities", [])
            if duties:
                # 在 layout 中查找对应的 role
                try:
                    team = await client.safe_call(
                        "/itmp/pmProjectMemberService/findPmProjectMemberList",
                        {"pmProjectId": project_id, "page": 0, "size": 100}
                    )
                    member_role = None
                    for m in team.get("content", []):
                        if m.get("name") == name or m.get("nickname") == name or m.get("userId") == name:
                            member_role = m.get("role", "")
                            break

                    if member_role:
                        duty_names = [d.get("name", d) if isinstance(d, dict) else d for d in duties if d.get("checked", True) if isinstance(d, dict) else True]
                        if duty_names:
                            await client.safe_call(
                                "/portal/abikoleManagerService/updateDuty",
                                {"rid": member_role, "ids": duty_names, "pid": project_id, "checked": True}
                            )
                except Exception as e:
                    errors.append(f"同步 {name} 的职责失败: {e}")

        # 获取最终结果
        final = await client.safe_call(
            "/itmp/pmProjectMemberService/findPmProjectMemberList",
            {"pmProjectId": project_id, "page": 0, "size": 100}
        )
        if "content" in final:
            final["content"] = [_normalize_team_member(m) for m in final["content"]]

        result = {"success": True, "message": "批量同步完成", "data": final}
        if errors:
            result["errors"] = errors
        return json.dumps(result, ensure_ascii=False)

    except JavaClientError as e:
        return json.dumps({"success": False, "message": e.message}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": f"批量同步异常: {str(e)}"}, ensure_ascii=False)


# ============================================================
# Tool 7: 更新成员职责
# ============================================================
@mcp.tool()
async def update_member_duty(project_id: str, name: str, duty_name: str, checked: bool) -> str:
    """
    为团队成员勾选或取消勾选职责。
    参数:
      project_id - 项目编号
      name       - 成员姓名（用于查找成员角色）
      duty_name  - 职责名称（如：产品发布、项目立项、里程碑节点评审）
      checked    - true=勾选, false=取消勾选
    """
    if DEV_MODE:
        result = update_duty(project_id, name, duty_name, checked)
        if result.get("success") and "data" in result:
            result["data"] = [_normalize_team_member(m) for m in result["data"]]
        return json.dumps(result, ensure_ascii=False)

    try:
        client = _get_java_client()

        # 先查找成员的 role，用于 Java API 的 rid 参数
        team_result = await client.safe_call(
            "/itmp/pmProjectMemberService/findPmProjectMemberList",
            {"pmProjectId": project_id, "page": 0, "size": 100}
        )
        members = team_result.get("content", [])
        member_role = None
        for m in members:
            if m.get("userId") == name or m.get("name") == name or m.get("nickname") == name:
                member_role = m.get("role", "")
                break

        if not member_role:
            return json.dumps({"success": False, "message": f"未找到成员: {name}"}, ensure_ascii=False)

        java_result = await client.safe_call(
            "/portal/abikoleManagerService/updateDuty",
            {"rid": member_role, "ids": [duty_name], "pid": project_id, "checked": checked}
        )

        if java_result.get("success"):
            updated = await client.safe_call(
                "/itmp/pmProjectMemberService/findPmProjectMemberList",
                {"pmProjectId": project_id, "page": 0, "size": 100}
            )
            if "content" in updated:
                updated["content"] = [_normalize_team_member(m) for m in updated["content"]]
            java_result["data"] = updated

        return json.dumps(java_result, ensure_ascii=False)
    except JavaClientError as e:
        return json.dumps({"success": False, "message": e.message, "detail": e.detail}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] update_member_duty 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)


# ============================================================
# Tool 8: 查询用户信息
# ============================================================
@mcp.tool()
async def get_user_info(user_id: str) -> str:
    """
    根据用户ID查询用户基本信息。
    参数: user_id - 用户ID
    """
    if DEV_MODE:
        result = get_user_by_id(user_id)
        return json.dumps(result, ensure_ascii=False)

    try:
        client = _get_java_client()
        java_result = await client.safe_call(
            "/itmp/pmProjectmanagement/findUserById",
            {"id": user_id}
        )
        return _wrap_read_response(java_result)
    except JavaClientError as e:
        return json.dumps({"success": False, "message": e.message, "detail": e.detail}, ensure_ascii=False)
    except Exception as e:
        import traceback
        print(f"[MCP] 未预期的错误: {e}")
        traceback.print_exc()
        return json.dumps({"success": False, "message": f"服务器内部错误: {str(e)}"}, ensure_ascii=False)


# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    mode_label = "开发模式(Python mock)" if DEV_MODE else "生产模式(Java HTTP → H2)"
    print("=" * 60)
    print(f"MCP HTTP Server (Java Data Gateway)")
    print(f"模式: {mode_label}")
    print(f"监听: http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}")
    print(f"SDK: FastMCP (Streamable HTTP)")
    if not DEV_MODE:
        from mcp_server.config import JAVA_BASE_URL
        print(f"Java 服务: {JAVA_BASE_URL}")
    print("=" * 60)

    mcp.run(transport="streamable-http")
