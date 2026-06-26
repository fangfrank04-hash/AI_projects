# MCP 服务设计文档

**文档状态**：已定稿，可直接用于开发  
**编写日期**：2026-05-07  
**编写人**：高见远（架构师）  
**适用范围**：MCP Server（Python）/ Java 数据服务层  
**目标读者**：AI 编码助手 + 后端开发者  
**协议版本**：MCP 2025-06-18（Streamable HTTP）  
**Python SDK 版本**：`mcp>=1.8.0`  

---

## 一、设计概述

### 1.1 MCP Server 定位

MCP Server 是 Python AI 后台与 Java 数据服务层之间的**协议适配网关**。它不负责业务逻辑，只做三件事：

1. **协议转换**：将 MCP 的 JSON-RPC Tool Call 转换为 Java 的 `x-www-form-urlencoded` HTTP 请求
2. **数据透传**：将 Java 返回的 JSON 数据原样或轻量裁剪后返回给 MCP Client
3. ** Mock 隔离**：开发模式下（`DEV_MODE=true`）直接返回本地 Mock 数据，不连接真实 Java 服务

### 1.2 职责边界

| 职责归属 | 说明 |
|----------|------|
| **MCP Server** | 接收 JSON-RPC → 转换请求格式 → 调用 Java → 返回 JSON-RPC Response |
| **Java 服务** | 提供业务数据（项目信息、团队成员、阶段活动、交付物等） |
| **Python FastAPI** | 运行 ReActAgent，通过 MCP Client 调用 MCP Server |
| **agentscope** | Agent 编排、工具决策、LLM 交互 |

### 1.3 为什么用 Streamable HTTP

根据 MCP 2025-06-18 规范，Streamable HTTP 是官方推荐的新一代传输协议，相比旧版 HTTP+SSE 和 stdio：

| 维度 | stdio | 旧版 HTTP+SSE | **Streamable HTTP** |
|------|-------|---------------|---------------------|
| 进程模型 | 子进程 | 独立进程 | **独立进程** |
| 连接方式 | 标准输入输出 | SSE 长连接 | **POST + GET 双通道** |
| 会话管理 | 无 | 无 | **Mcp-Session-Id** |
| 多客户端 | 不支持 | 支持 | **支持** |
| 断线恢复 | 不支持 | 不支持 | **Last-Event-ID 重放** |
| 适合场景 | 本地插件 | 远程服务 | **生产级远程服务** |

本项目选择 Streamable HTTP，因为：
- MCP Server 必须作为**独立进程**运行（与 FastAPI 不同进程）
- 需要**会话管理**支持多用户并发
- 未来可能部署为独立容器，需要远程连接能力

---

## 二、技术选型

### 2.1 Python MCP SDK

**选型**：官方 `mcp` Python SDK（`pip install mcp>=1.8.0`）

**理由**：
- v1.8.0（2025-05-08 发布）正式支持 Streamable HTTP 传输
- 与规范 2025-06-18 对齐，原生支持 `Mcp-Session-Id` 和 SSE 流
- 提供 `FastMCP` 快捷类，工具注册只需装饰器 + 类型注解

**不选 `fastmcp` 的理由**：
- `fastmcp` 是社区封装库，虽然 API 更简洁，但官方 SDK 已足够轻量
- 官方 SDK 的 `server.run(transport="streamable-http")` 一行即可启动
- 减少依赖层级，降低维护风险

### 2.2 HTTP Client

**选型**：`httpx`（异步）

**理由**：
- 原生异步支持（`async/await`），与 MCP Server 的异步模型一致
- 支持 `x-www-form-urlencoded` 编码（`data={...}`）
- 超时控制精确（`timeout=Timeout(connect=5.0, read=30.0)`）

### 2.3 关键依赖

```text
# mcp_server/requirements.txt
mcp>=1.8.0
httpx>=0.27.0
python-dotenv>=1.0.0
```

---

## 三、端点设计规范

### 3.1 端点清单

MCP Server 只暴露**单一端点**，通过 HTTP Method 区分动作：

