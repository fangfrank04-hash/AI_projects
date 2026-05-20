"""
Mock 数据定义 + 内存CRUD操作
开发模式（DEV_MODE=true）下直接操作内存数据，不连接真实 Java 服务

数据结构对齐 Java 接口返回：
- get_project → 对标 findProjectById 返回值
- get_team_members → 对标 findPmProjectMemberList 返回值（分页）
- update_project → 对标 updatePmProject（仅限 productNo/productName）
- add_member / delete_member / update_member_roles / update_duty 对标对应 Java 接口
"""
import copy
import uuid

# ============================================================
# 初始模板数据
# ============================================================

MOCK_PROJECT = {
    "id": "PJ-202603-S-068",
    "name": "验证主表单01221",
    "dept": "信息科技部",
    "baseReq": "BD-2026-0078",
    "level": "S级",
    "productNo": "",
    "productName": "",
    "reqDept": "信息科技部",
    "changeReq": "",
    "pmName": "陈杰"
}

MOCK_TEAM_PAGE = {
    "content": [
        {
            "id": "M001",
            "userId": "U001",
            "userName": "张伟",
            "roleName": "产品经理",
            "roleIds": ["R001"],
            "responsibilities": [
                {"name": "产品发布", "checked": True},
                {"name": "业务方案可行性分析", "checked": True}
            ]
        },
        {
            "id": "M002",
            "userId": "U002",
            "userName": "陈杰",
            "roleName": "项目经理",
            "roleIds": ["R002"],
            "responsibilities": [
                {"name": "产品发布", "checked": True},
                {"name": "项目立项", "checked": True}
            ]
        },
        {
            "id": "M003",
            "userId": "U003",
            "userName": "李明",
            "roleName": "开发负责人",
            "roleIds": ["R003"],
            "responsibilities": [
                {"name": "技术方案设计", "checked": True},
                {"name": "编码实现", "checked": True},
                {"name": "代码评审", "checked": True}
            ]
        },
        {
            "id": "M004",
            "userId": "U004",
            "userName": "王芳",
            "roleName": "测试负责人",
            "roleIds": ["R004"],
            "responsibilities": [
                {"name": "测试用例设计", "checked": True},
                {"name": "功能测试", "checked": True},
                {"name": "回归测试", "checked": True}
            ]
        },
        {
            "id": "M005",
            "userId": "U005",
            "userName": "马伟华",
            "roleName": "开发工程师",
            "roleIds": ["R005"],
            "responsibilities": [
                {"name": "编码实现", "checked": True},
                {"name": "代码评审", "checked": True},
                {"name": "技术方案设计", "checked": True}
            ]
        }
    ],
    "totalElements": 5,
    "totalPages": 1,
    "number": 0,
    "size": 10
}

MOCK_USER = {
    "id": "U001",
    "name": "张伟",
    "deptName": "信息科技部",
    "email": "zhangwei@example.com"
}

# ============================================================
# 可用的全部职责列表（供新增成员时参考）
# ============================================================

ALL_DUTIES = [
    "产品发布", "业务方案可行性分析", "项目立项",
    "项目方案制定与发布", "项目计划管控", "上线/投产业务验证",
    "项目结项", "里程碑节点评审", "项目后评价",
    "结项和后评价", "需求评估", "制定项目实施方案",
    "撰写系统操作手册", "研发与测试交付件评审", "组织系统测试"
]

# ============================================================
# 内存运行状态（深拷贝初始数据，服务重启后重置）
# ============================================================

_project_state = copy.deepcopy(MOCK_PROJECT)
_team_state = copy.deepcopy(MOCK_TEAM_PAGE["content"])


def _reset_state():
    """重置内存状态为初始数据（用于测试）"""
    global _project_state, _team_state
    _project_state = copy.deepcopy(MOCK_PROJECT)
    _team_state = copy.deepcopy(MOCK_TEAM_PAGE["content"])


def _new_id():
    return str(uuid.uuid4())[:8]


def _paginate(content: list, page: int = 0, size: int = 10) -> dict:
    """将列表包装为分页格式，对齐 Java Page 结构"""
    total = len(content)
    total_pages = max(1, (total + size - 1) // size)
    start = page * size
    end = start + size
    return {
        "content": content[start:end],
        "totalElements": total,
        "totalPages": total_pages,
        "number": page,
        "size": size
    }


# ============================================================
# CRUD 操作（对标 Java 接口返回值）
# ============================================================

def get_project(project_id: str) -> dict:
    """获取项目基本信息"""
    return {"success": True, "data": copy.deepcopy(_project_state)}


def update_project(data: dict) -> dict:
    """
    更新项目基本信息（仅限 productNo 和 productName）
    其余字段透传但不会被修改
    """
    allowed = ["productNo", "productName"]
    changed = []
    for key in allowed:
        if key in data and data[key] != _project_state.get(key, ""):
            _project_state[key] = data[key]
            changed.append(key)
    if changed:
        return {
            "success": True,
            "message": f"已更新: {', '.join(changed)}",
            "data": copy.deepcopy(_project_state)
        }
    return {"success": True, "message": "无变更", "data": copy.deepcopy(_project_state)}


def get_team_members(project_id: str) -> dict:
    """获取项目团队成员列表（分页）"""
    return {"success": True, "data": _paginate(copy.deepcopy(_team_state))}


def add_member(project_id: str, name: str, role: str, responsibilities: list = None) -> dict:
    """添加团队成员"""
    for m in _team_state:
        if m["userName"] == name:
            return {"success": False, "message": f"成员 {name} 已存在"}
    member = {
        "id": _new_id(),
        "userId": _new_id(),
        "userName": name,
        "roleName": role,
        "roleIds": [],
        "responsibilities": responsibilities or []
    }
    _team_state.append(member)
    return {"success": True, "message": f"已添加成员: {name}（{role}）", "data": copy.deepcopy(_team_state)}


def delete_member(project_id: str, name: str) -> dict:
    """删除团队成员（已禁用：团队成员不可删除）"""
    return {"success": False, "message": "团队成员不可删除，只能通过勾选/取消职责来管理。如需调整人员，请联系管理员。"}


def update_member_roles(project_id: str, name: str, new_role: str) -> dict:
    """更新团队成员角色名称（已禁用：角色不可修改）"""
    return {"success": False, "message": "团队角色由系统维护，不可在此修改。"}


def update_duty(project_id: str, name: str, duty_name: str, checked: bool) -> dict:
    """为团队成员勾选/取消勾选职责（取消时保留职责条目，checked=false）"""
    for m in _team_state:
        if m["userName"] == name:
            resp = m["responsibilities"]
            # 兼容旧格式：字符串列表 → 对象列表
            if resp and isinstance(resp[0], str):
                resp = [{"name": r, "checked": True} for r in resp]
                m["responsibilities"] = resp
            # 查找并更新 checked 状态
            for r in resp:
                if r["name"] == duty_name:
                    r["checked"] = checked
                    break
            else:
                # 职责不在列表中，追加新条目
                resp.append({"name": duty_name, "checked": checked})
            action = "勾选" if checked else "取消"
            return {
                "success": True,
                "message": f"已为 {name} {action}职责: {duty_name}",
                "data": copy.deepcopy(_team_state)
            }
    return {"success": False, "message": f"未找到成员: {name}"}


def get_user_by_id(user_id: str) -> dict:
    """根据用户ID获取用户信息"""
    return {"success": True, "data": copy.deepcopy(MOCK_USER)}
