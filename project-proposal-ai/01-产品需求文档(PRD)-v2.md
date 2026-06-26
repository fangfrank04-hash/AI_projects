# 一体化项目与架构管理平台 - AI项目方案书自动填写及检查

## 产品需求文档 (PRD) v2.1 — Python主导架构

**文档状态**：已定稿，可直接用于开发
**编写日期**：2026-05-07
**编写人**：许清楚（产品经理）
**适用范围**：前端(React) / Python AI后台(FastAPI+agentscope) / Java数据服务层
**目标读者**：AI编码助手 + 全栈开发者

---

## 一、需求概述

### 1.1 业务背景

一体化项目与架构管理平台前期已完成一期和二期建设，于2025年上线多批次优化，并实现了信创改造，在需求、项目、架构、数据标准、IT知识产权等维度实现了全面推广使用。

随着各领域制度要求和使用体验反馈，为进一步增强平台整体服务能力，全面提升用户使用效率，拟基于大模型技术增加**项目方案书自动填写及检查**功能。

### 1.2 架构重大调整说明（v2核心变更）

v1.0采用"Java主导"架构：前端 → Java Spring Boot → Python FastAPI → 通义千问。该架构下Java承担全部业务逻辑与数据层，Python仅作为纯AI服务被Java调用。

**v2.0反转为"Python主导"架构**：

```
前端(React) ←SSE流式→ Python FastAPI(+agentscope) ←MCP→ Java数据服务
                                      ↓
                                  通义千问(qwen-max)
```

**反转原因**：
- AI Agent需要自主决策（判断查数据还是调LLM），Python层更适合作为智能编排中心
- 减少Java与Python之间的往返通信延迟
- 前端直接获取SSE流式响应，用户体验更流畅
- Python通过MCP协议标准化调用Java数据服务，职责边界更清晰

### 1.3 项目目标

在现有平台基础上，增加AI聊天机器人，辅助项目经理自动填写项目方案书。本次v2.0版本**仅聚焦步骤1**：
- 项目基本信息查询与编辑（仅限productNo和productName）
- 项目团队查询与职责维护
- 通过AI对话修改项目基本信息和团队成员
- 一键回填到主页面

**预期效果**：项目基本信息与团队职责的确认，从手动填写缩短至AI辅助下的3-5分钟。

### 1.4 需求来源

金科公司 - 2026年四季度优化需求

### 1.5 v2.0明确不做（V3再做）

| 不做项 | 说明 |
|--------|------|
| 步骤2（管控方案） | V3实现 |
| 步骤3（进度计划） | V3实现 |
| 步骤4（资源计划） | V3实现 |
| 步骤5（质量保证计划） | V3实现 |
| 方案书检查功能 | V3实现 |
| 历史数据参考 | V3实现 |
| 知识库规则动态加载 | V3实现 |
| 生产环境SSO/LDAP认证 | V3实现 |

---

## 二、用户角色与权限

| 角色 | 职责 | 权限 |
|------|------|------|
| **项目经理(PM)** | 负责项目整体管理 | 维护团队信息、启动AI填写、编辑productNo/productName、确认回填 |
| **项目成员** | 参与项目执行 | 查看方案书、查看AI聊天内容、无编辑权限 |
| **系统管理员** | 维护系统配置 | 查看操作日志、配置MCP连接 |

**关键权限规则**：
- 只有项目经理可以操作AI聊天机器人的编辑功能
- 非项目经理打开方案书页面时，AI聊天入口显示，但编辑功能禁用（输入框置灰、表格字段readonly、一键回填按钮禁用）
- 本地开发阶段全部使用mock用户，不接入真实鉴权

---

## 三、功能需求

### 3.1 AI聊天机器人入口

**需求编号**：FR-001
**功能描述**：在【项目实施管理 - 项目方案书】页面右下角，新增聊天机器人悬浮入口。
**交互细节**：
- 入口为圆形悬浮按钮，带机器人图标（红色渐变背景）
- 点击后弹出聊天对话框（支持拖拽移动位置）
- 对话框支持最大化/最小化
- 刷新页面后对话框默认打开，保持连续体验