| Method | Path | 用途 | 请求头要求 |
|--------|------|------|------------|
| POST | `/mcp` | 发送 JSON-RPC Request / Notification / Response | `Accept: application/json, text/event-stream`；非初始化请求需携带 `Mcp-Session-Id` |
| GET | `/mcp` | 建立 SSE 流，接收 Server 主动推送的消息 | `Accept: text/event-stream`；需携带 `Mcp-Session-Id` |
| DELETE | `/mcp` | 客户端主动终止会话 | 需携带 `Mcp-Session-Id` |

### 3.2 Session 管理

```
1. 初始化：POST /mcp（无 Mcp-Session-Id）
   → Server 返回 InitializeResult + Mcp-Session-Id: <uuid>

2. 确认：POST /mcp（带 Mcp-Session-Id）
   → Server 返回 HTTP 202 Accepted

3. 后续调用：POST /mcp（带 Mcp-Session-Id）
   → Server 返回 JSON Response 或 SSE Stream

4. 接收通知：GET /mcp（带 Mcp-Session-Id）
   → Server 建立 SSE 流

5. 终止：DELETE /mcp（带 Mcp-Session-Id）
   → Server 清理会话资源
```

### 3.3 启动配置

```python
# mcp_server/server.py
from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("zhongzhai_java_gateway")

# 启动参数由环境变量控制
HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8001"))
PATH = os.getenv("MCP_PATH", "/mcp")

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        path=PATH
    )
```

### 3.4 安全约束

- 开发环境绑定 `127.0.0.1`，禁止 `0.0.0.0`
- 生产环境通过反向代理（Nginx）添加 TLS 和 Basic Auth
- 校验 `Origin` 头防止 DNS Rebinding

---

## 四、Tool Registry

### 4.1 工具总览

MCP Server 注册 **8 个核心工具**（覆盖项目基本信息、项目团队、用户查询）。V3 扩展工具（阶段活动、交付物、关联项目）在 4.2 节单独说明。

| 序号 | Tool 名称 | 操作类型 | 对应 Java 接口 |
|:----:|-----------|----------|----------------|
| 1 | `get_project_info` | 查询 | `findProjectById` |
| 2 | `update_project` | 更新 | `updatePmProject` |
| 3 | `get_team_members` | 查询 | `findPmProjectMemberList` |
| 4 | `add_members` | 创建 | `createPmProjectMembers` |
| 5 | `delete_members` | 删除 | `deletePmProjectMembers` |
| 6 | `update_member_roles` | 更新 | `updateMemberRoles` |
| 7 | `update_duty` | 更新 | `updateDuty` |
| 8 | `get_user_by_id` | 查询 | `findUserById` |

### 4.2 工具详细定义

#### T1. get_project_info

```json
{
  "name": "get_project_info",
  "description": "根据项目ID查询项目基本信息，包括项目名称、部门、级别、产品编号、产品名称、项目经理等",
  "inputSchema": {
    "type": "object",
    "properties": {
      "id": {
        "type": "string",
        "description": "项目编号，例如 PJ-202603-S-068"
      }
    },
    "required": ["id"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "id": { "type": "string" },
      "name": { "type": "string", "description": "项目名称" },
      "dept": { "type": "string", "description": "立项申请部门" },
      "baseReq": { "type": "string", "description": "基准需求编号" },
      "level": { "type": "string", "description": "项目级别：S级/A级/B级/C级" },
      "productNo": { "type": "string", "description": "产品编号（可编辑）" },
      "productName": { "type": "string", "description": "产品名称（可编辑）" },
      "reqDept": { "type": "string", "description": "需求相关部门" },
      "changeReq": { "type": "string", "description": "变更需求编号" },
      "pmName": { "type": "string", "description": "项目经理姓名" }
    }
  }
}
```

#### T2. update_project

```json
{
  "name": "update_project",
  "description": "更新项目基本信息。当前仅允许编辑 productNo（产品编号）和 productName（产品名称），其余字段会被透传但不会被修改",
  "inputSchema": {
    "type": "object",
    "properties": {
      "id": { "type": "string", "description": "项目编号" },
      "productNo": { "type": "string", "description": "产品编号" },
      "productName": { "type": "string", "description": "产品名称" },
      "name": { "type": "string", "description": "项目名称（透传）" },
      "dept": { "type": "string", "description": "立项申请部门（透传）" },
      "baseReq": { "type": "string", "description": "基准需求编号（透传）" },
      "level": { "type": "string", "description": "项目级别（透传）" },
      "reqDept": { "type": "string", "description": "需求相关部门（透传）" },
      "changeReq": { "type": "string", "description": "变更需求编号（透传）" },
      "pmName": { "type": "string", "description": "项目经理姓名（透传）" }
    },
    "required": ["id"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "message": { "type": "string" }
    }
  }
}
```

