# 错误处理手册

本文档详细说明 `project_info_manager` Skill在执行过程中可能遇到的错误以及处理方式。

## 错误分类

### 1. 权限错误

#### 1.1 非PM用户尝试修改数据

**错误代码**：`PERMISSION_DENIED_NOT_PM`

**错误信息**：
```json
{
  "success": false,
  "message": "权限拒绝：只有项目经理可以修改项目信息"
}
```

**触发场景**：
- 非PM用户调用 `update_project_info`
- 非PM用户调用 `add_team_member`
- 非PM用户调用 `update_member_duty`

**处理逻辑**：
1. 检查 `isPM` 标志
2. 如果 `isPM=false`，直接返回权限拒绝错误
3. **不调用MCP工具**，避免无效请求

**代码示例**：
```python
async def tool_update_project_info(project_id: str, productNo: str = "", productName: str = ""):
    """更新项目基本信息（仅限productNo和productName，其余字段不可修改）"""
    if not self.is_pm:  # ✅ 权限校验
        return ToolResponse([TextBlock(type="text", text=json.dumps(
            {"success": False, "message": "权限拒绝：只有项目经理可以修改项目信息"}, ensure_ascii=False))])
    # 继续执...
```

**用户提示**：
```
❌ 权限拒绝：您非项目经理，只能查看数据。
```

---

#### 1.2 尝试修改不可编辑字段

**错误代码**：`FIELD_NOT_EDITABLE`

**错误信息**：
```json
{
  "success": false,
  "message": "抱歉，系统规定除【产品编号】和【产品名称】外，其他项目基本信息不可在此修改。"
}
```

**触发场景**：
- 用户要求修改 `name`（项目名称）
- 用户要求修改 `dept`（立项部门）
- 用户要求修改 `level`（项目级别）
- 用户要求修改 `baseReq`（基准需求编号）
- 用户要求修改 `reqDept`（需求部门）
- 用户要求修改 `changeReq`（变更需求编号）
- 用户要求修改 `pmName`（项目经理）

**处理逻辑**：
1. 解析用户意图，提取要修改的字段名
2. 检查字段白名单（`productNo` 和 `productName`）
3. 如果字段不在白名单中，拦截并回复
4. **不调用MCP工具**

**用户提示**：
```
💡 抱歉，系统规定除【产品编号】和【产品名称】外，其他项目基本信息不可在此修改。如需修改，请联系管理员。
```

---

### 2. 参数错误

#### 2.1 缺少必需参数

**错误代码**：`MISSING_REQUIRED_PARAMETER`

**错误信息**：
```json
{
  "success": false,
  "message": "缺少必需参数：project_id"
}
```

**触发场景**：
- 调用任何工具时缺少 `project_id`
- 调用 `add_team_member` 时缺少 `name` 或 `role`
- 调用 `update_member_duty` 时缺少 `duty_name` 或 `checked`

**处理逻辑**：
1. 解析用户指令，提取参数
2. 检查必需参数是否齐全
3. 如果缺失，追问用户确认

**用户提示**：
```
请确认：您要将【哪个字段】修改为什么值？
```

**代码示例**：
```python
# 用户指令："把产品编号改成什么？"
# 解析后发现缺少 productNo 的新值
# 追问确认
return "请确认：您要将【产品编号】修改为什么值？"
```

---

#### 2.2 参数格式错误

**错误代码**：`INVALID_PARAMETER_FORMAT`

**错误信息**：
```json
{
  "success": false,
  "message": "参数格式错误：checked 必须是 true 或 false"
}
```

**触发场景**：
- `checked` 参数不是布尔值
- `project_id` 为空字符串
- `name` 包含特殊字符

**处理逻辑**：
1. 在调用工具前验证参数格式
2. 如果格式错误，返回错误信息
3. **不调用MCP工具**

---

### 3. 数据错误

#### 3.1 成员不存在

**错误代码**：`MEMBER_NOT_FOUND`

**错误信息**：
```json
{
  "success": false,
  "message": "未找到成员 XXX"
}
```

**触发场景**：
- 调用 `update_member_duty` 时，成员不存在

**处理逻辑**：
1. 先调用 `get_team_members_list` 获取最新团队列表
2. 检查成员是否存在
3. 如果不存在，返回错误提示

**用户提示**：
```
未找到成员 XXX，请确认姓名是否正确。
```

---