### 3.2 聊天基础交互（问候 + 信息检查）

**需求编号**：FR-002
**功能描述**：聊天对话框弹出后，机器人主动发送问候信息，并展示项目基本信息与团队职责的预览卡片。
**交互流程**：
```
机器人首次问候：
"您好，{项目经理姓名}！我是您的AI项目助手。
目前支持为您自动解析与填写【项目基本信息】及【团队职责】。"

[延迟1秒后]
→ 展示预览卡片（项目基本信息 + 项目团队）
→ 提示："请确认以下信息，修改后点一键回填同步至主页面表单。"
```

**信息检查规则**：
- 若项目团队为空 → 提示"项目团队尚未维护，请先联系项目经理完成团队录入"，预览卡片中团队表格显示空状态
- 若项目信息完整 → 正常展示预览卡片

### 3.3 步骤1：项目基本信息与团队职责确认

**需求编号**：FR-003
**功能描述**：采用**预览确认 + 一键回填**方式，完成项目基本信息与团队职责的维护。

#### 3.3.1 项目基本信息展示与编辑

**数据来源**：Python通过MCP调用Java接口 `findProjectById` 获取

**展示字段**：

| 字段 | 说明 | 可编辑 |
|------|------|--------|
| 项目编号 | 如PJ-202603-S-068 | 否（readonly灰色显示） |
| 项目名称 | 如"验证主表单01221" | 否（readonly灰色显示） |
| 立项申请部门 | 如"信息科技部" | 否（readonly灰色显示） |
| 基准需求编号 | 如BD-2026-0078 | 否（readonly灰色显示） |
| 变更需求编号 | - | 否（readonly灰色显示） |
| 项目控制策略类型 | S级/A级/B级/C级 | 否（readonly灰色显示） |
| **产品编号** | - | **是**（可输入框，PM可编辑） |
| **产品名称** | - | **是**（可输入框，PM可编辑） |
| 需求相关部门 | - | 否（readonly灰色显示） |

**编辑规则**：
- 只有项目经理（isCurrentUserPM=true）可编辑productNo和productName
- 非项目经理所有字段均为readonly

#### 3.3.2 项目团队展示与编辑

**数据来源**：Python通过MCP调用Java接口 `findPmProjectMemberList` 获取

**展示字段**：

| 字段 | 说明 | 可编辑 |
|------|------|--------|
| 序号 | 自增 | 否 |
| 项目角色 | 产品经理、项目经理等 | 否（readonly，由Java系统维护） |
| 人员 | 具体姓名 | 否（readonly，由Java系统维护） |
| 职责 | 复选框列表 | 是（PM可勾选/取消） |

**职责数据结构**：
```json
[
  {"name": "产品发布", "checked": true},
  {"name": "业务方案可行性分析", "checked": true},
  {"name": "项目立项", "checked": false}
]
```

**编辑规则**：
- 角色和人员字段由Java系统维护，AI聊天内只读展示
- 职责字段通过复选框勾选/取消，只有PM可操作
- 增删改人员通过AI对话指令实现（见3.4节）

#### 3.3.3 一键回填功能

**需求编号**：FR-004
**功能描述**：预览卡片下方设置【确认并一键回填】按钮。
**回填规则**：
- 点击后，将draftProjectData和draftTeamData同步到主页面状态（setProjectData / setTeamData）
- 通过SSE发送 `fillback` 指令给Python，Python通过MCP调用Java的 `updatePmProject` 和 `updateDuty` 接口持久化
- 回填成功后，前端主页面数据实时刷新
- 机器人发送确认消息："回填成功！项目基本信息与团队数据已同步至左侧表单。"

### 3.4 智能对话与指令修改

**需求编号**：FR-005
**功能描述**：用户可通过聊天框输入自然语言指令，指导AI修改预览内容。
**规则**：
- 指令仅影响当前预览内容（草稿状态），需点击【一键回填】后才持久化
- 指令修改后，预览卡片实时更新
- 用户可多次输入指令，直到满意后确认回填
- 支持日常对话（问候、自我介绍等），AI以自然语言回复