#### T3. get_team_members

```json
{
  "name": "get_team_members",
  "description": "分页查询项目团队成员列表，包含角色、姓名、职责等信息",
  "inputSchema": {
    "type": "object",
    "properties": {
      "pmProjectId": {
        "type": "string",
        "description": "项目编号"
      },
      "page": {
        "type": "integer",
        "description": "页码，从0开始",
        "default": 0
      },
      "size": {
        "type": "integer",
        "description": "每页条数",
        "default": 10
      }
    },
    "required": ["pmProjectId"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "content": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "id": { "type": "string", "description": "成员记录ID" },
            "userId": { "type": "string", "description": "用户ID" },
            "userName": { "type": "string", "description": "用户姓名" },
            "roleName": { "type": "string", "description": "角色名称" },
            "roleIds": { "type": "array", "items": { "type": "string" } },
            "responsibilities": { "type": "array", "items": { "type": "string" } }
          }
        }
      },
      "totalElements": { "type": "integer" },
      "totalPages": { "type": "integer" },
      "number": { "type": "integer" },
      "size": { "type": "integer" }
    }
  }
}
```

#### T4. add_members

```json
{
  "name": "add_members",
  "description": "向项目添加团队成员，通过 userIds 批量添加",
  "inputSchema": {
    "type": "object",
    "properties": {
      "pmProjectId": { "type": "string", "description": "项目编号" },
      "userIds": {
        "type": "array",
        "items": { "type": "string" },
        "description": "待添加的用户ID列表"
      }
    },
    "required": ["pmProjectId", "userIds"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "message": { "type": "string" },
      "data": { "type": "object" }
    }
  }
}
```

#### T5. delete_members

```json
{
  "name": "delete_members",
  "description": "从项目删除团队成员。支持通过 ids（成员记录ID）或 userIds（用户ID）删除，两者至少提供一个",
  "inputSchema": {
    "type": "object",
    "properties": {
      "pmProjectId": { "type": "string", "description": "项目编号" },
      "userIds": {
        "type": "array",
        "items": { "type": "string" },
        "description": "用户ID列表（可选）"
      },
      "ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "成员记录ID列表（可选）"
      }
    },
    "required": ["pmProjectId"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "message": { "type": "string" }
    }
  }
}
```

#### T6. update_member_roles

```json
{
  "name": "update_member_roles",
  "description": "修改项目成员的角色分配",
  "inputSchema": {
    "type": "object",
    "properties": {
      "id": { "type": "string", "description": "成员记录ID" },
      "userId": { "type": "string", "description": "用户ID" },
      "projectId": { "type": "string", "description": "项目编号" },
      "roleIds": {
        "type": "array",
        "items": { "type": "string" },
        "description": "角色ID列表"
      }
    },
    "required": ["id", "userId", "projectId", "roleIds"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "message": { "type": "string" }
    }
  }
}
```

#### T7. update_duty

```json
{
  "name": "update_duty",
  "description": "更新团队成员的职责分配。rid 为角色ID，ids 为职责ID列表，pid 为项目编号",
  "inputSchema": {
    "type": "object",
    "properties": {
      "rid": { "type": "string", "description": "角色ID" },
      "ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "职责ID列表"
      },
      "pid": { "type": "string", "description": "项目编号" }
    },
    "required": ["rid", "ids", "pid"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "message": { "type": "string" }
    }
  }
}
```

#### T8. get_user_by_id

```json
{
  "name": "get_user_by_id",
  "description": "根据用户ID查询用户基本信息，用于添加成员前确认用户存在",
  "inputSchema": {
    "type": "object",
    "properties": {
      "userId": { "type": "string", "description": "用户ID" }
    },
    "required": ["userId"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "id": { "type": "string" },
      "name": { "type": "string" },
      "deptName": { "type": "string" },
      "email": { "type": "string" }
    }
  }
}
```