#### 3.2 成员已存在

**错误代码**：`MEMBER_ALREADY_EXISTS`

**错误信息**：
```json
{
  "success": false,
  "message": "成员 XXX 已在团队中"
}
```

**触发场景**：
- 调用 `add_team_member` 时，成员已存在

**处理逻辑**：
1. 先调用 `get_team_members_list` 获取最新团队列表
2. 检查成员是否已存在
3. 如果已存在，返回错误提示

**用户提示**：
```
成员 XXX 已在团队中。
```

---

### 4. 系统错误

#### 4.1 MCP工具调用失败

**错误代码**：`MCP_TOOL_CALL_FAILED`

**错误信息**：
```json
{
  "success": false,
  "message": "操作失败：MCP工具调用失败 - 连接超时"
}
```

**触发场景**：
- MCP Server不可用
- 网络连接超时
- Java服务不可用

**处理逻辑**：
1. 捕获异常
2. 返回错误详情
3. **不自动重试超过2次**

**代码示例**：
```python
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
```

**用户提示**：
```
❌ 操作失败：MCP工具调用失败 - 连接超时。
请稍后重试，或联系管理员。
```

---

#### 4.2 JSON解析失败

**错误代码**：`JSON_PARSE_FAILED`

**错误信息**：
```json
{
  "success": false,
  "message": "操作失败：返回数据格式错误"
}
```

**触发场景**：
- MCP工具返回的数据不是有效的JSON
- 网络传输过程中数据损坏

**处理逻辑**：
1. 尝试解析JSON
2. 如果解析失败，返回错误提示
3. 记录详细日志供管理员排查

---

## 重试策略

### 重试规则

1. **最大重试次数**：2次
2. **重试间隔**：1秒
3. **重试条件**：
   - ✅ 网络连接超时
   - ✅ 临时服务不可用
   - ❌ 参数错误（不重试）
   - ❌ 权限错误（不重试）
   - ❌ 数据不存在（不重试）

### 重试示例代码

```python
import asyncio

async def call_mcp_tool_with_retry(tool_func, max_retries=2, *args, **kwargs):
    """带重试的MCP工具调用"""
    for i in range(max_retries + 1):
        try:
            result = await tool_func(*args, **kwargs)
            return result
        except Exception as e:
            if i < max_retries:
                print(f"[Agent] 工具调用失败，第{i+1}次重试：{e}")
                await asyncio.sleep(1)  # 等待1秒
                continue
            else:
                print(f"[Agent] 工具调用失败，已达到最大重试次数：{e}")
                raise e
```

---

## 用户提示模板

### 成功提示

```
✅ 已更新：将【产品编号】修改为 ABC-2026-001。请确认后点击一键回填。
```

```
✅ 已添加成员：张三，角色：开发工程师。
```

```
✅ 已更新：为张三勾选【需求评审】职责。
```

---

### 错误提示

```
❌ 权限拒绝：您非项目经理，只能查看数据。
```

```
💡 抱歉，系统规定除【产品编号】和【产品名称】外，其他项目基本信息不可在此修改。如需修改，请联系管理员。
```

```
⚠️ 未找到成员 XXX，请确认姓名是否正确。
```

```
⚠️ 成员 XXX 已在团队中。
```

```
❌ 操作失败：MCP工具调用失败 - 连接超时。
请稍后重试，或联系管理员。
```

---

### 追问提示

```
请确认：您要将【产品编号】修改为什么值？
```

```
请确认：您要添加的成员姓名和角色是什么？
```

---

## 日志记录规范

### 日志级别

1. **INFO**：正常操作记录
   ```
   [Agent] Skill loaded: project_info_manager
   [Agent] MCP read tools registered (auto-discovered)
   [Agent] 更新项目信息成功：project_id=P001, productNo=ABC-2026-001
   ```

2. **WARNING**：潜在问题记录
   ```
   [Agent] Warning: Skill not found: xxx
   [Agent] 成员 XXX 已在团队中，跳过添加
   ```

3. **ERROR**：错误信息记录
   ```
   [Agent] tool_update_project_info 调用失败: Connection timeout
   [Agent] JSON解析失败：Invalid JSON format
   ```

---

## 参考资料

- [MCP工具详细文档](api_reference.md)
- [字段约束说明](field_constraints.md)
- [AgentScope官方文档 - 错误处理](https://doc.agentscope.io/)
