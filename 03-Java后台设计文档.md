# Java数据服务层接口规范 - 项目方案书AI自动填写系统

**文档状态**：已定稿，可直接用于开发
**编写日期**：2026-05-07
**编写人**：寇豆码（工程师）
**适用范围**：Java数据服务层（Spring Boot）/ MCP Server
**目标读者**：AI编码助手 + 后端开发者

---

## 一、技术选型

| 技术项 | 选型 | 版本 | 说明 |
|--------|------|------|------|
| 框架 | Spring Boot | 3.2.x | 提供REST数据接口 |
| JDK | Java 17 | LTS | 长期支持版本 |
| 数据库(开发) | H2 | 2.2.x | 嵌入式，本地开发无需安装 |
| 数据库(生产) | MySQL | 8.0+ | 企业级数据库 |
| 数据库连接池 | HikariCP | 内置 | 性能最佳 |
| ORM | Spring Data JPA | 内置 | 简化数据库操作 |
| 构建工具 | Maven | 3.9.x | 依赖管理 |

**选型理由**：
- Spring Boot 3.x 提供稳定的REST数据服务
- H2用于本地开发，MySQL用于生产，通过Spring Profile切换
- JPA自动建表，减少SQL维护成本

**重要说明**：
- Java在v2.0中仅作为**纯数据服务层**，不承载业务逻辑和AI决策
- 所有业务编排、AI交互、会话管理均在Python端完成
- Python通过MCP协议调用本文档定义的Java接口

---

## 二、架构定位

### 2.1 v2.0架构中的Java角色

```
前端(React)
    |
    ▼ SSE流式
Python FastAPI (+agentscope ReActAgent)
    |
    ▼ MCP协议 (HTTP Stateless)
MCP Server (Python)
    |
    ▼ HTTP POST x-www-form-urlencoded
Java数据服务层 (Spring Boot)
    |
    ▼ JPA/Hibernate
H2(开发) / MySQL(生产)
```

### 2.2 职责边界

| 层级 | 职责 | 不做的职责 |
|------|------|-----------|
| **Java数据服务层** | 提供项目/团队/阶段活动/交付物的CRUD接口 | 业务逻辑、AI决策、Prompt组装 |
| **Python FastAPI** | ReActAgent编排、LLM调用、SSE流式输出 | 直接操作数据库 |
| **MCP Server** | 协议转换（MCP JSON-RPC <> Java HTTP） | 业务逻辑 |
| **前端** | React页面渲染、EventSource接收SSE | 直接调用Java接口 |

### 2.3 统一入口

Java所有接口通过单一入口暴露：

```
POST /portal/RestAction.invoke.do?url={接口路径}
```

Python MCP Server通过此入口调用所有Java数据服务。

---

## 三、统一入口规范

### 3.1 请求格式

| 项 | 说明 |
|----|------|
| **URL** | `POST http://{host}:{port}/portal/RestAction.invoke.do?url={接口路径}` |
| **Content-Type** | `application/x-www-form-urlencoded` |
| **请求体** | `param={JSON字符串}` |

### 3.2 请求示例

```http
POST http://localhost:8088/portal/RestAction.invoke.do?url=/itmp/pmProjectService/findProjectById
Content-Type: application/x-www-form-urlencoded

param={"id":"PJ-202603-S-068"}
```

### 3.3 响应格式

Java返回JSON格式数据：

```json
{
  "id": "PJ-202603-S-068",
  "name": "验证主表单01221",
  "dept": "信息科技部",
  ...
}
```

### 3.4 认证方式

| 阶段 | 认证方式 |
|------|----------|
| 本地开发 | 无需Token/Cookie，直接调用 |
| 后续接入内网 | 补充认证格式（待定） |

---

## 四、接口清单

### 4.1 项目基本信息接口

#### 4.1.1 查询项目基本信息

| 属性 | 值 |
|------|-----|
| **接口名称** | findProjectById |
| **接口路径** | `/itmp/pmProjectService/findProjectById` |
| **HTTP方法** | POST |
| **说明** | 根据项目ID查询项目基本信息 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | string | 是 | 项目编号，如PJ-202603-S-068 |