### 4.3 V3 扩展工具（预留）

以下工具供 V3 阶段使用，当前版本预留接口定义：

| Tool 名称 | 对应 Java 接口 |
|-----------|----------------|
| `get_phase_activities` | `findProjectProgramPlanTreeByProjectId` |
| `cut_phase_activity` | `savePlanTaskCutResult` |
| `get_deliverables` | `findAssetByProjectProgramPage` |
| `cut_deliverable` | `savePlanTaskRel` |
| `get_related_projects` | `findRelProject` |

---

## 五、Java HTTP Client 设计

### 5.1 封装层结构

```
mcp_server/
├── server.py          # FastMCP 实例、工具注册、启动入口
├── java_client.py     # Java HTTP Client 封装（核心）
├── mock_data.py       # Mock 数据定义
└── config.py          # 环境变量加载
```

### 5.2 Java Client 实现

```python
# mcp_server/java_client.py
import os
import json
import httpx
from typing import Any, Dict, Optional

JAVA_BASE_URL = os.getenv("JAVA_SERVICE_URL", "http://localhost:8088")
TIMEOUT = httpx.Timeout(connect=5.0, read=30.0)


class JavaClient:
    """封装对 Java 后台的 HTTP 调用"""

    def __init__(self, base_url: str = JAVA_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=TIMEOUT)

    async def invoke(
        self,
        service_path: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用 Java RestAction.invoke.do

        :param service_path: Java 服务路径，如 /itmp/pmProjectService/findProjectById
        :param payload: 请求参数 dict，会被序列化为 JSON 字符串后作为 param= 发送
        :return: Java 返回的 JSON 数据
        """
        url = f"{self.base_url}/portal/RestAction.invoke.do"
        params = {"url": service_path}
        data = {"param": json.dumps(payload, ensure_ascii=False)}

        response = await self.client.post(url, params=params, data=data)
        response.raise_for_status()

        # Java 可能返回 JSON 字符串包裹的响应，需要二次解析
        text = response.text
        try:
            result = json.loads(text)
            # 如果 result 本身是字符串（双重 JSON 编码），再解析一次
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except json.JSONDecodeError:
            return {"raw": text}

    async def close(self):
        await self.client.aclose()
```

### 5.3 请求格式转换对照

以 `get_project_info(id="PJ-202603-S-068")` 为例：

| 阶段 | 格式 |
|------|------|
| **MCP Tool Call** | JSON-RPC Request: `{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_project_info","arguments":{"id":"PJ-202603-S-068"}}}` |
| **Python 函数调用** | `await java_client.invoke("/itmp/pmProjectService/findProjectById", {"id": "PJ-202603-S-068"})` |
| **HTTP 请求** | `POST http://localhost:8088/portal/RestAction.invoke.do?url=/itmp/pmProjectService/findProjectById` <br> `Content-Type: application/x-www-form-urlencoded` <br> `param={"id":"PJ-202603-S-068"}` |
| **Java 响应** | `{"id":"PJ-202603-S-068","name":"验证主表单01221",...}` |
| **MCP Tool Response** | JSON-RPC Response: `{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\"id\":\"PJ-202603-S-068\",...}"}]}}` |

### 5.4 响应解析策略

Java 返回的数据结构不统一，MCP Server 需要适配：

1. **查询类接口**：直接返回 Java 的 JSON 对象，由 MCP Client（Python Agent）自行解析字段
2. **修改类接口**：Java 可能返回 `{"success": true}` 或纯文本 `"OK"`，统一包装为 `{"success": true, "message": "操作成功"}`
3. **分页接口**：保留 Java 的 `content` / `totalElements` / `totalPages` 结构，不做转换

---

## 六、数据流图