#### 3.4.1 支持的指令类型

**1. 修改项目基本信息（仅限productNo/productName）**

示例指令：
- "产品编号改成ABC-2026-001"
- "把产品名称改成新核心系统"

**拦截规则**：
- 若指令涉及不可编辑字段（如项目名称、立项部门、项目级别等）
- AI回复："抱歉，系统规定除【产品编号】和【产品名称】外，其他项目基本信息不可在此修改。"

**2. 修改团队成员职责（勾选/取消）**

示例指令：
- "给产品经理增加需求评审职责"
- "取消项目经理的产品发布职责"
- "把测试负责人的职责改一下"

**3. 增删改团队成员**

示例指令：
- "新增一个架构师张三"
- "删除成员李四"
- "把王五的角色改成开发负责人"

**AI处理流程**：
```
用户输入指令
  ↓
Python ReActAgent接收
  ↓
意图识别（修改项目信息 / 修改团队 / 日常对话）
  ↓
[修改项目信息] → 校验字段可编辑性 → 更新draftProjectData → 返回SSE: {type:"update_project", data:{...}}
[修改团队] → 调用MCP工具（add_member/delete_member/update_duty等）→ 更新draftTeamData → 返回SSE: {type:"update_team", data:{...}}
[日常对话] → 调用通义千问生成回复 → 返回SSE: {type:"text", content:"..."}
```

#### 3.4.2 SSE流式消息格式

Python通过SSE向前端推送以下事件类型：

| 事件类型 | 说明 | 前端处理 |
|----------|------|----------|
| `text` | AI自然语言回复 | 追加到聊天消息列表 |
| `update_project` | 项目基本信息更新 | 更新draftProjectData，预览卡片刷新 |
| `update_team` | 团队数据更新 | 更新draftTeamData，预览卡片刷新 |
| `error` | 错误提示 | 显示红色错误消息 |
| `fillback_complete` | 回填完成确认 | 显示成功提示，刷新主页面 |

#### 3.4.3 输入框Placeholder动态提示

根据当前上下文，输入框placeholder动态变化：
- 默认："输入指令，如：修改产品编号为XXX..."
- 当用户正在编辑时："继续输入指令，或点击一键回填..."

---

## 四、非功能需求

### 4.1 性能需求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| SSE首包响应 | < 1秒 | 用户发送指令到收到第一条SSE事件 |
| AI流式输出 | 实时 | LLM生成内容逐字流式返回 |
| 数据查询响应 | < 2秒 | MCP调用Java接口获取项目/团队数据 |
| 一键回填响应 | < 2秒 | 从点击到主页面刷新 |
| 页面加载时间 | < 2秒 | 方案书主页面首屏 |

### 4.2 SSE流式需求

| 需求 | 说明 |
|------|------|
| 连接稳定性 | SSE连接断开后前端自动重连（最多3次，间隔1s/2s/4s） |
| 心跳机制 | 每30秒发送一次ping事件，保持连接活跃 |
| 消息顺序 | 保证消息按生成顺序到达前端 |
| 数据完整性 | 每条SSE消息包含完整的数据快照，前端可直接覆盖更新 |

### 4.3 可用性需求

| 指标 | 目标值 |
|------|--------|
| 系统可用性 | 99.5% |
| 数据持久化 | 100%不丢失（通过Java接口保证） |
| 错误恢复 | 支持对话重试、SSE重连 |

### 4.4 安全需求（本地开发阶段简化）

| 需求 | 说明 |
|------|------|
| 认证 | 本地开发使用mock用户，不接入SSO/LDAP |
| 授权 | 前端通过isCurrentUserPM控制编辑权限 |
| 传输加密 | 本地开发允许HTTP |
| 数据隔离 | mock数据隔离，不访问真实项目数据 |

### 4.5 扩展性需求

| 需求 | 说明 |
|------|------|
| LLM切换 | 支持通义千问qwen-max/qwen-plus切换 |
| MCP工具扩展 | 新增Java接口可通过MCP快速接入 |
| 步骤扩展 | V3时通过agentscope Workflow扩展步骤2-5 |

