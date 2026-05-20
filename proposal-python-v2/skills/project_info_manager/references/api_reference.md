# API工具参考文档

本文档详细说明 `project_info_manager` Skill可使用的所有MCP工具。

## 工具列表

### 1. get_project_info

**功能**：获取项目基本信息

**参数**：
- `project_id` (string, 必需)：项目ID

**返回**：
```json
{
  "success": true,
  "data": {
    "id": "项目ID",
    "name": "项目名称",
    "dept": "立项申请部门",
    "level": "项目级别(S/A/B/C)",
    "baseReq": "基准需求编号",
    "reqDept": "需求相关部门",
    "changeReq": "变更需求编号",
    "pmName": "项目经理姓名",
    "productNo": "产品编号",
    "productName": "产品名称"
  }
}
```

**使用示例**：
```python
result = await get_project_info(project_id="P001")
```

**注意事项**：
- 所有用户都可以调用此工具
- 返回的数据中，只有 `productNo` 和 `productName` 可编辑

---

### 2. update_project_info

**功能**：修改项目基本信息（仅限productNo和productName）

**参数**：
- `project_id` (string, 必需)：项目ID
- `productNo` (string, 可选)：新产品编号
- `productName` (string, 可选)：新产品名称

**返回**：
```json
{
  "success": true,
  "message": "更新成功",
  "data": {
    "productNo": "ABC-2026-001",
    "productName": "新核心系统"
  }
}
```

**使用示例**：
```python
result = await update_project_info(
    project_id="P001",
    productNo="ABC-2026-001",
    productName="新核心系统"
)
```

**权限要求**：
- 只有 `isPM=true` 的用户可以调用
- 如果权限不足，返回：`{"success": false, "message": "权限拒绝：只有项目经理可以修改项目信息"}`

**可编辑字段**：
- ✅ `productNo` — 产品编号
- ✅ `productName` — 产品名称

**不可编辑字段**（调用时会报错）：
- ❌ `id` — 项目编号
- ❌ `name` — 项目名称
- ❌ `dept` — 立项申请部门
- ❌ `level` — 项目级别
- ❌ `baseReq` — 基准需求编号
- ❌ `reqDept` — 需求相关部门
- ❌ `changeReq` — 变更需求编号
- ❌ `pmName` — 项目经理姓名

---

### 3. get_team_members_list

**功能**：获取团队成员列表

**参数**：
- `project_id` (string, 必需)：项目ID

**返回**：
```json
{
  "success": true,
  "data": [
    {
      "name": "张三",
      "role": "项目经理",
      "responsibilities": {
        "需求评审": True,
        "产品设计": False,
        "开发排期": True,
        "测试验收": False,
        "产品发布": True
      }
    },
    {
      "name": "李四",
      "role": "开发工程师",
      "responsibilities": {
        "需求评审": False,
        "产品设计": False,
        "开发排期": False,
        "测试验收": False,
        "产品发布": False
      }
    }
  ]
}
```

**使用示例**：
```python
result = await get_team_members_list(project_id="P001")
```

**注意事项**：
- 所有用户都可以调用此工具
- `responsibilities` 是一个字典，key是职责名称，value是布尔值（是否勾选）

---

### 4. add_team_member

**功能**：添加新成员

**参数**：
- `project_id` (string, 必需)：项目ID
- `name` (string, 必需)：成员姓名
- `role` (string, 必需)：成员角色

**返回**：
```json
{
  "success": true,
  "message": "成员添加成功",
  "data": {
    "name": "王五",
    "role": "测试工程师",
    "responsibilities": {
      "需求评审": False,
      "产品设计": False,
      "开发排期": False,
      "测试验收": False,
      "产品发布": False
    }
  }
}
```

**使用示例**：
```python
result = await add_team_member(
    project_id="P001",
    name="王五",
    role="测试工程师"
)
```

**权限要求**：
- 只有 `isPM=true` 的用户可以调用

**错误情况**：
- 成员已存在：返回 `{"success": false, "message": "成员王五已在团队中"}`

---

### 5. update_member_duty

**功能**：勾选/取消职责

**参数**：
- `project_id` (string, 必需)：项目ID
- `name` (string, 必需)：成员姓名
- `duty_name` (string, 必需)：职责名称
- `checked` (boolean, 必需)：是否勾选

**返回**：
```json
{
  "success": true,
  "message": "职责更新成功",
  "data": {
    "name": "张三",
    "duty_name": "需求评审",
    "checked": true
  }
}
```

**使用示例**：
```python
# 勾选职责
result = await update_member_duty(
    project_id="P001",
    name="张三",
    duty_name="需求评审",
    checked=True
)

# 取消职责
result = await update_member_duty(
    project_id="P001",
    name="张三",
    duty_name="需求评审",
    checked=False
)
```

**权限要求**：
- 只有 `isPM=true` 的用户可以调用

**可选职责列表**：
- 需求评审
- 产品设计
- 开发排期
- 测试验收
- 产品发布

---

## 错误处理

### 常见错误类型

1. **权限不足**：
```json
{
  "success": false,
  "message": "权限拒绝：只有项目经理可以修改项目信息"
}
```

2. **参数缺失**：
```json
{
  "success": false,
  "message": "缺少必需参数：project_id"
}
```

3. **成员不存在**：
```json
{
  "success": false,
  "message": "未找到成员XXX"
}
```

4. **成员已存在**：
```json
{
  "success": false,
  "message": "成员XXX已在团队中"
}
```

5. **字段不可编辑**：
```json
{
  "success": false,
  "message": "抱歉，系统规定除【产品编号】和【产品名称】外，其他项目基本信息不可在此修改。"
}
```

6. **成员不可删除或修改**：
```json
{
  "success": false,
  "message": "团队成员不可删除或修改角色，只能通过勾选/取消职责来管理。"
}
```

### 重试策略

- 工具调用失败后，**不要自动重试超过2次**
- 如果连续失败，报告错误详情给用户
- 提示用户检查网络连接或联系管理员

---

## 使用示例

### 示例1：查看项目信息

```python
# 步骤1：获取项目基本信息
project_result = await get_project_info(project_id="P001")
if project_result["success"]:
    project_data = project_result["data"]
    print(f"项目名称：{project_data['name']}")
    print(f"产品编号：{project_data['productNo']}")
    print(f"产品名称：{project_data['productName']}")

# 步骤2：获取团队成员列表
team_result = await get_team_members_list(project_id="P001")
if team_result["success"]:
    team_data = team_result["data"]
    for member in team_data:
        print(f"成员：{member['name']}，角色：{member['role']}")
```

### 示例2：修改产品编号

```python
# 修改产品编号
result = await update_project_info(
    project_id="P001",
    productNo="ABC-2026-001"
)

if result["success"]:
    print("✅ 已更新：将【产品编号】修改为 ABC-2026-001")
else:
    print(f"❌ 更新失败：{result['message']}")
```

### 示例3：添加新成员

```python
# 添加新成员
result = await add_team_member(
    project_id="P001",
    name="王五",
    role="测试工程师"
)

if result["success"]:
    print("✅ 已添加成员：王五，角色：测试工程师")
else:
    print(f"❌ 添加失败：{result['message']}")
```

---

## 参考资料

- [AgentScope官方文档 - Skills](https://doc.agentscope.io/zh_CN/tutorial/task_agent_skill.html)
- [MCP协议规范](https://spec.modelcontextprotocol.io/)
- [项目方案书AI自动填写系统 - 设计文档](../05-MCP服务设计文档.md)