### 6.1 完整调用链路

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层 (React 18)                               │
│                          EventSource → SSE 流                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼ SSE (text/event-stream)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Python AI 后台 (FastAPI + agentscope)                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  ReActAgent (agentscope)                                              │  │
│  │  ├── 决策：调用 MCP Tool                                              │  │
│  │  └── Toolkit.register_mcp_client()                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼ MCP Client (Streamable HTTP)          │
│                         POST http://localhost:8001/mcp                      │
│                         Headers: Mcp-Session-Id, Accept                     │
│                         Body: JSON-RPC Request                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MCP Server (Python, Port 8001)                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  FastMCP (mcp>=1.8.0)                                                 │  │
│  │  ├── Endpoint: POST/GET/DELETE /mcp                                   │  │
│  │  ├── Session Manager (Mcp-Session-Id)                                 │  │
│  │  └── Tool Dispatcher                                                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│            ┌────────────────────────┴────────────────────────┐              │
│            ▼                                                  ▼              │
│  ┌─────────────────────┐                          ┌─────────────────────┐   │
│  │  Mock 模式分支      │                          │  生产模式分支       │   │
│  │  (DEV_MODE=true)    │                          │  (DEV_MODE=false)   │   │
│  │  └── mock_data.py   │                          │  └── java_client.py │   │
│  └─────────────────────┘                          └─────────────────────┘   │
│                                                            │                 │
│                                                            ▼                 │
│                                              POST http://localhost:8088      │
│                                              /portal/RestAction.invoke.do    │
│                                              param={...}                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                                            │
                                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Java 数据服务层                                  │
│                         (Spring Boot + H2/MySQL)                            │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  RestActionController                                                 │  │
│  │  ├── pmProjectService.findProjectById                                 │  │
│  │  ├── pmProjectMemberService.findPmProjectMemberList                   │  │
│  │  ├── pmProjectMemberService.createPmProjectMembers                    │  │
│  │  └── ...                                                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 单请求时序（以 update_project 为例）

```
Python Agent          MCP Server            JavaClient            Java Service
    │                    │                      │                      │
    │  1. JSON-RPC POST  │                      │                      │
    │    tools/call      │                      │                      │
    │ ────────────────>  │                      │                      │
    │                    │                      │                      │
    │                    │  2. 路由到            │                      │
    │                    │     update_project   │                      │
    │                    │                      │                      │
    │                    │  3. 组装参数          │                      │
    │                    │     {"id":"...",     │                      │
    │                    │      "productNo":""} │                      │
    │                    │                      │                      │
    │                    │  4. async invoke     │                      │
    │                    │ ──────────────────>  │                      │
    │                    │                      │                      │
    │                    │                      │  5. POST x-www-form  │
    │                    │                      │     param=JSON       │
    │                    │                      │ ──────────────────>  │
    │                    │                      │                      │
    │                    │                      │  6. JSON Response    │
    │                    │                      │ <──────────────────  │
    │                    │                      │                      │
    │                    │  7. 解析 & 包装       │                      │
    │                    │ <──────────────────  │                      │
    │                    │                      │                      │
    │  8. JSON-RPC Resp  │                      │                      │
    │    result:{...}    │                      │                      │
    │ <────────────────  │                      │                      │
```

---

## 七、错误处理设计

### 7.1 错误分层

| 层级 | 错误场景 | MCP 错误码 | HTTP 状态码 | 说明 |
|------|----------|------------|-------------|------|
| **网络层** | MCP Server 无法连接 Java | `-32001` | 502 | 服务暂时不可用 |
| **Java 层** | Java 返回 404 | `-32602` | 200 (MCP 层) | Java 接口不存在，参数校验失败 |
| **Java 层** | Java 返回 500 | `-32603` | 200 (MCP 层) | Java 内部错误 |
| **Java 层** | Java 请求超时 | `-32000` | 200 (MCP 层) | 请求超时，建议重试 |
| **MCP 层** | 工具名不存在 | `-32601` | 200 | Method not found |
| **MCP 层** | 参数校验失败 | `-32602` | 200 | Invalid params |

### 7.2 错误响应格式

MCP Server 统一返回标准 JSON-RPC Error Response：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Java service timeout",
    "data": {
      "source": "java_client",
      "detail": "Request to /itmp/pmProjectService/findProjectById timed out after 30s"
    }
  }
}
```

### 7.3 Java Client 异常处理代码

```python
# mcp_server/java_client.py
from mcp.types import ErrorData

class JavaClientError(Exception):
    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail

    def to_mcp_error(self) -> ErrorData:
        return ErrorData(
            code=self.code,
            message=self.message,
            data={"source": "java_client", "detail": self.detail}
        )