---

## 五、新架构设计

### 5.1 Python主导三服务架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         前端层 (React 18)                            │
│  ┌─────────────┐  ┌─────────────────────┐  ┌───────────────────┐   │
│  │ 方案书页面  │  │ AIChatbot           │  │ EventSource(SSE)  │   │
│  │ (已有页面)  │  │ (聊天+预览卡片)     │  │ 连接 /api/chat/   │   │
│  └─────────────┘  │  - 项目基本信息展示  │  │ stream            │   │
│                   │  - 团队职责表格      │  └───────────────────┘   │
│                   │  - 一键回填按钮      │                          │
│                   └─────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ SSE流式 (text/event-stream)
┌─────────────────────────────────────────────────────────────────────┐
│              Python AI后台 (FastAPI + agentscope) - 业务主导          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ReActAgent                                                │   │
│  │  ├─ DashScopeChatModel (qwen-max)                         │   │
│  │  ├─ DashScopeChatFormatter                                │   │
│  │  ├─ InMemoryMemory                                        │   │
│  │  └─ Toolkit                                               │   │
│  │       ├─ get_project_info                                 │   │
│  │       ├─ get_team_members                                 │   │
│  │       ├─ get_user_by_id                                   │   │
│  │       ├─ update_project                                   │   │
│  │       ├─ add_member                                       │   │
│  │       ├─ delete_member                                    │   │
│  │       ├─ update_member_roles                              │   │
│  │       └─ update_duty                                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐   │
│  │ /api/chat/stream│  │ agentscope.mcp  │  │ SKILL.md         │   │
│  │ SSE端点         │  │ .HttpStateless  │  │ (团队职责维护)   │   │
│  │                 │  │ Client          │  │ 加载到Toolkit    │   │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ MCP协议 (HTTP Stateless)
┌─────────────────────────────────────────────────────────────────────┐
│              Java数据服务层 (Spring Boot) - 纯数据服务                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 统一入口：POST /portal/RestAction.invoke.do?url=xxx        │   │
│  │                                                             │   │
│  │ 项目基本信息：                                              │   │
│  │   查询：/itmp/pmProjectService/findProjectById              │   │
│  │   编辑：/itmp/pmProjectService/updatePmProject              │   │
│  │                                                             │   │
│  │ 项目团队：                                                  │   │
│  │   查询：/itmp/pmProjectMemberService/findPmProjectMemberList│   │
│  │   查询用户：/itmp/pmProjectmanagement/findUserById          │   │
│  │   添加：/itmp/pmProjectMemberService/createPmProjectMembers │   │
│  │   删除：/itmp/pmProjectMemberService/deletePmProjectMembers │   │
│  │   编辑角色：/itmp/pmProjectMemberService/updateMemberRoles  │   │
│  │   编辑职责：/portal/abikoleManagerService/updateDuty        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 数据流说明

```
用户打开方案书页面
  ↓
前端建立SSE连接：EventSource → GET /api/chat/stream?projectId=xxx
  ↓
Python接收连接，ReActAgent初始化：
  1. 调用MCP工具 get_project_info → Java返回项目基本信息
  2. 调用MCP工具 get_team_members → Java返回团队列表
  3. 通过SSE推送 preview 事件 → 前端展示预览卡片
  ↓
用户在聊天框输入指令："把产品编号改成ABC-001"
  ↓
Python ReActAgent决策：
  - 意图识别 → 修改项目信息
  - 校验可编辑性 → productNo允许编辑
  - 调用MCP工具 update_project → Java保存
  - 通过SSE推送 update_project 事件 → 前端更新预览卡片
  ↓
用户点击【一键回填】
  ↓
前端发送 fillback 指令 via SSE
  ↓
Python调用MCP工具批量持久化（updatePmProject + updateDuty）
  ↓
Python推送 fillback_complete 事件 → 前端刷新主页面
```

### 5.3 关键原则