**请求示例**：
```json
{"id":"PJ-202603-S-068"}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 项目编号 |
| name | string | 项目名称 |
| dept | string | 立项申请部门 |
| baseReq | string | 基准需求编号 |
| changeReq | string | 变更需求编号 |
| level | string | 项目控制策略类型：S级/A级/B级/C级 |
| productNo | string | 产品编号（v2可编辑） |
| productName | string | 产品名称（v2可编辑） |
| reqDept | string | 需求相关部门 |
| pmName | string | 项目经理姓名 |
| proposalBackground | string | 方案书背景说明（V3使用） |
| proposalScope | string | 方案书范围说明（V3使用） |
| status | string | 项目状态 |
| createdAt | datetime | 创建时间 |
| updatedAt | datetime | 更新时间 |

**响应示例**：
```json
{
  "id": "PJ-202603-S-068",
  "name": "验证主表单01221",
  "dept": "信息科技部",
  "baseReq": "BD-2026-0078",
  "changeReq": "",
  "level": "S级",
  "productNo": "",
  "productName": "",
  "reqDept": "信息科技部",
  "pmName": "陈杰",
  "proposalBackground": null,
  "proposalScope": null,
  "status": "待确认",
  "createdAt": "2026-03-15T10:30:00",
  "updatedAt": "2026-03-20T14:22:00"
}
```

**错误码**：

| 错误码 | 说明 |
|--------|------|
| 404 | 项目不存在 |
| 500 | 系统内部错误 |

---

#### 4.1.2 编辑项目基本信息

| 属性 | 值 |
|------|-----|
| **接口名称** | updatePmProject |
| **接口路径** | `/itmp/pmProjectService/updatePmProject` |
| **HTTP方法** | POST |
| **说明** | 更新项目基本信息。v2仅允许修改productNo和productName，其余字段透传 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | string | 是 | 项目编号 |
| name | string | 是 | 项目名称（透传） |
| dept | string | 否 | 立项申请部门（透传） |
| baseReq | string | 否 | 基准需求编号（透传） |
| changeReq | string | 否 | 变更需求编号（透传） |
| level | string | 否 | 项目级别（透传） |
| productNo | string | 否 | 产品编号（v2可编辑） |
| productName | string | 否 | 产品名称（v2可编辑） |
| reqDept | string | 否 | 需求相关部门（透传） |
| pmName | string | 否 | 项目经理姓名（透传） |

**请求示例**：
```json
{
  "id": "PJ-202603-S-068",
  "name": "验证主表单01221",
  "dept": "信息科技部",
  "baseReq": "BD-2026-0078",
  "changeReq": "",
  "level": "S级",
  "productNo": "ABC-2026-001",
  "productName": "新核心系统",
  "reqDept": "信息科技部",
  "pmName": "陈杰"
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| message | string | 操作结果消息 |

**响应示例**：
```json
{
  "success": true,
  "message": "更新成功"
}
```

---

### 4.2 项目团队接口

#### 4.2.1 查询项目团队成员列表

| 属性 | 值 |
|------|-----|
| **接口名称** | findPmProjectMemberList |
| **接口路径** | `/itmp/pmProjectMemberService/findPmProjectMemberList` |
| **HTTP方法** | POST |
| **说明** | 分页查询项目团队成员列表 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pmProjectId | string | 是 | 项目编号 |
| nickname | string | 否 | 用户昵称/姓名（模糊查询） |
| roleIds | array | 否 | 角色ID列表，如["R001","R002"] |
| pageable | object | 否 | 分页参数 |
| pageable.page | integer | 否 | 页码，从0开始，默认0 |
| pageable.size | integer | 否 | 每页条数，默认10 |

**请求示例**：
```json
{
  "pmProjectId": "PJ-202603-S-068",
  "nickname": "",
  "roleIds": [],
  "pageable": {
    "page": 0,
    "size": 10
  }
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| content | array | 成员列表 |
| content[].id | string/number | 成员记录ID |
| content[].userId | string | 用户ID |
| content[].nickname | string | 用户昵称/姓名 |
| content[].roleName | string | 角色名称 |
| content[].roleIds | array | 角色ID列表 |
| content[].responsibilities | array | 职责列表（字符串数组） |
| totalElements | integer | 总记录数 |
| totalPages | integer | 总页数 |
| number | integer | 当前页码 |
| size | integer | 每页大小 |

**响应示例**：
```json
{
  "content": [
    {
      "id": "M001",
      "userId": "U001",
      "nickname": "张伟",
      "roleName": "产品经理",
      "roleIds": ["R001"],
      "responsibilities": ["产品发布", "业务方案可行性分析"]
    },
    {
      "id": "M002",
      "userId": "U002",
      "nickname": "陈杰",
      "roleName": "项目经理",
      "roleIds": ["R002"],
      "responsibilities": ["产品发布", "项目立项"]
    }
  ],
  "totalElements": 2,
  "totalPages": 1,
  "number": 0,
  "size": 10
}
```

---

#### 4.2.2 查询用户基本信息

| 属性 | 值 |
|------|-----|
| **接口名称** | findUserById |
| **接口路径** | `/itmp/pmProjectmanagement/findUserById` |
| **HTTP方法** | POST |
| **说明** | 根据用户ID查询用户基本信息，用于添加成员前确认用户存在 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | string | 是 | 用户ID |

**请求示例**：
```json
{"id":"U001"}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 用户ID |
| name | string | 用户姓名 |
| deptName | string | 所属部门 |
| email | string | 邮箱 |

**响应示例**：
```json
{
  "id": "U001",
  "name": "张伟",
  "deptName": "信息科技部",
  "email": "zhangwei@example.com"
}
```

---

#### 4.2.3 添加团队成员

| 属性 | 值 |
|------|-----|
| **接口名称** | createPmProjectMembers |
| **接口路径** | `/itmp/pmProjectMemberService/createPmProjectMembers` |
| **HTTP方法** | POST |
| **说明** | 向项目批量添加团队成员 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pmProjectId | string | 是 | 项目编号 |
| userIds | array | 是 | 待添加的用户ID列表 |

**请求示例**：
```json
{
  "pmProjectId": "PJ-202603-S-068",
  "userIds": ["U003", "U004"]
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| message | string | 操作结果消息 |
| data | object | 附加数据（可选） |

---

#### 4.2.4 删除团队成员

| 属性 | 值 |
|------|-----|
| **接口名称** | deletePmProjectMembers |
| **接口路径** | `/itmp/pmProjectMemberService/deletePmProjectMembers` |
| **HTTP方法** | POST |
| **说明** | 从项目删除团队成员。ids和userIds至少提供一个 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pmProjectId | string | 是 | 项目编号 |
| userIds | array | 否 | 用户ID列表 |
| ids | array | 否 | 成员记录ID列表 |

**请求示例**：
```json
{
  "pmProjectId": "PJ-202603-S-068",
  "userIds": ["U003"],
  "ids": ["M003"]
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| message | string | 操作结果消息 |

---

#### 4.2.5 编辑成员角色

| 属性 | 值 |
|------|-----|
| **接口名称** | updateMemberRoles |
| **接口路径** | `/itmp/pmProjectMemberService/updateMemberRoles` |
| **HTTP方法** | POST |
| **说明** | 修改项目成员的角色分配 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | string | 是 | 成员记录ID |
| userId | string | 是 | 用户ID |
| projectId | string | 是 | 项目编号 |
| roleIds | array | 是 | 角色ID列表 |

**请求示例**：
```json
{
  "id": "M002",
  "userId": "U002",
  "projectId": "PJ-202603-S-068",
  "roleIds": ["R002", "R003"]
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| message | string | 操作结果消息 |

---

### 4.3 团队职责接口

#### 4.3.1 更新团队职责

| 属性 | 值 |
|------|-----|
| **接口名称** | updateDuty |
| **接口路径** | `/portal/abikoleManagerService/updateDuty` |
| **HTTP方法** | POST |
| **说明** | 更新团队成员的职责分配。rid为角色ID，ids为编辑数据的ID列表，pid为项目编号 |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| rid | string | 是 | 角色ID |
| ids | array | 是 | 编辑数据的ID列表（职责ID列表） |
| pid | string | 是 | 项目编号 |

**请求示例**：
```json
{
  "rid": "R001",
  "ids": ["D001", "D002"],
  "pid": "PJ-202603-S-068"
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| message | string | 操作结果消息 |

---

### 4.4 关联项目接口（V3使用）

> **注意**：以下接口为V3阶段使用，v2.0预留接口定义。

#### 4.4.1 查询关联项目列表

| 属性 | 值 |
|------|-----|
| **接口名称** | findRelProject |
| **接口路径** | `/itmp/pmProjectmanagement/findRelProject` |
| **HTTP方法** | POST |
| **说明** | 查询项目的关联项目列表（V3使用） |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| rel | string | 否 | 关联类型 |
| projectId | string | 是 | 项目编号 |

**请求示例**：
```json
{
  "rel": "",
  "projectId": "PJ-202603-S-068"
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 关联项目ID |
| name | string | 关联项目名称 |
| rel | string | 关联类型 |
| projectId | string | 主项目ID |

---

### 4.5 阶段活动接口（V3使用）

> **注意**：以下接口为V3阶段使用，v2.0预留接口定义。

#### 4.5.1 查询阶段活动树

| 属性 | 值 |
|------|-----|
| **接口名称** | findProjectProgramPlanTreeByProjectId |
| **接口路径** | `/itmp/pmProjectPlanService/findProjectProgramPlanTreeByProjectId` |
| **HTTP方法** | POST |
| **说明** | 根据项目ID查询阶段活动树（V3使用） |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| projectId | string | 是 | 项目编号 |

**请求示例**：
```json
{"projectId":"PJ-202603-S-068"}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| taskNo | string | 活动编号 |
| taskName | string | 活动名称 |
| parentId | string | 父节点ID |
| cutResult | string | 裁剪结果：1-保留/0-裁剪 |
| cutResultExplain | string | 裁剪说明 |
| children | array | 子活动列表 |

---

#### 4.5.2 保存阶段活动裁剪结果

| 属性 | 值 |
|------|-----|
| **接口名称** | savePlanTaskCutResult |
| **接口路径** | `/itmp/pmProjectPlanService/savePlanTaskCutResult` |
| **HTTP方法** | POST |
| **说明** | 保存阶段活动裁剪结果（V3使用） |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| tasks | array | 是 | 活动裁剪列表 |
| tasks[].taskNo | string | 是 | 活动编号 |
| tasks[].cutResult | string | 是 | 裁剪结果：1-保留/0-裁剪 |
| tasks[].cutResultExplain | string | 否 | 裁剪说明 |

**请求示例**：
```json
{
  "tasks": [
    {
      "taskNo": "T001",
      "cutResult": "1",
      "cutResultExplain": "必须保留"
    },
    {
      "taskNo": "T002",
      "cutResult": "0",
      "cutResultExplain": "不需要"
    }
  ]
}
```

---

### 4.6 交付物接口（V3使用）

> **注意**：以下接口为V3阶段使用，v2.0预留接口定义。

#### 4.6.1 查询交付物分页列表

| 属性 | 值 |
|------|-----|
| **接口名称** | findAssetByProjectProgramPage |
| **接口路径** | `/itmp/pmProjectPlanService/findAssetByProjectProgramPage` |
| **HTTP方法** | POST |
| **说明** | 查询项目交付物分页列表（V3使用） |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| rel | string | 否 | 关联类型 |
| projectId | string | 是 | 项目编号 |

**请求示例**：
```json
{
  "rel": "",
  "projectId": "PJ-202603-S-068"
}
```

**返回字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 交付物ID |
| name | string | 交付物名称 |
| rel | string | 关联类型 |
| projectId | string | 项目ID |
| cutResult | string | 裁剪结果 |
| cutResultExplain | string | 裁剪说明 |

---

#### 4.6.2 保存交付物裁剪结果

| 属性 | 值 |
|------|-----|
| **接口名称** | savePlanTaskRel |
| **接口路径** | `/itmp/pmProjectPlanService/savePlanTaskRel` |
| **HTTP方法** | POST |
| **说明** | 保存交付物裁剪结果（V3使用） |

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| rel | array | 是 | 交付物裁剪列表 |
| rel[].id | string | 是 | 交付物ID |
| rel[].cutResult | string | 是 | 裁剪结果：1-保留/0-裁剪 |
| rel[].cutResultExplain | string | 否 | 裁剪说明 |

**请求示例**：
```json
{
  "rel": [
    {
      "id": "A001",
      "cutResult": "1",
      "cutResultExplain": "必须保留"
    }
  ]
}
```

---

### 4.7 接口汇总表

| 分类 | 接口名称 | 接口路径 | v2/v3 |
|------|----------|----------|-------|
| 项目基本信息 | 查询项目 | `/itmp/pmProjectService/findProjectById` | v2 |
| 项目基本信息 | 编辑项目 | `/itmp/pmProjectService/updatePmProject` | v2 |
| 项目团队 | 查询成员列表 | `/itmp/pmProjectMemberService/findPmProjectMemberList` | v2 |
| 项目团队 | 查询用户 | `/itmp/pmProjectmanagement/findUserById` | v2 |
| 项目团队 | 添加成员 | `/itmp/pmProjectMemberService/createPmProjectMembers` | v2 |
| 项目团队 | 删除成员 | `/itmp/pmProjectMemberService/deletePmProjectMembers` | v2 |
| 项目团队 | 编辑角色 | `/itmp/pmProjectMemberService/updateMemberRoles` | v2 |
| 团队职责 | 更新职责 | `/portal/abikoleManagerService/updateDuty` | v2 |
| 关联项目 | 查询关联项目 | `/itmp/pmProjectmanagement/findRelProject` | **V3** |
| 阶段活动 | 查询活动树 | `/itmp/pmProjectPlanService/findProjectProgramPlanTreeByProjectId` | **V3** |
| 阶段活动 | 保存裁剪结果 | `/itmp/pmProjectPlanService/savePlanTaskCutResult` | **V3** |
| 交付物 | 查询交付物 | `/itmp/pmProjectPlanService/findAssetByProjectProgramPage` | **V3** |
| 交付物 | 保存裁剪结果 | `/itmp/pmProjectPlanService/savePlanTaskRel` | **V3** |

---

## 五、数据模型

### 5.1 实体关系图

```
+-----------+       +---------------+       +------------------+
| projects  |1-----*| team_members  |       | proposals        |
+-----------+       +---------------+       +------------------+
| id (PK)   |       | id (PK)       |       | id (PK)          |
| name      |       | project_id FK |       | project_id FK UQ |
| dept      |       | role          |       | current_step     |
| base_req  |       | name          |       | completed_steps  |
| level     |       | responsibilities      | status           |
| product_no|       | created_at    |       | confirmed_by     |
| product_na|       +---------------+       | confirmed_at     |
| req_dept  |                             | created_at       |
| change_req|                             | updated_at       |
| pm_name   |                             +------------------+
| status    |                                      |1
| created_at|                                      |
| updated_at|                              +-------+--------+
+-----------+                              | proposal_steps |
                                           +----------------+
                                           | id (PK)        |
                                           | proposal_id FK |
                                           | step_number    |
                                           | step_name      |
                                           | data (JSON)    |
                                           | status         |
                                           | created_at     |
                                           | updated_at     |
                                           +----------------+
```

### 5.2 项目表 (projects)

| 字段名 | 类型 | 长度 | 可空 | 说明 |
|--------|------|------|------|------|
| id | VARCHAR | 50 | 否 | 主键，项目编号 |
| name | VARCHAR | 200 | 否 | 项目名称 |
| dept | VARCHAR | 100 | 是 | 立项申请部门 |
| base_req | VARCHAR | 50 | 是 | 基准需求编号 |
| level | VARCHAR | 10 | 是 | 项目级别：S级/A级/B级/C级 |
| product_no | VARCHAR | 50 | 是 | 产品编号（v2可编辑） |
| product_name | VARCHAR | 200 | 是 | 产品名称（v2可编辑） |
| req_dept | VARCHAR | 100 | 是 | 需求相关部门 |
| change_req | VARCHAR | 50 | 是 | 变更需求编号 |
| pm_name | VARCHAR | 50 | 否 | 项目经理姓名 |
| proposal_background | TEXT | - | 是 | 方案书背景说明（V3使用） |
| proposal_scope | TEXT | - | 是 | 方案书范围说明（V3使用） |
| status | VARCHAR | 20 | 是 | 项目状态，默认"待确认" |
| created_at | TIMESTAMP | - | 是 | 创建时间 |
| updated_at | TIMESTAMP | - | 是 | 更新时间 |

**索引**：
- PRIMARY KEY (`id`)
- INDEX `idx_pm_name` (`pm_name`)

### 5.3 项目团队成员表 (team_members)

| 字段名 | 类型 | 长度 | 可空 | 说明 |
|--------|------|------|------|------|
| id | BIGINT | - | 否 | 主键，自增 |
| project_id | VARCHAR | 50 | 否 | 外键，关联projects.id |
| role | VARCHAR | 50 | 否 | 项目角色名称 |
| name | VARCHAR | 50 | 否 | 成员姓名 |
| responsibilities | TEXT | - | 是 | 职责列表（JSON格式） |
| created_at | TIMESTAMP | - | 是 | 创建时间 |

**索引**：
- PRIMARY KEY (`id`)
- INDEX `idx_project_id` (`project_id`)
- FOREIGN KEY (`project_id`) REFERENCES `projects`(`id`) ON DELETE CASCADE

### 5.4 方案书表 (proposals)

| 字段名 | 类型 | 长度 | 可空 | 说明 |
|--------|------|------|------|------|
| id | BIGINT | - | 否 | 主键，自增 |
| project_id | VARCHAR | 50 | 否 | 外键，关联projects.id，唯一 |
| current_step | INT | - | 是 | 当前步骤 1-5，默认1 |
| completed_steps | VARCHAR | 50 | 是 | 已完成步骤（JSON数组） |
| status | VARCHAR | 20 | 是 | 状态：待确认/已确认 |
| confirmed_by | VARCHAR | 50 | 是 | 确认人 |
| confirmed_at | TIMESTAMP | - | 是 | 确认时间 |
| created_at | TIMESTAMP | - | 是 | 创建时间 |
| updated_at | TIMESTAMP | - | 是 | 更新时间 |

**索引**：
- PRIMARY KEY (`id`)
- UNIQUE KEY `uk_project_id` (`project_id`)
- INDEX `idx_current_step` (`current_step`)
- FOREIGN KEY (`project_id`) REFERENCES `projects`(`id`) ON DELETE CASCADE

### 5.5 方案书步骤数据表 (proposal_steps)

| 字段名 | 类型 | 长度 | 可空 | 说明 |
|--------|------|------|------|------|
| id | BIGINT | - | 否 | 主键，自增 |
| proposal_id | BIGINT | - | 否 | 外键，关联proposals.id |
| step_number | INT | - | 否 | 步骤编号 1-5 |
| step_name | VARCHAR | 50 | 否 | 步骤名称 |
| data | TEXT | - | 否 | 步骤数据（JSON格式） |
| status | VARCHAR | 20 | 是 | 状态：草稿/已确认，默认"草稿" |
| created_at | TIMESTAMP | - | 是 | 创建时间 |
| updated_at | TIMESTAMP | - | 是 | 更新时间 |

**索引**：
- PRIMARY KEY (`id`)
- UNIQUE KEY `uk_proposal_step` (`proposal_id`, `step_number`)
- INDEX `idx_proposal_id` (`proposal_id`)
- INDEX `idx_status` (`status`)
- FOREIGN KEY (`proposal_id`) REFERENCES `proposals`(`id`) ON DELETE CASCADE

### 5.6 操作日志表 (operation_logs)

| 字段名 | 类型 | 长度 | 可空 | 说明 |
|--------|------|------|------|------|
| id | BIGINT | - | 否 | 主键，自增 |
| project_id | VARCHAR | 50 | 是 | 项目编号 |
| user_id | VARCHAR | 50 | 否 | 用户ID |
| operation | VARCHAR | 100 | 否 | 操作类型 |
| details | TEXT | - | 是 | 操作详情 |
| ip_address | VARCHAR | 50 | 是 | IP地址 |
| created_at | TIMESTAMP | - | 是 | 创建时间 |

**索引**：
- PRIMARY KEY (`id`)
- INDEX `idx_project_id` (`project_id`)
- INDEX `idx_user_id` (`user_id`)

### 5.7 JPA实体类

```java
// entity/Project.java
@Entity
@Table(name = "projects")
@Data
@JsonIgnoreProperties({"hibernateLazyInitializer", "handler"})
public class Project {
    @Id
    @Column(name = "id", length = 50)
    private String id;

    @Column(name = "name", nullable = false, length = 200)
    private String name;

    @Column(name = "dept", length = 100)
    private String dept;

    @Column(name = "base_req", length = 50)
    private String baseReq;

    @Column(name = "level", length = 10)
    private String level;

    @Column(name = "product_no", length = 50)
    private String productNo;

    @Column(name = "product_name", length = 200)
    private String productName;

    @Column(name = "req_dept", length = 100)
    private String reqDept;

    @Column(name = "change_req", length = 50)
    private String changeReq;

    @Column(name = "pm_name", nullable = false, length = 50)
    private String pmName;

    @Column(name = "proposal_background", columnDefinition = "TEXT")
    private String proposalBackground;

    @Column(name = "proposal_scope", columnDefinition = "TEXT")
    private String proposalScope;

    @Column(name = "status", length = 20)
    private String status = "待确认";

    @JsonIgnore
    @OneToMany(mappedBy = "project", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<TeamMember> teamMembers;

    @JsonIgnore
    @OneToOne(mappedBy = "project", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private Proposal proposal;

    @CreatedDate
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}
```

```java
// entity/TeamMember.java
@Entity
@Table(name = "team_members")
@Data
public class TeamMember {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @Column(name = "role", nullable = false, length = 50)
    private String role;

    @Column(name = "name", nullable = false, length = 50)
    private String name;

    @Column(name = "responsibilities", columnDefinition = "TEXT")
    @JdbcTypeCode(SqlTypes.JSON)
    private List<ResponsibilityItem> responsibilities;

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
```

```java
// entity/ResponsibilityItem.java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ResponsibilityItem {
    private String name;
    private boolean checked = true;
}
```

---

## 六、与MCP的对接说明

### 6.1 调用链路

```
Python ReActAgent
    |
    ▼ MCP Client (agentscope.mcp.HttpStatelessClient)
MCP Server (Python, Port 8001)
    |
    ▼ HTTP POST
Java数据服务层
    |
    ▼ JPA
H2 / MySQL
```

### 6.2 MCP工具与Java接口映射

| MCP工具名 | 对应Java接口路径 | 操作类型 |
|-----------|------------------|----------|
| `get_project_info` | `/itmp/pmProjectService/findProjectById` | 查询 |
| `update_project` | `/itmp/pmProjectService/updatePmProject` | 更新 |
| `get_team_members` | `/itmp/pmProjectMemberService/findPmProjectMemberList` | 查询 |
| `get_user_by_id` | `/itmp/pmProjectmanagement/findUserById` | 查询 |
| `add_members` | `/itmp/pmProjectMemberService/createPmProjectMembers` | 创建 |
| `delete_members` | `/itmp/pmProjectMemberService/deletePmProjectMembers` | 删除 |
| `update_member_roles` | `/itmp/pmProjectMemberService/updateMemberRoles` | 更新 |
| `update_duty` | `/portal/abikoleManagerService/updateDuty` | 更新 |

### 6.3 参数映射关系

MCP Tool的输入参数直接映射为Java接口的`param` JSON内容：

**示例**：MCP调用 `get_project_info(id="PJ-202603-S-068")`

| 阶段 | 格式 |
|------|------|
| MCP Tool Call | `{"id": "PJ-202603-S-068"}` |
| HTTP请求体 | `param={"id":"PJ-202603-S-068"}` |
| Java接收 | `param`参数解析为JSON对象 |

### 6.4 响应处理

| 接口类型 | Java响应 | MCP Server处理 |
|----------|----------|----------------|
| 查询类 | 直接返回JSON对象 | 原样包装为MCP TextContent |
| 修改类 | 返回`{"success":true}`或纯文本 | 统一包装为`{"success":true, "message":"操作成功"}` |
| 分页类 | 返回`content`/`totalElements`结构 | 保留原结构，不做转换 |

### 6.5 认证

| 阶段 | 认证方式 |
|------|----------|
| 本地开发 | 无需认证。MCP Server直接调用Java接口 |
| 后续接入内网 | 补充认证格式（待定）。可能在HTTP Header中传递Token |

---

## 七、本地开发说明

### 7.1 H2数据库配置

```yaml
# application-dev.yml
spring:
  datasource:
    url: jdbc:h2:file:./data/proposal_db;DB_CLOSE_ON_EXIT=FALSE;AUTO_SERVER=TRUE
    driver-class-name: org.h2.Driver
    username: sa
    password:

  jpa:
    hibernate:
      ddl-auto: update
    show-sql: true
    properties:
      hibernate:
        dialect: org.hibernate.dialect.H2Dialect
        format_sql: true

  h2:
    console:
      enabled: true
      path: /h2-console
      settings:
        web-allow-others: true
```

### 7.2 Mock数据

本地开发时，H2数据库通过`data.sql`初始化Mock数据：

```sql
-- data.sql
INSERT INTO projects (id, name, dept, base_req, level, product_no, product_name, req_dept, change_req, pm_name, status, created_at, updated_at)
VALUES ('PJ-202603-S-068', '验证主表单01221', '信息科技部', 'BD-2026-0078', 'S级', '', '', '信息科技部', '', '陈杰', '待确认', NOW(), NOW());

INSERT INTO team_members (project_id, role, name, responsibilities, created_at)
VALUES ('PJ-202603-S-068', '产品经理', '张伟', '[{"name":"产品发布","checked":true},{"name":"业务方案可行性分析","checked":true}]', NOW());

INSERT INTO team_members (project_id, role, name, responsibilities, created_at)
VALUES ('PJ-202603-S-068', '项目经理', '陈杰', '[{"name":"产品发布","checked":true},{"name":"项目立项","checked":true}]', NOW());
```

### 7.3 项目结构（v2.0精简版）

```
src/main/java/com/ccdc/proposal/
├── ProposalApplication.java          # 启动类
├── config/
│   ├── DatabaseConfig.java          # 数据库配置（H2/MySQL切换）
│   └── DataInitializer.java         # 数据初始化
├── controller/
│   └── RestActionController.java    # [新增] 统一入口控制器
├── service/
│   ├── ProjectService.java          # 项目数据服务
│   ├── TeamMemberService.java       # 团队成员数据服务
│   └── UserService.java             # 用户数据服务
├── repository/
│   ├── ProjectRepository.java
│   ├── TeamMemberRepository.java
│   └── UserRepository.java
├── entity/
│   ├── Project.java
│   ├── TeamMember.java
│   ├── ResponsibilityItem.java
│   ├── Proposal.java               # V3使用
│   ├── ProposalStep.java           # V3使用
│   └── OperationLog.java
└── dto/
    ├── ProjectData.java
    └── TeamMemberData.java

src/main/resources/
├── application.yml                   # 主配置
├── application-dev.yml               # 开发环境（H2）
├── application-prod.yml              # 生产环境（MySQL）
└── data.sql                          # 初始Mock数据
```

### 7.4 启动方式

```bash
# 开发模式（使用H2数据库）
./mvnw spring-boot:run

# 或指定配置文件
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev

# 生产模式（使用MySQL数据库）
./mvnw spring-boot:run -Dspring-boot.run.profiles=prod

# 打包
./mvnw clean package -DskipTests

# 运行jar（开发环境）
java -jar target/proposal-java-1.0.0.jar --spring.profiles.active=dev
```

### 7.5 开发环境访问

| 服务 | URL |
|------|-----|
| Java数据服务 | http://localhost:8088 |
| H2控制台 | http://localhost:8088/h2-console |
| MCP Server | http://localhost:8001/mcp |
| Python FastAPI | http://localhost:8000 |

---

## 八、全局异常处理

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusinessException(BusinessException e) {
        log.warn("业务异常: {}", e.getMessage());
        return ResponseEntity.badRequest()
                .body(new ErrorResponse("BUSINESS_ERROR", e.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleException(Exception e) {
        log.error("系统异常", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ErrorResponse("SYSTEM_ERROR", "系统繁忙，请稍后重试"));
    }
}
```

**错误响应格式**：

```json
{
  "code": "BUSINESS_ERROR",
  "message": "项目不存在"
}
```

---

## 九、版本说明

| 版本 | 日期 | 修改人 | 变更内容 |
|------|------|--------|----------|
| v2.0 | 2026-05-07 | 寇豆码 | 初稿：Java纯数据服务层接口规范，基于PRD v2.1和MCP设计文档重写 |

**关键变更说明**：
- 架构从"Java主导"反转为"Python主导"
- Java仅作为纯数据服务层，删除所有AI相关服务（AIClientService、PromptBuilder、ProposalWorkflow）
- 删除Java调用Python的说明
- 新增统一入口规范（`POST /portal/RestAction.invoke.do?url={接口路径}`）
- 接口清单按PRD v2.1第7.5节整理，标注V3使用接口
- 新增与MCP的对接说明章节
- 简化项目结构，移除不必要的Controller和Service

---

**文档结束**