async def safe_invoke(self, service_path: str, payload: dict) -> dict:
    try:
        return await self.invoke(service_path, payload)
    except httpx.TimeoutException as e:
        raise JavaClientError(
            code=-32000,
            message="Java service timeout",
            detail=f"Request to {service_path} timed out: {e}"
        )
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            raise JavaClientError(
                code=-32602,
                message="Java interface not found",
                detail=f"{service_path} returned 404"
            )
        elif status >= 500:
            raise JavaClientError(
                code=-32603,
                message="Java internal error",
                detail=f"{service_path} returned {status}"
            )
        raise JavaClientError(
            code=-32001,
            message="Java service unavailable",
            detail=f"{service_path} returned {status}"
        )
    except httpx.RequestError as e:
        raise JavaClientError(
            code=-32001,
            message="Java service unreachable",
            detail=str(e)
        )
```

### 7.4 Tool 层异常捕获

```python
# mcp_server/server.py
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ErrorData

mcp = FastMCP("zhongzhai_java_gateway")
java_client = JavaClient()

@mcp.tool()
async def get_project_info(id: str) -> list:
    """查询项目基本信息"""
    try:
        result = await java_client.safe_invoke(
            "/itmp/pmProjectService/findProjectById",
            {"id": id}
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except JavaClientError as e:
        raise Exception(json.dumps(e.to_mcp_error().model_dump()))
```

---

## 八、Mock 模式设计

### 8.1 触发条件

```bash
export DEV_MODE=true   # 启用 Mock 模式
export DEV_MODE=false  # 调用真实 Java（默认）
```

### 8.2 Mock 数据文件

```python
# mcp_server/mock_data.py
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
            "responsibilities": ["产品发布", "业务方案可行性分析"]
        },
        {
            "id": "M002",
            "userId": "U002",
            "userName": "陈杰",
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

MOCK_USER = {
    "id": "U001",
    "name": "张伟",
    "deptName": "信息科技部",
    "email": "zhangwei@example.com"
}

MOCK_SUCCESS = {"success": True, "message": "操作成功"}
```

### 8.3 Mock 分支逻辑

```python
# mcp_server/server.py
import os
from mock_data import MOCK_PROJECT, MOCK_TEAM_PAGE, MOCK_USER, MOCK_SUCCESS

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

@mcp.tool()
async def get_project_info(id: str) -> list:
    if DEV_MODE:
        return [TextContent(type="text", text=json.dumps(MOCK_PROJECT, ensure_ascii=False))]
    result = await java_client.safe_invoke("/itmp/pmProjectService/findProjectById", {"id": id})
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

@mcp.tool()
async def update_project(id: str, **kwargs) -> list:
    if DEV_MODE:
        # 模拟修改：只更新 productNo/productName
        updated = {**MOCK_PROJECT, **{k: v for k, v in kwargs.items() if v is not None}}
        return [TextContent(type="text", text=json.dumps({**MOCK_SUCCESS, "data": updated}, ensure_ascii=False))]
    result = await java_client.safe_invoke("/itmp/pmProjectService/updatePmProject", {"id": id, **kwargs})
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

# ... 其他工具同理
```

### 8.4 Mock 与生产数据格式一致性原则

- Mock 数据的**字段名**、**数据结构**必须与真实 Java 返回完全一致
- Mock 数据需定期与 Java 接口文档同步更新
- 新增字段时，Mock 和生产代码同步修改

---

## 九、部署方案

### 9.1 独立进程启动

MCP Server 作为独立进程运行，与 FastAPI 分离：

```bash
# Terminal 1: 启动 MCP Server
export DEV_MODE=true
export MCP_PORT=8001
export MCP_HOST=127.0.0.1
export JAVA_SERVICE_URL=http://localhost:8088

cd proposal-python-v2/mcp_server
python server.py
# 输出: MCP Server running at http://127.0.0.1:8001/mcp

# Terminal 2: 启动 FastAPI
cd proposal-python-v2
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 9.2 环境变量清单

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DEV_MODE` | `false` | `true` 启用 Mock 模式，不调 Java |
| `MCP_HOST` | `127.0.0.1` | MCP Server 绑定地址 |
| `MCP_PORT` | `8001` | MCP Server 监听端口 |
| `MCP_PATH` | `/mcp` | MCP 端点路径 |
| `JAVA_SERVICE_URL` | `http://localhost:8088` | Java 服务根地址 |
| `JAVA_TIMEOUT_CONNECT` | `5.0` | Java 连接超时（秒） |
| `JAVA_TIMEOUT_READ` | `30.0` | Java 读取超时（秒） |
| `LOG_LEVEL` | `INFO` | 日志级别 |

### 9.3 Docker 部署（生产）

```dockerfile
# mcp_server/Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8001

EXPOSE 8001
CMD ["python", "server.py"]
```

```yaml
# docker-compose.yml (节选)
services:
  mcp-server:
    build: ./proposal-python-v2/mcp_server
    ports:
      - "8001:8001"
    environment:
      - DEV_MODE=false
      - JAVA_SERVICE_URL=http://java-service:8088
      - MCP_HOST=0.0.0.0
    networks:
      - backend

  python-api:
    build: ./proposal-python-v2
    ports:
      - "8000:8000"
    environment:
      - MCP_SERVER_URL=http://mcp-server:8001/mcp
    depends_on:
      - mcp-server
    networks:
      - backend

  java-service:
    build: ./proposal-java
    ports:
      - "8088:8088"
    networks:
      - backend

networks:
  backend:
    driver: bridge
```

---

## 十、与 Python FastAPI 的集成说明

### 10.1 agentscope 连接 MCP Server

agentscope 通过 `streamablehttp_client` 异步上下文管理器连接 MCP Server：

```python
# agent_setup.py
from mcp.client.streamable_http import streamablehttp_client
from agentscope.tool import Toolkit
import os

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp")

async def create_toolkit() -> Toolkit:
    toolkit = Toolkit()

    # 1. 建立 Streamable HTTP 连接
    async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, get_session_id):
        # 2. 初始化 MCP Session
        from mcp import ClientSession
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            session_id = get_session_id()
            print(f"MCP Session established: {session_id}")

            # 3. 获取可用工具列表
            tools_result = await session.list_tools()
            available_tools = [tool.name for tool in tools_result.tools]
            print(f"Available MCP tools: {available_tools}")

            # 4. 注册到 agentscope Toolkit
            # agentscope 会自动将 MCP tools 转换为 Agent 可调用的函数
            toolkit.register_mcp_tools(tools_result.tools, session)

    return toolkit
```

### 10.2 Agent 调用 MCP Tool 的完整流程

```python
# agent_setup.py (简化示意)
from agentscope.agents import ReActAgent
from agentscope.models import DashScopeChatWrapper

async def create_agent(project_id: str, queue) -> ReActAgent:
    toolkit = await create_toolkit()

    model = DashScopeChatWrapper(
        config_name="qwen-max",
        model_name="qwen-max",
        api_key=os.getenv("DASHSCOPE_API_KEY")
    )

    agent = ReActAgent(
        name="ProjectAssistant",
        model=model,
        toolkit=toolkit,
        sys_prompt=SYS_PROMPT_TEMPLATE.format(
            project_id=project_id,
            # ...
        )
    )
    return agent
```

### 10.3 连接配置要点

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| `MCP_SERVER_URL` | `http://127.0.0.1:8001/mcp` | Streamable HTTP 端点 |
| 连接复用 | 每个 Agent 实例独立 Session | FastAPI 的 `agent_pool` 管理生命周期 |
| 超时 | 默认 30s | 与 Java 读取超时对齐 |
| 重连 | 收到 HTTP 404 后重新 Initialize | 遵循 MCP 规范 |

### 10.4 注意事项

1. **Session 隔离**：每个用户会话（SSE 连接）应创建独立的 MCP Session，避免多用户共享 SessionId 导致消息混淆
2. **资源释放**：FastAPI 连接断开时，应发送 `DELETE /mcp` 终止 MCP Session，防止服务端资源泄漏
3. **并发限制**：MCP Server 默认单进程异步模型，如需高并发可考虑 `uvicorn` + `gunicorn` 多 worker 部署

---

**文档结束**