| 原则 | 说明 |
|------|------|
| **Python主导** | 所有业务编排、AI决策、会话管理在Python端 |
| **Java纯数据服务** | Java仅通过MCP暴露数据CRUD接口，不承载业务逻辑 |
| **前端只连Python** | 前端通过SSE与Python通信，不直接调用Java |
| **流式体验** | 所有AI交互通过SSE流式返回，用户实时看到进度 |
| **配置驱动** | 团队职责规则通过SKILL.md加载到Toolkit，可热更新 |

---

## 六、接口清单

### 6.1 前端 ↔ Python（SSE端点）

| 方法 | 路径 | 说明 |
|------|------|------|
| **GET** | **`/api/chat/stream`** | **核心SSE端点**，建立流式连接，接收所有AI事件 |

#### SSE连接参数

```
GET /api/chat/stream?projectId=PJ-202603-S-068&userName=陈杰&isPM=true
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| projectId | string | 是 | 项目编号 |
| userName | string | 是 | 当前用户姓名 |
| isPM | boolean | 是 | 是否项目经理 |

#### SSE事件类型（Server → Client）

| 事件名 | 数据格式 | 说明 |
|--------|----------|------|
| `connected` | `{"sessionId": "xxx", "status": "ok"}` | 连接建立成功 |
| `preview` | `{"projectData": {...}, "teamData": [...]}` | 初始预览数据 |
| `text` | `{"content": "AI回复文本"}` | AI自然语言回复 |
| `update_project` | `{"projectData": {...}}` | 项目信息更新 |
| `update_team` | `{"teamData": [...]}` | 团队数据更新 |
| `fillback_complete` | `{"success": true, "message": "..."}` | 回填完成 |
| `error` | `{"message": "错误信息"}` | 错误提示 |
| `ping` | `{"time": 1234567890}` | 心跳包 |

#### 客户端发送消息（Client → Server via SSE POST）

| 方法 | 路径 | 说明 |
|------|------|------|
| **POST** | **`/api/chat/message`** | 发送用户指令 |

**请求体**：
```json
{
  "sessionId": "xxx",
  "message": "把产品编号改成ABC-001",
  "projectId": "PJ-202603-S-068"
}
```

### 6.2 Python ↔ Java-MCP（工具列表）

Python通过 `agentscope.mcp.HttpStatelessClient` 连接本地MCP Server，MCP Server转发调用Java数据服务。

| MCP工具名 | 对应Java接口 | 参数 | 返回值 |
|-----------|-------------|------|--------|
| `get_project_info` | `/itmp/pmProjectService/findProjectById` | `{"id":"项目ID"}` | ProjectData对象 |
| `update_project` | `/itmp/pmProjectService/updatePmProject` | `{"id":"...", "name":"...", "dept":"...", "baseReq":"...", "changeReq":"...", "level":"...", "productNo":"...", "productName":"...", "reqDept":"...", "pmName":"..."}` | 更新结果 |
| `get_team_members` | `/itmp/pmProjectMemberService/findPmProjectMemberList` | `{"pmProjectId":"...", "nickname":"...", "roleIds":["..."], "pageable":{"page":0,"size":10}}` | 分页团队成员列表 |
| `get_user_by_id` | `/itmp/pmProjectmanagement/findUserById` | `{"id":"..."}` | 用户对象 |
| `add_member` | `/itmp/pmProjectMemberService/createPmProjectMembers` | `{"pmProjectId":"...", "userIds":["..."]}` | 添加结果 |
| `delete_member` | `/itmp/pmProjectMemberService/deletePmProjectMembers` | `{"pmProjectId":"...", "userIds":["..."], "ids":["..."]}` | 删除结果 |
| `update_member_roles` | `/itmp/pmProjectMemberService/updateMemberRoles` | `{"id":"...", "userId":"...", "projectId":"...", "roleIds":["..."]}` | 更新结果 |
| `update_duty` | `/portal/abikoleManagerService/updateDuty` | `{"rid":"角色ID", "ids":["编辑数据的ID列表"], "pid":"项目ID"}` | 更新结果 |

**Java统一入口格式**：
```
POST http://25.50.238.23:8088/portal/RestAction.invoke.do?url={接口路径}
Content-Type: application/x-www-form-urlencoded

param={"id":"PJ-202603-S-068",...}
```

**本地开发Mock约定**：
- MCP Server在本地开发模式下返回mock数据
- 不调用真实Java服务（IP: 25.50.238.23）
- Mock数据与前端当前mock数据结构一致

---

## 七、数据字典

### 7.1 项目基本信息 (ProjectData)

| 字段 | 类型 | 说明 | 可编辑 |
|------|------|------|--------|
| id | string | 项目编号，如PJ-202603-S-068 | 否 |
| name | string | 项目名称 | 否 |
| dept | string | 立项申请部门 | 否 |
| baseReq | string | 基准需求编号 | 否 |
| changeReq | string | 变更需求编号 | 否 |
| level | string | 项目控制策略类型：S级/A级/B级/C级 | 否 |
| **productNo** | string | **产品编号** | **是（仅PM）** |
| **productName** | string | **产品名称** | **是（仅PM）** |
| reqDept | string | 需求相关部门 | 否 |
| pmName | string | 项目经理姓名 | 否 |
| proposalBackground | string | 方案书背景说明 | 否（V3使用） |
| proposalScope | string | 方案书范围说明 | 否（V3使用） |
| status | string | 项目状态，默认"待确认" | 否（V3使用） |
| createdAt | datetime | 创建时间 | 否 |
| updatedAt | datetime | 更新时间 | 否 |

### 7.2 团队成员 (TeamMember)

| 字段 | 类型 | 说明 | 可编辑 |
|------|------|------|--------|
| id | string/number | 成员记录ID | 否 |
| userId | string | 用户ID | 否 |
| nickname | string | 用户昵称/姓名 | 否 |
| pmProjectId | string | 所属项目ID | 否 |
| role | string | 项目角色名称，如产品经理 | 否 |
| roleIds | array | 角色ID列表 | 否（通过updateMemberRoles修改） |
| responsibilities | array | 职责列表，复选框形式 | 是（仅PM） |
| createdAt | datetime | 创建时间 | 否 |

### 7.3 职责项 (Responsibility)

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 职责名称，如"产品发布" |
| checked | boolean | 是否勾选 |

### 7.4 SSE消息事件 (SSEEvent)

| 字段 | 类型 | 说明 |
|------|------|------|
| event | string | 事件类型：connected/preview/text/update_project/update_team/error/ping |
| data | object | 事件数据，根据event类型变化 |

### 7.5 Java接口参数说明

#### 项目基本信息接口

| 接口路径 | 请求方式 | 参数 | 返回值 |
|----------|----------|------|--------|
| `/itmp/pmProjectService/findProjectById` | POST | `{"id":"项目ID"}` | ProjectData对象 |
| `/itmp/pmProjectService/updatePmProject` | POST | `{"id":"...", "name":"...", "dept":"...", "baseReq":"...", "changeReq":"...", "level":"...", "productNo":"...", "productName":"...", "reqDept":"...", "pmName":"..."}` | 更新结果 |

#### 项目团队接口

| 接口路径 | 请求方式 | 参数 | 返回值 |
|----------|----------|------|--------|
| `/itmp/pmProjectMemberService/findPmProjectMemberList` | POST | `{"pmProjectId":"...", "nickname":"...", "roleIds":["..."], "pageable":{"page":0,"size":10}}` | 分页团队成员列表 |
| `/itmp/pmProjectmanagement/findUserById` | POST | `{"id":"..."}` | 用户对象 |
| `/itmp/pmProjectMemberService/createPmProjectMembers` | POST | `{"pmProjectId":"...", "userIds":["..."]}` | 添加结果 |
| `/itmp/pmProjectMemberService/deletePmProjectMembers` | POST | `{"pmProjectId":"...", "userIds":["..."], "ids":["..."]}` | 删除结果 |
| `/itmp/pmProjectMemberService/updateMemberRoles` | POST | `{"id":"...", "userId":"...", "projectId":"...", "roleIds":["..."]}` | 更新结果 |

#### 项目方案书-团队职责接口

| 接口路径 | 请求方式 | 参数 | 返回值 |
|----------|----------|------|--------|
| `/portal/abikoleManagerService/updateDuty` | POST | `{"rid":"角色ID", "ids":["编辑数据的ID列表"], "pid":"项目ID"}` | 更新结果 |

#### 关联项目接口（V3）

| 接口路径 | 请求方式 | 参数 | 返回值 |
|----------|----------|------|--------|
| `/itmp/pmProjectmanagement/findRelProject` | POST | `{"rel":"...", "projectId":"..."}` | 关联项目列表 |

#### 阶段活动接口（V3）

| 接口路径 | 请求方式 | 参数 | 返回值 |
|----------|----------|------|--------|
| `/itmp/pmProjectPlanService/findProjectProgramPlanTreeByProjectId` | POST | `{"projectId":"..."}` | 阶段活动树 |
| `/itmp/pmProjectPlanService/savePlanTaskCutResult` | POST | `{"tasks":[{"taskNo":"...", "cutResult":"1", "cutResultExplain":"..."}]}` | 保存结果 |

#### 交付物接口（V3）

| 接口路径 | 请求方式 | 参数 | 返回值 |
|----------|----------|------|--------|
| `/itmp/pmProjectPlanService/findAssetByProjectProgramPage` | POST | `{"rel":"...", "projectId":"..."}` | 交付物分页列表 |
| `/itmp/pmProjectPlanService/savePlanTaskRel` | POST | `{"rel":[{"id":"...", "cutResult":"1", "cutResultExplain":"..."}]}` | 保存结果 |

### 7.6 关联项目 (RelatedProject) — V3

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 关联项目ID |
| name | string | 关联项目名称 |
| rel | string | 关联类型 |
| projectId | string | 主项目ID |

### 7.7 阶段活动 (PhaseActivity) — V3

| 字段 | 类型 | 说明 |
|------|------|------|
| taskNo | string | 活动编号 |
| taskName | string | 活动名称 |
| parentId | string | 父节点ID |
| cutResult | string | 裁剪结果：1-保留/0-裁剪 |
| cutResultExplain | string | 裁剪说明 |
| children | array | 子活动列表 |

### 7.8 交付物 (Deliverable) — V3

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 交付物ID |
| name | string | 交付物名称 |
| rel | string | 关联类型 |
| projectId | string | 项目ID |
| cutResult | string | 裁剪结果 |
| cutResultExplain | string | 裁剪说明 |

---

## 八、验收标准

### 8.1 功能验收

| 验收项 | 验收标准 |
|--------|----------|
| AI入口 | 方案书页面右下角显示AI聊天入口，点击弹出对话框 |
| 信息检查 | 未维护团队信息时，机器人正确提示 |
| 预览卡片 | 正确展示项目基本信息表格 + 团队职责表格，字段与可编辑性符合设计 |
| 项目信息编辑 | PM可编辑productNo和productName，非PM不可编辑 |
| 团队职责编辑 | PM可勾选/取消职责复选框，非PM不可操作 |
| 指令修改-项目信息 | 输入"产品编号改成XXX"，预览卡片实时更新productNo |
| 指令修改-拦截 | 输入"项目名称改成XXX"，AI回复拦截提示 |
| 指令修改-团队 | 输入"新增架构师张三"，团队表格增加一行 |
| 指令修改-职责 | 输入"给产品经理增加XXX职责"，复选框列表更新 |
| 日常对话 | 输入"你好"，AI以自然语言回复，不修改数据 |
| 一键回填 | 点击后数据正确回填到主页面，刷新不丢失 |
| SSE流式 | AI回复逐字流式显示，无卡顿 |
| 权限控制 | 非项目经理编辑功能禁用，提示友好 |

### 8.2 性能验收

| 验收项 | 验收标准 |
|--------|----------|
| SSE首包 | 用户发送指令到收到第一条SSE事件 < 1秒 |
| 数据查询 | MCP调用Java接口获取项目/团队数据 < 2秒 |
| 回填响应 | 从点击回填到主页面刷新 < 2秒 |
| SSE重连 | 断线后自动重连，最多3次 |

### 8.3 架构验收

| 验收项 | 验收标准 |
|--------|----------|
| Python主导 | 前端只连接Python SSE，不直接调Java |
| MCP调用 | Python通过agentscope.mcp.HttpStatelessClient调用Java数据服务 |
| Agent决策 | ReActAgent能自主决策：查数据→MCP工具，理解意图→通义千问 |
| Skill加载 | 团队职责维护SKILL.md成功加载到Toolkit |
| Mock数据 | 本地开发全部使用mock，不依赖真实Java服务 |

---

## 九、风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| LLM响应不稳定 | 高 | 增加重试机制（最多3次），超时降级返回提示 |
| LLM意图识别错误 | 中 | 明确Prompt约束，增加拦截模板 |
| SSE连接断开 | 中 | 前端自动重连，最多3次，重连后恢复会话状态 |
| Java MCP调用失败 | 高 | 本地开发使用mock数据，不阻塞前端演示 |
| MCP协议兼容性 | 中 | 使用agentscope官方HttpStatelessClient实现 |

---

## 十、附录

### 10.1 术语表

| 术语 | 说明 |
|------|------|
| SSE | Server-Sent Events，服务器推送事件，用于流式通信 |
| MCP | Model Context Protocol，模型上下文协议，标准化AI与数据服务的连接 |
| ReActAgent | agentscope中的推理-行动Agent，能自主决策调用工具或LLM |
| Toolkit | agentscope中的工具集，加载MCP工具和Skill |
| SKILL.md | agentscope技能定义文件，描述团队职责维护的业务规则 |
| 回填 | AI生成的草稿数据写入主表单并持久化 |
| Mock | 本地开发使用模拟数据，不连接真实服务 |

### 10.2 技术栈汇总

| 层级 | 技术 | 版本/型号 |
|------|------|----------|
| 前端 | React + Vite + EventSource | 18 / 5.x |
| Python AI | FastAPI + agentscope | 0.110+ / 最新 |
| LLM | 通义千问 | qwen-max |
| MCP Client | agentscope.mcp.HttpStatelessClient | 内置 |
| Java数据服务 | Spring Boot（已有） | 3.2.x |
| 数据库(开发) | H2 | 2.2.x |
| 数据库(生产) | MySQL | 8.0+ |
| 缓存 | InMemoryMemory | agentscope内置 |

### 10.3 与v1.0的关键差异对照

| 维度 | v1.0 (Java主导) | v2.0 (Python主导) |
|------|-----------------|-------------------|
| 前端通信协议 | HTTP REST (请求-响应) | SSE流式 (服务器推送) |
| 前端直接连接 | Java Spring Boot | Python FastAPI |
| Java角色 | 业务主导 + 数据层 | 纯数据服务层 |
| Python角色 | 纯AI服务（被Java调用） | 业务编排 + AI决策中心 |
| AI决策位置 | Java Service层 | Python ReActAgent |
| 数据查询方式 | Java查库后传给Python | Python通过MCP调Java |
| 会话管理 | Java + Python各自管理 | Python InMemoryMemory统一管理 |
| 步骤范围 | 5步全做 | 仅步骤1 |
| 认证 | SSO/LDAP + JWT | Mock用户（本地开发） |

---

## 十一、版本历史

| 版本 | 日期 | 修改人 | 变更内容 |
|------|------|--------|----------|
| v2.0 | 2026-05-07 | 许清楚 | 初稿：Python主导架构，聚焦步骤1（项目基本信息+团队职责） |
| v2.1 | 2026-05-07 | 许清楚 | 基于Java接口图片更新数据字典：补充ProjectData完整字段、TeamMember字段（userId/nickname等）、新增Java接口参数说明、新增V3数据结构（关联项目/阶段活动/交付物）、更新MCP工具列表为8个工具、修正updateDuty接口路径 |

---

**文档结束**
