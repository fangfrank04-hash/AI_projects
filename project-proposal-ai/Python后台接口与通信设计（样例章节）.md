# Python AI 后台 — 接口与通信设计（样例章节）

> **阅读说明**
> 本文档假设读者有 JavaScript（Node.js/Express）开发经验，通过类比帮助快速理解 Python/FastAPI 的对应概念。
> 文档中的代码示例不是完整实现，而是"骨架代码"——你看了就能理解设计意图，AI 也能据此生成完整代码。

---

## 一、FastAPI 快速入门（给 JS 开发者的类比）

### 1.1 FastAPI 是什么？

一句话：**FastAPI之于Python，就像 Express 之于 Node.js。**

| 概念 | Express (Node.js) | FastAPI (Python) | 说明 |
|------|-------------------|------------------|------|
| 创建应用 | `const app = express()` | `app = FastAPI()` | 完全一样 |
| 定义路由 | `app.get('/api/hello', (req, res) => {...})` | `@app.get('/api/hello')` + `def hello():...` | 装饰器 = 注解路由 |
| 路径参数 | `req.params.id` | 函数参数 `id: str` | 自动解析，类型注解 |
| 请求体 | `req.body` | Pydantic Model | **FastAPI 优势：自动校验请求体格式** |
| 响应 | `res.json({...})` | `return {...}` | 直接 return 字典，自动转 JSON |
| 中间件 | `app.use(...)` | `@app.middleware(...)` | 一样的概念 |
| 启动服务 | `app.listen(3000)` | `uvicorn main:app --port 8000` | 命令行启动 |

### 1.2 一个最简单的 FastAPI 应用

```python
# main.py — 这就是你整个 Python 后台的入口文件

from fastapi import FastAPI

app = FastAPI(title="AI Chatbot Backend")

# 定义一个 GET 接口 —— 和 app.get('/hello', ...) 完全一样的意思
@app.get("/api/hello")
def say_hello(name: str = "世界"):
    """
    相当于 Express 的:
    app.get('/api/hello', (req, res) => {
        const name = req.query.name || '世界'
        res.json({ message: `你好，${name}` })
    })
    """
    return {"message": f"你好，{name}"}  # f-string = JS 的模板字符串 `${name}`
```

运行方式：
```bash
# 安装 FastAPI（类似 npm install fastapi）
pip install fastapi uvicorn

# 启动服务（类似 node server.js，端口 8000）
uvicorn main:app --port 8000
```

启动后访问 `http://localhost:8000/api/hello?name=陈杰`，返回：
```json
{"message": "你好，陈杰"}
```

### 1.3 请求体（Request Body）—— Pydantic Model

这是 FastAPI 最强大的特性。相当于 JS 里的 Joi/Zod 校验，但**内置且自动生效**：

```python
from pydantic import BaseModel

# 用 class 定义请求体的格式 —— 相当于 JS 的 interface/type
class ChatMessage(BaseModel):
    message: str        # 必填，字符串
    project_id: str     # 必填，字符串
    step: int           # 必填，整数
    user_inputs: dict | None = None  # 可选，字典（类似 JS 的 object | null）

# 使用：把 Pydantic 类作为参数，FastAPI 自动解析请求体 + 校验
@app.post("/api/chat")
async def handle_chat(msg: ChatMessage):
    """
    相当于 Express 的:
    app.post('/api/chat', express.json(), (req, res) => {
        const { message, project_id, step, user_inputs } = req.body
        ...
    })

    但 FastAPI 多了一步：
    如果请求体缺少必填字段，或类型不对，自动返回 422 错误
    你不需要写任何校验代码！
    """
    print(f"收到消息: {msg.message}")     # f-string = JS 的 `收到消息: ${msg.message}`
    print(f"项目ID: {msg.project_id}")
    print(f"当前步骤: {msg.step}")
    return {"reply": "AI回复内容"}
```

### 1.4 异步 —— async/await

你在 JS 里已经很熟了，Python 的写法几乎一样：

```python
# Python（和 JS 对比）
import httpx  # 相当于 JS 的 fetch / axios

# Python 写法
async def call_java_api():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8080/api/project/PJ-001")
        return response.json()

# JS 等价写法
# async function callJavaApi() {
#     const response = await fetch("http://localhost:8080/api/project/PJ-001");
#     return response.json();
# }
```

> **关键区别**：Python 用 `httpx` 库发 HTTP 请求（不是内置的 `requests`，因为 `requests` 不支持 async）。安装：`pip install httpx`。

---

## 二、整体通信架构

在写接口之前，先搞清楚三端之间怎么通信：

```
┌─────────────┐          ┌──────────────┐          ┌─────────────┐
│   前端       │          │  Python AI   │          │  Java 后台   │
│  (React)    │          │   后台        │          │ (Spring Boot)│
│             │          │  (FastAPI)   │          │             │
│  端口:3000  │          │  端口:8000   │          │  端口:8080   │
└──────┬──────┘          └──────┬───────┘          └──────┬──────┘
       │                        │                         │
       │  ① 用户发消息给 AI     │                         │
       │  POST /ai/chat         │                         │
       │ ──────────────────────>│                         │
       │                        │  ② 获取项目/团队数据      │
       │                        │  GET /api/project/{id}   │
       │                        │ ────────────────────────>│
       │                        │  返回: 项目信息JSON       │
       │                        │ <────────────────────────│
       │                        │                         │
       │                        │  ③ 调用 LLM 生成内容      │
       │                        │  POST (LLM API)          │
       │                        │ ────────> [LLM 云服务]    │
       │                        │  返回: 生成的内容         │
       │                        │ <──────── [LLM 云服务]    │
       │                        │                         │
       │  ④ 返回 AI 回复        │                         │
       │  SSE 流式响应          │                         │
       │ <──────────────────────│                         │
       │                        │                         │
       │  ⑤ 用户点击"确认回填"   │                         │
       │  PUT /api/project/{id}/proposal                   │
       │ ────────────────────────────────────────────────>│
       │  返回: 回填成功          │                         │
       │ <────────────────────────────────────────────────│
       │                        │                         │
```

**核心要点：**

1. **前端只跟两个后端通信**：AI 相关的请求打 Python（8000），业务数据的读写打 Java（8080）
2. **Python 主动调 Java**：Python 需要获取项目数据时，会反向调用 Java 的接口
3. **回填操作归前端→Java**：用户点"确认回填"时，是前端直接调 Java 接口写入数据，Python 不经手
4. **AI 的职责很纯粹**：只负责"理解意图 → 获取上下文 → 调 LLM → 返回结果"，不做数据持久化

---

## 三、Python 后台需要提供的接口清单

### 3.1 接口总览

| # | 接口 | 方法 | 调用方 | 说明 |
|---|------|------|--------|------|
| 1 | `/ai/chat` | POST | 前端 | AI 对话主接口（SSE 流式） |
| 2 | `/ai/start/{project_id}` | POST | 前端 | 启动 AI 流程（初始化上下文） |
| 3 | `/ai/confirm-step` | POST | 前端 | 确认当前步骤（进入下一步） |
| 4 | `/ai/regenerate/{step_id}` | POST | 前端 | 重新生成某步骤的内容 |

> **为什么只有 4 个接口？**
>
> 你可能注意到，补全后的需求文档里列了 7-8 个接口（如 `/ai/generate/team-responsibilities`、`/ai/generate/control-plan` 等）。
>
> 实际上这些"生成"动作都归 `/ai/chat` 统一处理——AI 根据当前步骤决定生成什么。
> 前端不需要关心"调哪个生成接口"，只需要把消息发给 `/ai/chat`，AI 自己判断。
>
> 这和你之前讨论的"配置驱动"架构是一致的：引擎根据配置决定行为，而不是靠不同的接口。

### 3.2 通信协议：为什么用 SSE 而不是普通 HTTP

**问题**：LLM 生成一段内容可能需要 5-15 秒，如果用普通 HTTP 请求，用户会盯着白屏等。

**解决**：用 **SSE（Server-Sent Events）**—— 服务端一边生成，一边把文字"推"给前端。

```
普通 HTTP（用户等10秒才看到结果）:
前端 ──── 请求 ────> Python ──── 等10秒 ────> 返回完整内容 ────> 前端

SSE 流式（用户实时看到文字一个个出来）:
前端 ──── 请求 ────> Python ────> 推"你" ────> 前端
                                   推"好" ────> 前端
                                   推"，" ────> 前端
                                   推"陈" ────> 前端
                                   推"杰" ────> 前端
                                   推"..." ────> 前端
                                   推 [DONE] ──> 前端
```

**前端 SSE 代码对比（JS 你一定看得懂）：**

```javascript
// 前端用 EventSource 接收 SSE
// 注意：因为要发 POST 请求（带请求体），标准 EventSource 不支持
// 所以前端用 fetch + ReadableStream 来处理（已在前端代码中实现）

const response = await fetch('/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: '帮我生成团队职责', project_id: 'PJ-001', step: 1 })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    // chunk 可能是: "data: {\"type\":\"text\",\"content\":\"你\"}\n\n"
    // 解析后更新聊天界面
    const lines = chunk.split('\n');
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'text') {
                appendMessage(data.content);  // 实时追加文字
            }
        }
    }
}
```

### 3.3 Python 调 Java 接口—— httpx

```python
import httpx

# Java 后台的地址
JAVA_API_BASE = "http://localhost:8080"

async def get_project_info(project_id: str) -> dict:
    """
    调用 Java 接口获取项目信息
    相当于 JS: const res = await fetch(`${JAVA_API}/api/project/${project_id}`)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JAVA_API_BASE}/api/project/{project_id}",
            headers={"Authorization": f"Bearer {token}"}  # Token 从前端传过来
        )
        if response.status_code == 200:
            return response.json()  # 返回 dict，和 JS 的 res.json() 一样
        else:
            raise Exception(f"Java接口返回错误: {response.status_code}")

async def get_team_info(project_id: str) -> list:
    """调用 Java 接口获取项目团队信息"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JAVA_API_BASE}/api/project/{project_id}/team",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()  # 返回团队成员列表
```

> **关键问题：Token 怎么传？**
>
> 用户登录后，前端拿到 Token（Java/SSO 签发的）。前端调 Python 接口时，在 Header 里带上 Token。
> Python 再把 Token 透传给 Java，Java 验证 Token 有效性。
>
> ```
> 前端 ──(Header: Authorization: Bearer xxx)──> Python ──(同一个Token)──> Java
> ```

### 3.4 Python 调 LLM —— OpenAI SDK

```python
from openai import OpenAI

# 初始化 LLM 客户端 —— 不同厂商换一个 base_url 就行
llm_client = OpenAI(
    api_key="your-api-key",           # 从环境变量或配置读取
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 通义千问
)

async def generate_team_responsibilities(project_info: dict, team_info: list, rules: str) -> dict:
    """
    调用 LLM 生成团队职责

    参数:
        project_info: 项目信息（来自Java）
        team_info: 团队信息（来自Java）
        rules: 知识库规则（来自Java）

    返回:
        LLM 生成的结构化数据（dict）
    """
    # 1. 组装 Prompt
    prompt = f"""
    你是一个项目管理助手。根据以下信息，为每个团队成员生成职责描述。

    项目信息: {project_info}
    团队成员: {team_info}
    管理规则: {rules}

    请以 JSON 格式返回，格式如下:
    [
        {{"name": "陈杰", "role": "项目经理", "responsibilities": ["职责1", "职责2", ...]}},
        ...
    ]
    """

    # 2. 调用 LLM（支持流式）
    response = llm_client.chat.completions.create(
        model="qwen-max",           # 模型名
        messages=[
            {"role": "system", "content": "你是一个专业的项目管理助手。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,            # 越低越保守（0-1，类似 JS 的概念）
        response_format={"type": "json_object"}  # 强制返回 JSON
    )

    # 3. 解析结果
    result_text = response.choices[0].message.content
    import json
    return json.loads(result_text)  # 字符串 -> dict/list，和 JS 的 JSON.parse() 一样
```

> **多模型切换**：不同 LLM 厂商都兼容 OpenAI SDK 的接口格式，只需换 `base_url` 和 `model`：
>
> | 厂商 | base_url | model |
> |------|----------|-------|
> | 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` |
> | DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
> | Azure OpenAI | `https://your-resource.openai.azure.com/openai/...` | `gpt-4o` |
> | 文心一言 | `https://aip.baidubce.com/...` | 需要单独适配 |

---

## 四、接口详细设计

### 4.1 POST /ai/start/{project_id} — 启动 AI 流程

**用途**：用户打开聊天窗口时，前端调用此接口初始化 AI 上下文。

**请求**：
```
POST /ai/start/PJ-202603-S-068
Headers:
  Authorization: Bearer <token>
```

**响应（SSE 流式）**：
```
data: {"type":"status","content":"正在读取项目信息..."}\n\n
data: {"type":"status","content":"正在加载知识库规则..."}\n\n
data: {"type":"status","content":"正在生成第一步预览..."}\n\n
data: {"type":"step_init","step_id":"team-responsibilities","step_order":1,"step_name":"项目团队职责确认"}\n\n
data: {"type":"preview","data":{"team":[{"name":"陈杰","role":"项目经理","responsibilities":["项目计划管控","里程碑评审","..."]}...]}}\n\n
data: {"type":"status","content":"请确认团队职责内容，确认后点击回填。"}\n\n
data: [DONE]\n\n
```

**Python 代码骨架**：

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import json, httpx

app = FastAPI()
JAVA_API = "http://localhost:8080"

@app.post("/ai/start/{project_id}")
async def start_ai_flow(project_id: str, request: Request):
    """
    启动 AI 填写流程

    流程：
    1. 从 Request Header 取出 Token
    2. 用 Token 调 Java 接口获取项目信息、团队信息、知识库规则
    3. 初始化对话状态（存到内存或 Redis）
    4. 调 LLM 生成第一步内容
    5. 用 SSE 流式返回给前端
    """
    # ① 从请求头获取 Token（前端传过来的）
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    # ② 调 Java 获取项目数据
    async with httpx.AsyncClient() as client:
        # 并行请求（和 Promise.all 一样）
        project_resp, team_resp, rules_resp = await asyncio.gather(
            client.get(f"{JAVA_API}/api/project/{project_id}",
                       headers={"Authorization": f"Bearer {token}"}),
            client.get(f"{JAVA_API}/api/project/{project_id}/team",
                       headers={"Authorization": f"Bearer {token}"}),
            client.get(f"{JAVA_API}/api/knowledge/rules",
                       params={"projectLevel": "S"},  # 从项目信息获取级别
                       headers={"Authorization": f"Bearer {token}"}),
        )

    project_info = project_resp.json()
    team_info = team_resp.json()
    rules = rules_resp.json()

    # ③ 保存状态（这里用内存字典，生产环境用 Redis）
    sessions[project_id] = {
        "project": project_info,
        "team": team_info,
        "rules": rules,
        "current_step": 1,
        "completed_steps": [],
        "user_inputs": {}
    }

    # ④ 定义 SSE 生成器（类似 JS 的 async generator）
    async def event_stream():
        yield sse_format({"type": "status", "content": "正在读取项目信息..."})
        await asyncio.sleep(0.5)  # 模拟处理时间

        yield sse_format({"type": "status", "content": "正在加载知识库规则..."})
        await asyncio.sleep(0.3)

        yield sse_format({"type": "status", "content": "正在生成第一步预览..."})

        # ⑤ 调 LLM 生成第一步（团队职责）
        result = await generate_team_responsibilities(project_info, team_info, rules)

        yield sse_format({
            "type": "step_init",
            "step_id": "team-responsibilities",
            "step_order": 1,
            "step_name": "项目团队职责确认"
        })
        yield sse_format({"type": "preview", "data": result})
        yield sse_format({"type": "status", "content": "请确认团队职责内容，确认后点击回填。"})
        yield "[DONE]"

    # ⑥ 返回 SSE 响应
    return StreamingResponse(event_stream(), media_type="text/event-stream")

def sse_format(data: dict) -> str:
    """把字典转成 SSE 格式字符串: data: {...}\n\n"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
```

> **出问题时怎么排查？**
>
> - 如果"读取项目信息"卡住 → 检查 `JAVA_API` 地址是否正确，Java 服务是否启动
> - 如果 Token 报错 → 检查前端是否正确传了 `Authorization` Header
> - 如果 LLM 没返回 → 检查 `generate_team_responsibilities` 函数的 API Key 和网络
> - 如果前端收不到流 → 用浏览器 DevTools 的 Network 面板查看 `/ai/start` 请求是否有响应

### 4.2 POST /ai/chat — AI 对话主接口

**用途**：用户在聊天框发送消息时的统一入口。AI 根据当前步骤和消息内容决定做什么。

**请求体**：
```json
{
    "project_id": "PJ-202603-S-068",
    "message": "把陈杰的职责里加上风险管控",
    "current_step": 1
}
```

**响应（SSE 流式）**：
```
data: {"type":"status","content":"正在调整团队职责..."}\n\n
data: {"type":"preview","data":{"team":[{"name":"陈杰","role":"项目经理","responsibilities":["项目计划管控","里程碑评审","风险管控","..."]}...]}}\n\n
data: [DONE]\n\n
```

**Python 代码骨架**：

```python
class ChatRequest(BaseModel):
    project_id: str
    message: str
    current_step: int

@app.post("/ai/chat")
async def handle_chat(req: ChatRequest, request: Request):
    """
    AI 对话主接口

    这个接口是核心中的核心。所有"跟AI说话"的动作都走这里。

    内部逻辑（根据 current_step 分发）：
      step 1: 修改团队职责
      step 2: 修改管控方案 / 裁剪阶段
      step 3: 解析用户输入的日期和周期
      step 4: 解析用户输入的工作量数据
      step 5: 修改质量保证计划
    """
    session = sessions.get(req.project_id)
    if not session:
        return {"error": "会话不存在，请先调用 /ai/start"}

    session["current_step"] = req.current_step

    async def event_stream():
        if req.current_step == 1:
            # 用户在步骤1修改团队职责
            yield sse_format({"type": "status", "content": "正在调整团队职责..."})
            result = await modify_team_responsibilities(
                session, req.message  # 把用户消息传给 LLM 作为修改指令
            )
            yield sse_format({"type": "preview", "data": result})

        elif req.current_step == 3:
            # 用户在步骤3提供日期信息
            # 需要从消息中提取 "立项批复日" 和 "项目周期"
            yield sse_format({"type": "status", "content": "正在计算进度计划..."})
            parsed = await extract_schedule_inputs(req.message)  # LLM 提取结构化数据
            if parsed:
                session["user_inputs"]["schedule"] = parsed
                result = await generate_schedule(session, parsed)
                yield sse_format({"type": "preview", "data": result})
            else:
                yield sse_format({"type": "status", "content": "未能识别日期信息，请重新输入，例如：立项批复日2026-05-10，周期3个月"})

        # ... 其他步骤类似处理

        yield "[DONE]"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### 4.3 POST /ai/confirm-step — 确认当前步骤

**用途**：用户点击"确认并回填"按钮时调用。Python 只是标记步骤完成，**不负责实际回填**（回填是前端→Java）。

**请求体**：
```json
{
    "project_id": "PJ-202603-S-068",
    "step_id": "team-responsibilities",
    "confirmed_data": {
        "team": [{"name": "陈杰", "role": "项目经理", "responsibilities": [...]}]
    }
}
```

**响应（SSE 流式）**：
```
data: {"type":"step_completed","step_id":"team-responsibilities"}\n\n
data: {"type":"step_init","step_id":"control-plan","step_order":2,"step_name":"管控方案确认"}\n\n
data: {"type":"status","content":"正在生成管控方案..."}\n\n
data: {"type":"preview","data":{...管控方案内容...}}\n\n
data: [DONE]\n\n
```

**Python 代码骨架**：

```python
class ConfirmRequest(BaseModel):
    project_id: str
    step_id: str
    confirmed_data: dict

@app.post("/ai/confirm-step")
async def confirm_step(req: ConfirmRequest):
    """
    确认当前步骤，并自动开始下一步的生成

    注意：
    - 这里只是"确认"，实际回填（写入数据库）是前端收到响应后，自己调 Java 的 PUT 接口
    - Python 的职责：保存确认的数据到 session → 找到下一步 → 生成下一步的预览
    """
    session = sessions.get(req.project_id)
    if not session:
        return {"error": "会话不存在"}

    # ① 标记当前步骤完成，保存确认的数据
    session["completed_steps"].append(req.step_id)
    session[req.step_id] = req.confirmed_data

    # ② 查找下一步
    next_step = get_next_step(req.step_id)  # 从配置中查找
    if not next_step:
        # 所有步骤完成
        async def done_stream():
            yield sse_format({"type": "all_completed", "content": "所有步骤已完成，数据已回填至方案书。"})
            yield "[DONE]"
        return StreamingResponse(done_stream(), media_type="text/event-stream")

    # ③ 生成下一步的内容
    async def next_stream():
        yield sse_format({"type": "step_completed", "step_id": req.step_id})
        yield sse_format({
            "type": "step_init",
            "step_id": next_step["id"],
            "step_order": next_step["order"],
            "step_name": next_step["name"]
        })
        yield sse_format({"type": "status", "content": f"正在生成{next_step['name']}..."})

        result = await generate_step_content(session, next_step)
        yield sse_format({"type": "preview", "data": result})
        yield "[DONE]"

    return StreamingResponse(next_stream(), media_type="text/event-stream")
```

### 4.4 POST /ai/regenerate/{step_id} — 重新生成

**用途**：用户对 AI 生成的内容不满意，点击"重新生成"。

**请求体**：
```json
{
    "project_id": "PJ-202603-S-068"
}
```

**响应**：和该步骤首次生成时一样，返回 `preview` 类型的 SSE 事件。

```python
@app.post("/ai/regenerate/{step_id}")
async def regenerate_step(step_id: str, req: RegenerateRequest):
    """重新生成某步骤的内容（换一个 Prompt 或换个模型再试一次）"""
    session = sessions.get(req.project_id)

    async def stream():
        yield sse_format({"type": "status", "content": "正在重新生成..."})
        step_config = get_step_config(step_id)  # 从配置查找
        result = await generate_step_content(session, step_config)
        yield sse_format({"type": "preview", "data": result})
        yield "[DONE]"

    return StreamingResponse(stream(), media_type="text/event-stream")
```

---

## 五、项目目录结构（Python 端）

```
python-ai-backend/
├── main.py                     # 入口文件，启动 FastAPI
├── requirements.txt            # 依赖列表（类似 package.json）
├── configs/
│   └── project_proposal.yaml   # 项目方案书的配置（配置驱动架构的核心）
├── engine/
│   ├── chat_engine.py          # 对话引擎（核心逻辑：步骤编排、消息分发）
│   ├── llm_client.py           # LLM 调用封装（多模型切换）
│   └── session_manager.py      # 会话管理（存储对话状态）
├── services/
│   ├── java_api.py             # 调 Java 接口的封装
│   └── prompt_builder.py       # Prompt 模板渲染（Jinja2）
├── models/
│   ├── request_models.py       # Pydantic 请求体定义
│   └── config_models.py        # 配置文件的 Pydantic Model
└── tests/
    └── test_chat_engine.py     # 单元测试
```

**每个文件的职责（用 JS 类比）：**

| 文件 | 类比 JS | 职责 |
|------|---------|------|
| `main.py` | `server.js` | 启动服务，注册路由 |
| `engine/chat_engine.py` | `controllers/chatController.js` | 核心业务逻辑 |
| `engine/llm_client.py` | `services/openaiService.js` | 封装 LLM 调用 |
| `engine/session_manager.py` | `middleware/session.js` | 管理用户会话 |
| `services/java_api.py` | `services/javaApi.js` | 封装对 Java 的 HTTP 调用 |
| `services/prompt_builder.py` | `utils/promptBuilder.js` | 组装 Prompt 模板 |
| `models/request_models.py` | `types/requestTypes.ts` | 定义数据结构 |

---

## 六、requirements.txt（依赖清单）

```txt
# Web 框架
fastapi==0.115.0
uvicorn==0.30.0

# HTTP 客户端（调 Java 接口用）
httpx==0.27.0

# LLM SDK（调大模型用）
openai==1.50.0

# 数据校验（FastAPI 自带，但显式声明）
pydantic==2.9.0

# 配置文件解析
pyyaml==6.0

# Prompt 模板渲染
jinja2==3.1.0

# SSE 流式输出的辅助库
sse-starlette==2.0.0
```

> `requirements.txt` 相当于 `package.json` 的 dependencies。
> 安装方式：`pip install -r requirements.txt`（相当于 `npm install`）。

---

## 七、main.py 完整骨架

```python
# main.py — 把所有路由串联起来
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

app = FastAPI(title="AI Chatbot Backend", version="1.0.0")

# 跨域配置（前端 3000 端口访问 Python 8000 端口，必须配 CORS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # 前端地址
    allow_credentials=True,
    allow_methods=["*"],                       # 允许所有 HTTP 方法
    allow_headers=["*"],                       # 允许所有 Header（包括 Authorization）
)

# 内存会话存储（生产环境换 Redis）
sessions: dict = {}

JAVA_API = "http://localhost:8080"


# ========================================
# 请求体定义
# ========================================
class ChatRequest(BaseModel):
    project_id: str
    message: str
    current_step: int


class ConfirmRequest(BaseModel):
    project_id: str
    step_id: str
    confirmed_data: dict


class RegenerateRequest(BaseModel):
    project_id: str


# ========================================
# SSE 工具函数
# ========================================
def sse_format(data: dict) -> str:
    """dict → SSE 格式字符串"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ========================================
# 路由
# ========================================
@app.post("/ai/start/{project_id}")
async def start_ai_flow(project_id: str, request: Request):
    """启动 AI 流程 — 详见 4.1 节"""
    ...  # 上面的完整代码


@app.post("/ai/chat")
async def handle_chat(req: ChatRequest, request: Request):
    """AI 对话 — 详见 4.2 节"""
    ...


@app.post("/ai/confirm-step")
async def confirm_step(req: ConfirmRequest):
    """确认步骤 — 详见 4.3 节"""
    ...


@app.post("/ai/regenerate/{step_id}")
async def regenerate_step(step_id: str, req: RegenerateRequest):
    """重新生成 — 详见 4.4 节"""
    ...


# ========================================
# 启动
# ========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

> **启动命令**：`python main.py` 或 `uvicorn main:app --port 8000 --reload`
>
> `--reload` 相当于 nodemon，代码改了自动重启。

---

## 八、前端→Python→Java 一次完整调用的数据流

以"用户打开聊天窗口，AI 生成团队职责"为例：

```
时间线    前端 (React)                    Python (FastAPI)                  Java (Spring Boot)
──────    ─────────                       ────────────────                  ──────────────────
T1        点击聊天窗口
          POST /ai/start/PJ-001
          Header: Authorization: xxx
          ─────────────────────────────>
T2                                        收到请求
                                          提取 Token
T3                                        GET /api/project/PJ-001  ──────>
T4                                                                         查询数据库
T5                                        <──── {"id":"PJ-001",...}
T6                                        GET /api/project/PJ-001/team ──>
T7                                                                         查询团队表
T8                                        <──── [{"name":"陈杰",...}]
T9                                        GET /api/knowledge/rules ──────>
T10                                                                        查询规则表
T11                                       <──── {"S级":["开发","测试",...]}
T12                                       保存到 sessions["PJ-001"]
T13                                       调 LLM（通义千问）
T14                                       POST https://dashscope.../chat/completions
T15                                                              <──── LLM返回JSON
T16                                       解析 LLM 结果
          <──── SSE: status "正在生成..."
          <──── SSE: preview {team:[...]}
          <──── SSE: status "请确认..."
          <──── SSE: [DONE]
T17       渲染预览卡片
T18       用户点击"确认并回填"
          PUT /api/project/PJ-001/proposal  ────────────────────────────>
T19                                                                        更新数据库
T20       <──── 200 OK                          <──── {"success":true}
T21       同时调: POST /ai/confirm-step
          ─────────────────────────────>
T22                                       标记 step1 完成
T23                                       调 LLM 生成 step2
          <──── SSE: step_init step2
          <──── SSE: preview {control:[...]}
T24       渲染步骤2预览卡片
```

---

## 九、Java 后台接口文档（Python 需要调用的）

> **说明**：以下接口是 Java 后台已存在或按业务逻辑需要存在的接口。Python 只**读取**这些接口的数据，不负责写入。写入（回填）操作是前端直接调 Java。
>
> 你不需要实现这些接口（Java 同事负责），但你需要知道**调什么、传什么、返回什么**，才能写出正确的 Python 调用代码。

### 9.1 接口总览

| # | 接口 | 方法 | 调用方 | 用途 |
|---|------|------|--------|------|
| J1 | `/api/project/{project_id}` | GET | Python | 获取项目基本信息 |
| J2 | `/api/project/{project_id}/team` | GET | Python | 获取项目团队成员列表 |
| J3 | `/api/knowledge/rules` | GET | Python | 获取管控知识库规则 |
| J4 | `/api/project/{project_id}/proposal` | PUT | 前端 | 回填方案书数据 |
| J5 | `/api/auth/login` | POST | 前端 | 登录获取 Token（开发阶段简化版） |

---

### 9.2 J1: GET /api/project/{project_id} — 获取项目信息

**Python 什么时候调？** 启动 AI 流程时（`/ai/start`），需要拿到项目的名称、级别、类型等信息来生成方案。

**请求**：
```
GET /api/project/PJ-202603-S-068
Headers:
  Authorization: Bearer <token>
```

**响应**：
```json
{
  "code": 200,
  "data": {
    "projectId": "PJ-202603-S-068",
    "projectName": "新一代综合业务平台建设项目",
    "projectLevel": "S",
    "projectType": "IT项目建设",
    "department": "信息技术部",
    "manager": "陈杰",
    "startDate": "2026-03-15",
    "plannedEndDate": "2026-12-31",
    "status": "进行中",
    "description": "建设新一代综合业务平台，支撑公司核心业务数字化转型..."
  }
}
```

**Python 调用代码**：
```python
async def get_project_info(project_id: str, token: str) -> dict:
    """
    获取项目信息
    相当于 JS: const res = await fetch(`/api/project/${projectId}`, { headers: { Authorization } })
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JAVA_API}/api/project/{project_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()  # 不是200就抛异常，类似 JS 的 if (!res.ok) throw ...
        result = response.json()
        return result["data"]  # Java 的返回格式通常包一层 { code, data }，取 data 即可
```

---

### 9.3 J2: GET /api/project/{project_id}/team — 获取团队成员

**Python 什么时候调？** 步骤1（团队职责确认）需要知道有哪些成员及其角色，才能为他们分配职责。

**请求**：
```
GET /api/project/PJ-202603-S-068/team
Headers:
  Authorization: Bearer <token>
```

**响应**：
```json
{
  "code": 200,
  "data": [
    {
      "employeeId": "E001",
      "name": "陈杰",
      "role": "项目经理",
      "department": "信息技术部",
      "joinDate": "2026-03-15"
    },
    {
      "employeeId": "E002",
      "name": "王磊",
      "role": "技术负责人",
      "department": "信息技术部",
      "joinDate": "2026-03-15"
    },
    {
      "employeeId": "E003",
      "name": "李芳",
      "role": "需求负责人",
      "department": "业务运营部",
      "joinDate": "2026-03-20"
    }
  ]
}
```

**Python 调用代码**：
```python
async def get_team_info(project_id: str, token: str) -> list:
    """获取团队成员列表"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{JAVA_API}/api/project/{project_id}/team",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        result = response.json()
        return result["data"]  # 返回团队成员列表（list of dict）
```

---

### 9.4 J3: GET /api/knowledge/rules — 获取知识库规则

**Python 什么时候调？** 生成管控方案（步骤2）、进度计划（步骤3）等都需要参考公司制度规则。

**请求**：
```
GET /api/knowledge/rules?projectLevel=S&projectType=IT项目建设
Headers:
  Authorization: Bearer <token>
```

> **查询参数说明**：
> - `projectLevel`: 项目级别（S/A/B/C），决定适用哪些管控规则
> - `projectType`: 项目类型，不同类型有不同的管控要求

**响应**：
```json
{
  "code": 200,
  "data": {
    "controlPhases": [
      {
        "phase": "需求分析",
        "requiredArtifacts": ["需求规格说明书", "原型图", "需求评审记录"],
        "reviewRequired": true,
        "reviewers": ["技术负责人", "QA负责人"]
      },
      {
        "phase": "设计",
        "requiredArtifacts": ["概要设计文档", "详细设计文档", "数据库设计文档"],
        "reviewRequired": true,
        "reviewers": ["技术负责人", "架构师"]
      }
    ],
    "milestoneRules": {
      "S": ["立项评审", "需求评审", "设计评审", "上线评审", "验收评审"],
      "A": ["立项评审", "需求评审", "上线评审", "验收评审"],
      "B": ["立项评审", "上线评审", "验收评审"]
    },
    "qualityStandards": {
      "codeReviewRequired": true,
      "unitTestCoverage": 80,
      "performanceTestRequired": true
    }
  }
}
```

---

### 9.5 J4: PUT /api/project/{project_id}/proposal — 回填方案书

**谁调？** 前端直接调 Java。**Python 不调这个接口。**

用户点击"确认并回填"后，前端拿到 Python 生成的预览数据，自己调这个接口写入数据库。

**请求**：
```
PUT /api/project/PJ-202603-S-068/proposal
Headers:
  Authorization: Bearer <token>
  Content-Type: application/json

Body:
{
  "stepId": "team-responsibilities",
  "sectionData": {
    "team": [
      {
        "name": "陈杰",
        "role": "项目经理",
        "responsibilities": ["项目计划管控", "里程碑评审", "风险管控", "干系人沟通"]
      }
    ]
  }
}
```

**响应**：
```json
{
  "code": 200,
  "message": "方案书内容已更新"
}
```

> **前端调用代码（JS，给你参考，了解整个数据流）**：
> ```javascript
> // 用户点击"确认并回填"时，前端执行：
> async function handleConfirmBackfill(stepId, confirmedData) {
>     // 1. 先调 Java 回填
>     const res = await fetch(`/api/project/${projectId}/proposal`, {
>         method: 'PUT',
>         headers: {
>             'Authorization': `Bearer ${token}`,
>             'Content-Type': 'application/json'
>         },
>         body: JSON.stringify({ stepId, sectionData: confirmedData })
>     });
>
>     if (res.ok) {
>         // 2. 回填成功后，再调 Python 确认步骤，让 AI 进入下一步
>         const aiRes = await fetch('/ai/confirm-step', {
>             method: 'POST',
>             body: JSON.stringify({ project_id: projectId, stepId, confirmedData })
>         });
>     }
> }
> ```

---

### 9.6 J5: POST /api/auth/login — 登录（开发阶段简化版）

**谁调？** 前端。这是开发阶段的简化登录，正式环境走 SSO/LDAP 统一认证。

**请求**：
```
POST /api/auth/login
Content-Type: application/json

Body:
{
  "username": "chenjie",
  "password": "123456"
}
```

**响应**：
```json
{
  "code": 200,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImNoZW5qaWUiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTQ4MjQwMDB9.xxx",
    "username": "chenjie",
    "displayName": "陈杰",
    "role": "项目经理"
  }
}
```

> **Token 格式说明**：JWT（JSON Web Token），由三段 Base64 字符串组成，用 `.` 分隔。
> - 第一段（Header）：算法信息
> - 第二段（Payload）：用户信息（username、role、过期时间等）
> - 第三段（Signature）：签名（防止篡改）
>
> JWT 不需要 Redis 存储就能验证——Python/Java 各自用同一个密钥（SECRET）解码，校验签名和过期时间就行。这在后面 Token 认证章节会详细讲。

---

## 十、Token 认证机制

> **这一章解决什么问题？**
>
> 用户登录后拿到 Token。Token 要在三个服务之间传递：前端 → Python → Java。
> Python 怎么验证 Token 是有效的？怎么把 Token 透传给 Java？

### 10.1 整体流程

```
┌──────┐   1. POST /api/auth/login   ┌──────┐
│ 前端  │ ──────────────────────────> │ Java │
│      │   2. 返回 JWT Token         │      │
│      │ <────────────────────────── │      │
│      │                              │      │
│      │   3. 请求带 Token Header    │      │
│      │ ──────────────────────────> │ Python │
│      │                              │       │
│      │   4. Python 验证 Token     │       │
│      │      + 透传给 Java         │       │
│      │   5. Python ────────────> │ Java │
│      │   6. Java 返回数据        │      │
│      │      <─────────────────── │      │
└──────┘                              └──────┘
```

### 10.2 JWT 是什么？（给 JS 开发者的类比）

你可能用过 `jsonwebtoken` 这个 npm 包：
```javascript
// JS 里签发 JWT
const jwt = require('jsonwebtoken');
const token = jwt.sign({ username: 'chenjie', role: 'admin' }, 'secret-key', { expiresIn: '8h' });

// JS 里验证 JWT
const decoded = jwt.verify(token, 'secret-key');
```

Python 里完全一样，只是换了一个库：
```python
# Python 里签发 JWT（Python 不需要做这一步，Java 负责签发，但给你看完整链路）
import jwt
token = jwt.encode({"username": "chenjie", "role": "admin"}, "secret-key", algorithm="HS256")

# Python 里验证 JWT
decoded = jwt.decode(token, "secret-key", algorithms=["HS256"])
```

### 10.3 Token 中间件（Python 端）

每次前端调 Python 接口，都需要在 Header 里带 Token。Python 用**中间件**（相当于 Express 的 `app.use()`）统一拦截和验证：

```python
# middleware/auth.py — Token 验证中间件
import jwt
from fastapi import Request, HTTPException

# ⚠️ 生产环境必须从环境变量读取，不能写死在代码里
JWT_SECRET = "your-shared-secret-key"  # 和 Java 约定好的同一个密钥
JWT_ALGORITHM = "HS256"


async def verify_token(request: Request) -> dict:
    """
    从请求头提取并验证 JWT Token

    相当于 Express 中间件:
    app.use((req, res, next) => {
        const token = req.headers.authorization?.replace('Bearer ', '')
        try {
            req.user = jwt.verify(token, SECRET)
            next()
        } catch (e) {
            res.status(401).json({ error: 'Token无效或已过期' })
        }
    })

    返回解码后的用户信息 dict: {"username": "chenjie", "role": "admin", "exp": ...}
    """
    # 1. 从 Header 取 Token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization Header")

    token = auth_header.replace("Bearer ", "")

    # 2. 验证 Token（如果过期或伪造，会抛 jwt.InvalidTokenError）
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload  # {"username": "chenjie", "role": "admin", "exp": 1714824000}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token 无效")
```

### 10.4 在路由中使用 Token 验证

```python
# 在路由里调用验证函数，拿到用户信息
from middleware.auth import verify_token

@app.post("/ai/start/{project_id}")
async def start_ai_flow(project_id: str, request: Request):
    # 验证 Token，拿到用户信息
    user = await verify_token(request)  # {"username": "chenjie", "role": "admin"}
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    # 后续用 token 透传给 Java
    project_info = await get_project_info(project_id, token)

    # 也可以用 user 信息做权限判断
    # if user["role"] not in ["项目经理", "管理员"]:
    #     raise HTTPException(403, "无权限操作")
    ...
```

### 10.5 开发阶段简化方案

正式环境走 SSO/LDAP，但开发阶段你可以**跳过 Java 登录**，直接生成一个假 Token 来测试：

```python
# dev_utils.py — 开发工具（仅用于本地调试）
import jwt
from datetime import datetime, timedelta

DEV_JWT_SECRET = "dev-secret-not-for-production"

def create_dev_token(username: str = "chenjie", role: str = "项目经理") -> str:
    """
    开发阶段快速生成测试 Token
    相当于 JS: jwt.sign({ username, role }, 'secret', { expiresIn: '8h' })
    """
    payload = {
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=8)  # 8小时过期
    }
    return jwt.encode(payload, DEV_JWT_SECRET, algorithm="HS256")


# 使用方式：在 Python 启动时打印一个测试 Token，方便前端复制粘贴
if __name__ == "__main__":
    token = create_dev_token()
    print(f"\n{'='*50}")
    print(f"开发模式 - 测试 Token:")
    print(f"{token}")
    print(f"{'='*50}\n")
    print("把这个 Token 复制到前端的 Authorization Header 里即可测试")
```

> **依赖**：`pip install PyJWT`
>
> **关键点**：Python 和 Java 必须用**同一个 SECRET**。开发阶段可以先在两边都写死一个相同的值，后续再改为从配置中心/环境变量读取。

---

## 十一、会话存储方案

> **这章解决什么问题？**
>
> 用户打开聊天窗口，AI 开始生成步骤1。用户发消息修改步骤1，AI 需要记住"之前的上下文"。这些对话状态存在哪里？

### 11.1 会话里存什么？

每次 `/ai/start` 调用后，Python 需要记住这个项目的完整上下文：

```python
# 一个会话（session）的数据结构
session = {
    # ===== 基础信息（从 Java 获取，不会变） =====
    "project_id": "PJ-202603-S-068",
    "project_info": {"projectName": "...", "projectLevel": "S", ...},
    "team_info": [{"name": "陈杰", "role": "项目经理", ...}, ...],
    "knowledge_rules": {"controlPhases": [...], ...},
    "user": {"username": "chenjie", "role": "项目经理"},  # 从 Token 解析

    # ===== 流程状态（随对话推进而变化） =====
    "current_step": 2,               # 当前在第几步
    "completed_steps": ["team-responsibilities"],  # 已完成的步骤
    "step_results": {                 # 每步的生成结果
        "team-responsibilities": {
            "team": [{"name": "陈杰", "responsibilities": [...]}]
        }
    },
    "chat_history": [                 # 完整对话历史（给 LLM 看的）
        {"role": "assistant", "content": "我已为该项目生成了团队职责..."},
        {"role": "user", "content": "把陈杰的职责加上风险管控"},
        {"role": "assistant", "content": "已更新，陈杰的职责如下：..."},
    ],

    # ===== 元信息 =====
    "created_at": "2026-05-04T22:00:00",
    "last_active": "2026-05-04T22:30:00",
}
```

### 11.2 方案一：内存字典（开发阶段）

最简单的方案，直接用一个 Python 字典：

```python
# engine/session_manager.py — 会话管理器

from datetime import datetime
from typing import Optional


class MemorySessionManager:
    """
    内存会话管理器

    相当于 JS:
    const sessions = new Map()

    sessions.set('PJ-001', { project: {...}, currentStep: 1, ... })
    sessions.get('PJ-001')
    sessions.delete('PJ-001')
    """

    def __init__(self):
        self._sessions: dict = {}  # key: project_id, value: session dict

    def create(self, project_id: str, initial_data: dict) -> dict:
        """
        创建新会话
        相当于 JS: sessions.set(projectId, { ...initialData, createdAt: Date.now() })
        """
        session = {
            **initial_data,
            "current_step": 1,
            "completed_steps": [],
            "step_results": {},
            "chat_history": [],
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
        self._sessions[project_id] = session
        return session

    def get(self, project_id: str) -> Optional[dict]:
        """
        获取会话
        相当于 JS: sessions.get(projectId)
        """
        session = self._sessions.get(project_id)
        if session:
            session["last_active"] = datetime.now().isoformat()  # 更新活跃时间
        return session

    def update(self, project_id: str, updates: dict) -> dict:
        """
        更新会话（部分更新）
        相当于 JS: Object.assign(sessions.get(projectId), updates)
        """
        session = self._sessions.get(project_id)
        if not session:
            raise ValueError(f"会话不存在: {project_id}")
        session.update(updates)
        return session

    def delete(self, project_id: str):
        """
        删除会话
        相当于 JS: sessions.delete(projectId)
        """
        self._sessions.pop(project_id, None)

    def list_active(self) -> list:
        """列出所有活跃会话（开发调试用）"""
        return [
            {"project_id": pid, "step": s["current_step"], "last_active": s["last_active"]}
            for pid, s in self._sessions.items()
        ]


# 全局实例（相当于 JS 的单例）
session_manager = MemorySessionManager()
```

**使用示例**：
```python
from engine.session_manager import session_manager

# 创建会话
session_manager.create("PJ-001", {
    "project_info": {"projectName": "新平台", "projectLevel": "S"},
    "team_info": [{"name": "陈杰", "role": "项目经理"}],
})

# 获取会话
session = session_manager.get("PJ-001")
print(session["current_step"])  # 1

# 更新会话
session_manager.update("PJ-001", {
    "current_step": 2,
    "completed_steps": ["team-responsibilities"]
})

# 清理（流程结束时）
session_manager.delete("PJ-001")
```

### 11.3 方案二：Redis（生产环境）

> **你不需要在开发阶段配置 Redis**。代码里用"接口 + 切换开关"的方式，让两种存储方案可以自由切换。

```python
# engine/session_manager.py — 完整版（内存 + Redis 双模式）

import os
import json
from datetime import datetime
from typing import Optional


class MemorySessionManager:
    """内存会话管理器（开发用）"""
    # ... 上面的代码，这里省略 ...


class RedisSessionManager:
    """
    Redis 会话管理器（生产用）

    你不需要手写 Redis 操作代码。只需要知道：
    - Redis 是一个内存数据库，数据存在服务器内存里，读写极快
    - Python 用 redis-py 库连接 Redis
    - 数据用 JSON 序列化后存进去，取出来再反序列化

    相当于 JS 里用 ioredis 或 connect-redis 存 session
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        redis_url 格式: redis://用户名:密码@主机:端口/数据库编号
        例如: redis://:mypassword@10.0.0.100:6379/0
        """
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl = 8 * 3600  # 会话过期时间：8小时（和 JWT 过期时间一致）

    def _key(self, project_id: str) -> str:
        """Redis 的 key 格式：ai:session:{project_id}"""
        return f"ai:session:{project_id}"

    def create(self, project_id: str, initial_data: dict) -> dict:
        session = {
            **initial_data,
            "current_step": 1,
            "completed_steps": [],
            "step_results": {},
            "chat_history": [],
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
        # 存到 Redis，设置过期时间（EX = 秒）
        self._redis.setex(
            self._key(project_id),
            self._ttl,
            json.dumps(session, ensure_ascii=False)
        )
        return session

    def get(self, project_id: str) -> Optional[dict]:
        data = self._redis.get(self._key(project_id))
        if not data:
            return None
        session = json.loads(data)
        session["last_active"] = datetime.now().isoformat()
        # 刷新过期时间（每次访问都续期，相当于 session 的滑动过期）
        self._redis.expire(self._key(project_id), self._ttl)
        return session

    def update(self, project_id: str, updates: dict) -> dict:
        session = self.get(project_id)
        if not session:
            raise ValueError(f"会话不存在: {project_id}")
        session.update(updates)
        self._redis.setex(
            self._key(project_id),
            self._ttl,
            json.dumps(session, ensure_ascii=False)
        )
        return session

    def delete(self, project_id: str):
        self._redis.delete(self._key(project_id))


# ========================================
# 切换逻辑：根据环境变量自动选择
# ========================================
def get_session_manager():
    """
    根据环境变量决定用内存还是 Redis

    .env 文件里设置:
      SESSION_STORE=redis     → 用 Redis
      SESSION_STORE=memory    → 用内存（默认）

    相当于 JS 的:
    const sessionStore = process.env.SESSION_STORE === 'redis'
        ? new RedisStore(redisUrl)
        : new MemoryStore()
    """
    store_type = os.getenv("SESSION_STORE", "memory")  # 默认内存

    if store_type == "redis":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        print(f"[Session] 使用 Redis: {redis_url}")
        return RedisSessionManager(redis_url)
    else:
        print("[Session] 使用内存存储（开发模式）")
        return MemorySessionManager()


# 全局会话管理器
session_manager = get_session_manager()
```

### 11.4 在 .env 里配置

```ini
# .env — 环境变量配置文件（相当于 JS 的 .env）

# ===== 会话存储 =====
# 开发阶段
SESSION_STORE=memory

# 生产环境（把上面改成下面这行即可）
# SESSION_STORE=redis
# REDIS_URL=redis://:password@your-redis-host:6379/0
```

```python
# main.py 里加载 .env（相当于 JS 的 dotenv）
from dotenv import load_dotenv
load_dotenv()  # 自动读取 .env 文件里的环境变量
```

> **依赖**：`pip install python-dotenv`（Redis 方案额外需要 `pip install redis`）
>
> **切换成本**：从开发切到生产，只需要改 `.env` 里的 `SESSION_STORE=redis`，代码零改动。

---

## 十二、LLM 配置与调用

### 12.1 技术选型：通义千问 + OpenAI 兼容 SDK

| 项目 | 值 |
|------|-----|
| 模型厂商 | 阿里云·通义千问 |
| 调用方式 | OpenAI 兼容 SDK（`openai` Python 包） |
| 推荐模型 | `qwen-max`（能力最强） / `qwen-plus`（性价比高） |
| API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 流式支持 | 支持（SSE） |

> **为什么用 OpenAI SDK 调通义千问？**
>
> 通义千问提供了 OpenAI 兼容接口。这意味着你用 `openai` SDK 的代码，只需要改 `base_url` 和 `model` 就能切换到任意兼容的模型（DeepSeek、月之暗面、硅基流动等）。**你的 Python 代码不需要任何改动。**

### 12.2 API Key 管理

```python
# config/llm_config.py — LLM 配置

import os
from openai import OpenAI


def get_llm_client() -> OpenAI:
    """
    获取 LLM 客户端（单例）

    相当于 JS:
    const openai = new OpenAI({
        apiKey: process.env.OPENAI_API_KEY,
        baseURL: 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    })
    """
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),   # 从环境变量读取
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    )


def get_default_model() -> str:
    """获取默认模型名"""
    return os.getenv("LLM_MODEL", "qwen-max")
```

### 12.3 .env 配置

```ini
# .env — LLM 配置

# 通义千问 API Key（等你提供后填入）
DASHSCOPE_API_KEY=sk-your-api-key-here

# 通义千问 API 地址（一般不用改）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 默认模型（qwen-max 最强，qwen-plus 更便宜）
LLM_MODEL=qwen-max
```

### 12.4 LLM 调用封装（支持流式和非流式）

```python
# engine/llm_client.py — LLM 调用封装

import json
from openai import OpenAI
from config.llm_config import get_llm_client, get_default_model


async def call_llm(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.3,
    response_format: dict = None,
    stream: bool = False,
) -> str | object:
    """
    统一的 LLM 调用接口

    参数:
        messages: 对话历史列表 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        model: 模型名（不传就用默认的 qwen-max）
        temperature: 创造性程度（0=严格，1=发散，推荐 0.3）
        response_format: 指定返回格式，如 {"type": "json_object"} 强制返回 JSON
        stream: 是否流式返回（SSE 场景用 True，普通场景用 False）

    返回:
        stream=False: 返回字符串（LLM 的完整回复）
        stream=True: 返回异步生成器（yield 每个文字片段）

    相当于 JS:
    async function callLLM({ messages, model, temperature, stream }) {
        const response = await openai.chat.completions.create({
            model: model || 'qwen-max',
            messages,
            temperature,
            stream,
        });
        if (stream) return response;  // 返回 stream 对象
        return response.choices[0].message.content;
    }
    """
    client = get_llm_client()
    model = model or get_default_model()

    # 构建请求参数（类似 JS 的请求选项对象）
    request_params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if response_format:
        request_params["response_format"] = response_format

    if stream:
        # 流式模式：返回一个生成器，每次 yield 一个文字片段
        response = client.chat.completions.create(**request_params)

        async def text_stream():
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:  # 有些 chunk 是空的（只包含元数据）
                    yield delta.content

        return text_stream()
    else:
        # 非流式模式：等待完整结果返回
        response = client.chat.completions.create(**request_params)
        return response.choices[0].message.content


async def call_llm_json(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.3,
) -> dict:
    """
    调用 LLM 并强制返回 JSON

    这是 call_llm 的快捷方式，内部设了 response_format={"type": "json_object"}，
    并自动把返回的 JSON 字符串解析为 dict。

    相当于 JS:
    const text = await callLLM({ messages, responseFormat: { type: 'json_object' } });
    return JSON.parse(text);
    """
    result_text = await call_llm(
        messages=messages,
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        stream=False
    )
    return json.loads(result_text)
```

### 12.5 使用示例

```python
# 示例1：让 LLM 生成团队职责（返回 JSON）
messages = [
    {"role": "system", "content": "你是一个项目管理助手，请以 JSON 格式回复。"},
    {"role": "user", "content": "项目名称：新平台建设。团队成员：陈杰(项目经理)、王磊(技术负责人)。请为每人生成职责描述。"}
]
result = await call_llm_json(messages)
print(result)  # {"team": [{"name": "陈杰", "role": "项目经理", "responsibilities": [...]}, ...]}


# 示例2：流式生成（用于 SSE 推送给前端）
async def stream_chat():
    messages = [
        {"role": "system", "content": "你是项目管理助手。"},
        {"role": "user", "content": "请简述 S 级项目的管控要求。"}
    ]
    text_gen = await call_llm(messages, stream=True)
    async for chunk in text_gen:
        print(chunk, end="", flush=True)  # 实时打印：一个字一个字出来
```

---

## 十三、配置驱动架构设计

> **这是整个项目的核心架构设计。**
>
> **解决的问题**：不同部门的业务逻辑不同（步骤不同、规则不同、Prompt 不同），但 Python 引擎代码只有一套。差异全部通过 YAML 配置文件表达。

### 13.1 核心思想

```
传统的做法（每个部门一套代码）:
  部门A的 Python 代码:  hardcode("步骤1生成团队", "步骤2生成管控", ...)
  部门B的 Python 代码:  hardcode("步骤1生成需求", "步骤2生成预算", ...)
  部门C的 Python 代码:  hardcode("步骤1生成立项", "步骤2生成合规", ...)

配置驱动的做法（一套代码 + 多份配置）:
  Python 引擎代码:  read_config("部门A.yaml") → 按配置执行
  Python 引擎代码:  read_config("部门B.yaml") → 按配置执行
  Python 引擎代码:  read_config("部门C.yaml") → 按配置执行
```

**类比 JS**：就像 Webpack 的配置——Webpack 的核心代码不变，你通过 `webpack.config.js` 控制打包行为。我们的引擎代码不变，通过 YAML 控制生成行为。

### 13.2 配置文件示例：项目方案书

```yaml
# configs/project_proposal.yaml — 项目方案书的配置
# 这是配置驱动架构的核心文件

# ===== 基本信息 =====
metadata:
  name: "项目方案书自动填写"
  version: "1.0.0"
  description: "辅助项目经理填写项目方案书的 AI 引擎配置"

# ===== 适用条件（什么时候用这套配置） =====
conditions:
  department: "信息技术部"        # 适用部门
  project_type: "IT项目建设"      # 适用项目类型
  project_levels: ["S", "A"]     # 适用项目级别

# ===== 步骤定义 =====
steps:
  - id: "team-responsibilities"
    order: 1
    name: "项目团队职责确认"
    description: "为项目团队成员分配职责描述"

    # 这个步骤需要从 Java 获取哪些数据
    required_data:
      - project_info      # 项目信息（所有人名、级别等）
      - team_info          # 团队成员列表（姓名、角色、部门）

    # 这个步骤需要从 Java 获取哪些知识库规则
    required_rules:
      - role_definitions   # 角色职责定义

    # LLM 生成参数
    llm:
      model: "qwen-max"              # 用哪个模型
      temperature: 0.3               # 创造性程度
      response_format: "json_object" # 强制返回 JSON

    # Prompt 模板（用 {{变量}} 占位，运行时替换为真实数据）
    prompt_template: |
      你是一个项目管理助手。根据以下信息，为每个团队成员生成职责描述。

      ## 项目信息
      项目名称：{{project_name}}
      项目级别：{{project_level}}
      项目描述：{{project_description}}

      ## 团队成员
      {% for member in team_members %}
      - {{member.name}}（{{member.role}}，{{member.department}}）
      {% endfor %}

      ## 角色职责定义（参考规则）
      {{role_definitions}}

      ## 输出要求
      请以 JSON 格式返回，格式如下：
      {
        "team": [
          {"name": "成员姓名", "role": "角色", "department": "部门", "responsibilities": ["职责1", "职责2", ...]}
        ]
      }

    # 返回数据的验证规则（确保 LLM 返回的 JSON 格式正确）
    expected_output:
      type: "object"
      required_fields: ["team"]
      team_item_fields: ["name", "role", "department", "responsibilities"]

  - id: "control-plan"
    order: 2
    name: "管控方案确认"
    description: "根据项目级别和类型生成管控阶段和裁剪建议"

    required_data:
      - project_info
      - knowledge_rules    # 管控知识库规则

    required_rules:
      - control_phases
      - milestone_rules

    llm:
      model: "qwen-max"
      temperature: 0.2     # 管控方案要求更保守（低 temperature）
      response_format: "json_object"

    prompt_template: |
      根据{{project_level}}级{{project_type}}项目的管控要求，生成管控方案。

      ## 可选管控阶段（来自知识库）
      {% for phase in available_phases %}
      - {{phase.phase}}：{{phase.description}}
      {% endfor %}

      ## 里程碑要求
      {{milestone_rules}}

      请生成裁剪建议，以 JSON 格式返回：
      {
        "selected_phases": [...],
        "removed_phases": [...],
        "removal_reasons": {...},
        "milestones": [...]
      }

    expected_output:
      type: "object"
      required_fields: ["selected_phases", "removed_phases", "milestones"]

  - id: "schedule-plan"
    order: 3
    name: "进度计划确认"
    description: "根据立项批复日期和项目周期生成里程碑进度计划"

    required_data:
      - project_info
      - control_plan     # 步骤2的输出（步骤间有依赖）

    required_rules:
      - duration_rules   # 各阶段标准工期

    llm:
      model: "qwen-max"
      temperature: 0.1   # 进度计划需要非常精确

    prompt_template: |
      根据以下信息生成项目进度计划。

      ## 项目信息
      立项批复日：{{approval_date}}
      项目周期：{{project_duration}}个月

      ## 选定的管控阶段
      {% for phase in selected_phases %}
      - {{phase}}
      {% endfor %}

      ## 各阶段标准工期
      {{duration_rules}}

      请以 JSON 格式返回里程碑进度计划。

    expected_output:
      type: "object"
      required_fields: ["milestones", "gantt_data"]

  - id: "resource-plan"
    order: 4
    name: "资源配置确认"
    description: "根据管控方案和进度计划估算人力资源需求"

    required_data:
      - project_info
      - team_info
      - schedule_plan    # 依赖步骤3的输出

    llm:
      model: "qwen-plus"    # 资源估算用便宜的模型就够了
      temperature: 0.3

    prompt_template: |
      根据项目进度计划和团队情况，估算各阶段的人力资源需求。
      ...（模板内容省略）

    expected_output:
      type: "object"
      required_fields: ["resource_allocation"]

  - id: "quality-plan"
    order: 5
    name: "质量保证计划确认"
    description: "生成质量保证计划，包括测试策略和验收标准"

    required_data:
      - project_info
      - knowledge_rules

    llm:
      model: "qwen-max"
      temperature: 0.2

    prompt_template: |
      根据{{project_level}}级项目的质量标准，生成质量保证计划。
      ...（模板内容省略）
```

### 13.3 配置加载器

```python
# models/config_models.py — 配置文件的 Pydantic Model（自动校验格式）

from pydantic import BaseModel
from typing import Optional


class LLMConfig(BaseModel):
    """LLM 调用参数"""
    model: str = "qwen-max"
    temperature: float = 0.3
    response_format: Optional[str] = None  # "json_object" | None


class StepConfig(BaseModel):
    """步骤配置"""
    id: str                # 步骤标识（如 "team-responsibilities"）
    order: int             # 执行顺序（从1开始）
    name: str              # 步骤名称（显示给用户看的）
    description: str       # 步骤描述
    required_data: list    # 需要从 Java 获取的数据列表
    required_rules: list   # 需要从知识库获取的规则列表
    llm: LLMConfig         # LLM 调用参数
    prompt_template: str   # Prompt 模板（Jinja2 格式）
    expected_output: dict  # 返回数据的验证规则


class FlowConfig(BaseModel):
    """完整的流程配置"""
    metadata: dict         # 基本信息
    conditions: dict       # 适用条件
    steps: list[StepConfig]  # 步骤列表
```

```python
# services/config_loader.py — 配置加载器

import yaml
from pathlib import Path
from models.config_models import FlowConfig


def load_flow_config(config_path: str = "configs/project_proposal.yaml") -> FlowConfig:
    """
    加载 YAML 配置文件并校验

    相当于 JS:
    import fs from 'fs';
    import yaml from 'js-yaml';
    const config = yaml.load(fs.readFileSync('config.yaml', 'utf8'));

    但 Python 这边多了 Pydantic 校验：如果 YAML 格式不对（比如缺少必填字段），
    加载时就会报错，而不是运行到一半才发现问题。
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)  # YAML → Python dict，相当于 JSON.parse()

    # 用 Pydantic 校验 + 转换（类型不匹配会自动报错）
    config = FlowConfig(**raw)

    # 按 order 排序步骤（防止 YAML 里顺序写错）
    config.steps.sort(key=lambda s: s.order)

    print(f"[Config] 已加载配置: {config.metadata['name']}")
    print(f"[Config] 共 {len(config.steps)} 个步骤: {[s.name for s in config.steps]}")

    return config


def get_step_config(flow_config: FlowConfig, step_id: str) -> StepConfig:
    """根据 step_id 查找步骤配置"""
    for step in flow_config.steps:
        if step.id == step_id:
            return step
    raise ValueError(f"未找到步骤配置: {step_id}")


def get_next_step(flow_config: FlowConfig, current_step_id: str) -> StepConfig | None:
    """获取下一步骤（返回 None 表示已是最后一步）"""
    current = get_step_config(flow_config, current_step_id)
    for step in flow_config.steps:
        if step.order == current.order + 1:
            return step
    return None
```

### 13.4 Prompt 模板渲染器

```python
# services/prompt_builder.py — Prompt 模板渲染

from jinja2 import Template
from models.config_models import StepConfig


def render_prompt(step_config: StepConfig, context: dict) -> str:
    """
    把 YAML 里的 Prompt 模板渲染成实际的 Prompt

    参数:
        step_config: 步骤配置（包含 prompt_template）
        context: 模板变量的值，如 {"project_name": "新平台", "team_members": [...]}

    返回:
        渲染后的完整 Prompt 字符串

    相当于 JS 的模板引擎（EJS / Handlebars）:
    const template = ejs.compile("项目名： <%= projectName %>");
    const html = template({ projectName: "新平台" });
    """
    template = Template(step_config.prompt_template)
    return template.render(**context)
```

**使用示例**：
```python
# 加载配置
config = load_flow_config("configs/project_proposal.yaml")

# 获取步骤1的配置
step1 = get_step_config(config, "team-responsibilities")

# 准备模板变量
context = {
    "project_name": "新一代综合业务平台建设项目",
    "project_level": "S",
    "project_description": "支撑公司核心业务数字化转型",
    "team_members": [
        {"name": "陈杰", "role": "项目经理", "department": "信息技术部"},
        {"name": "王磊", "role": "技术负责人", "department": "信息技术部"},
    ],
    "role_definitions": "项目经理：项目计划管控、里程碑评审...",
}

# 渲染 Prompt
prompt = render_prompt(step1, context)
print(prompt)
# 输出：
# 你是一个项目管理助手。根据以下信息，为每个团队成员生成职责描述。
#
# ## 项目信息
# 项目名称：新一代综合业务平台建设项目
# 项目级别：S
# ...
```

### 13.5 配置驱动引擎（把所有东西串起来）

```python
# engine/chat_engine.py — 配置驱动的对话引擎

from models.config_models import FlowConfig, StepConfig
from services.config_loader import load_flow_config, get_step_config, get_next_step
from services.prompt_builder import render_prompt
from engine.llm_client import call_llm, call_llm_json
from engine.session_manager import session_manager


class ChatEngine:
    """
    配置驱动的对话引擎

    核心思想：引擎不硬编码任何业务逻辑，全部从配置读取。
    新增步骤？改 YAML，不改代码。
    新部门？加一份 YAML，不改代码。

    相当于 JS:
    class ChatEngine {
        constructor(configPath) {
            this.config = loadConfig(configPath);
        }
        async start(projectId) { ... }
        async chat(projectId, message) { ... }
    }
    """

    def __init__(self, config_path: str = "configs/project_proposal.yaml"):
        self.config: FlowConfig = load_flow_config(config_path)

    async def start_flow(self, project_id: str, project_data: dict, token: str):
        """
        启动流程（对应 /ai/start 接口）

        1. 从配置读取第一步
        2. 组装 Prompt
        3. 调 LLM
        4. 返回结果
        """
        # 创建会话
        session_manager.create(project_id, {
            "project_info": project_data["project_info"],
            "team_info": project_data["team_info"],
            "knowledge_rules": project_data["knowledge_rules"],
        })

        # 从配置获取第一步
        first_step = self.config.steps[0]

        # 组装 Prompt 并调用 LLM
        prompt = render_prompt(first_step, project_data)
        result = await call_llm_json(
            messages=[
                {"role": "system", "content": "你是一个专业的项目管理助手。"},
                {"role": "user", "content": prompt}
            ],
            model=first_step.llm.model,
            temperature=first_step.llm.temperature,
        )

        # 保存结果
        session_manager.update(project_id, {
            "current_step": first_step.order,
            "step_results": {first_step.id: result}
        })

        return first_step, result

    async def chat(self, project_id: str, message: str):
        """
        处理用户消息（对应 /ai/chat 接口）

        1. 获取当前步骤
        2. 把用户消息追加到对话历史
        3. 调 LLM 修改/优化当前步骤的内容
        """
        session = session_manager.get(project_id)
        current_step = get_step_config(self.config, f"step-{session['current_step']}")

        # 追加到对话历史
        session["chat_history"].append({"role": "user", "content": message})

        # 用 LLM 修改当前步骤
        prompt = f"""
        用户要求修改：
        {message}

        当前已有的内容：
        {session['step_results'][current_step.id]}

        请根据用户要求修改内容，保持 JSON 格式不变。
        """
        result = await call_llm_json(
            messages=[
                {"role": "system", "content": "你是项目管理助手，根据用户反馈修改方案内容。"},
                *session["chat_history"],
                {"role": "user", "content": prompt}
            ],
            model=current_step.llm.model,
            temperature=current_step.llm.temperature,
        )

        # 更新结果
        session_manager.update(project_id, {
            "step_results": {**session["step_results"], current_step.id: result}
        })

        return current_step, result

    async def confirm_and_next(self, project_id: str, step_id: str, confirmed_data: dict):
        """
        确认当前步骤并进入下一步（对应 /ai/confirm-step 接口）
        """
        session = session_manager.get(project_id)

        # 保存确认的数据
        session_manager.update(project_id, {
            "completed_steps": [*session["completed_steps"], step_id],
            "step_results": {**session["step_results"], step_id: confirmed_data}
        })

        # 查找下一步
        next_step = get_next_step(self.config, step_id)
        if not next_step:
            return None  # 全部完成

        # 准备下一步的上下文（可以引用前面步骤的结果）
        context = {
            "project_info": session["project_info"],
            "team_info": session["team_info"],
            "knowledge_rules": session["knowledge_rules"],
            **session["step_results"],  # 前面步骤的结果也可以作为模板变量
        }

        # 生成下一步内容
        prompt = render_prompt(next_step, context)
        result = await call_llm_json(
            messages=[
                {"role": "system", "content": "你是专业的项目管理助手。"},
                {"role": "user", "content": prompt}
            ],
            model=next_step.llm.model,
            temperature=next_step.llm.temperature,
        )

        session_manager.update(project_id, {
            "current_step": next_step.order,
            "step_results": {**session_manager.get(project_id)["step_results"], next_step.id: result}
        })

        return next_step, result


# 全局引擎实例
chat_engine = ChatEngine()
```

### 13.6 更新后的目录结构

```
python-ai-backend/
├── main.py                          # 入口文件
├── .env                             # 环境变量配置
├── requirements.txt                 # 依赖列表
├── configs/
│   ├── project_proposal.yaml        # 项目方案书配置（核心）
│   └── (未来) other_department.yaml # 其他部门的配置
├── config/
│   └── llm_config.py                # LLM 客户端配置
├── engine/
│   ├── chat_engine.py               # 对话引擎（配置驱动核心）
│   ├── llm_client.py                # LLM 调用封装
│   └── session_manager.py           # 会话管理（内存/Redis 双模式）
├── middleware/
│   └── auth.py                      # Token 验证中间件
├── models/
│   ├── request_models.py            # 请求体 Pydantic Model
│   └── config_models.py             # 配置文件 Pydantic Model
├── services/
│   ├── java_api.py                  # Java 接口调用封装
│   ├── config_loader.py             # 配置加载器
│   └── prompt_builder.py            # Prompt 模板渲染
├── dev_utils.py                     # 开发工具（生成测试 Token 等）
└── tests/
    ├── test_chat_engine.py
    └── test_session_manager.py
```

### 13.7 更新后的 requirements.txt

```txt
# Web 框架
fastapi==0.115.0
uvicorn==0.30.0

# HTTP 客户端（调 Java 接口）
httpx==0.27.0

# LLM SDK（通义千问 OpenAI 兼容模式）
openai==1.50.0

# 数据校验
pydantic==2.9.0

# 配置文件解析
pyyaml==6.0

# Prompt 模板渲染（类似 JS 的 EJS/Handlebars）
jinja2==3.1.0

# JWT Token 验证
PyJWT==2.9.0

# 环境变量管理（类似 JS 的 dotenv）
python-dotenv==1.0.1

# SSE 流式输出
sse-starlette==2.0.0

# Redis 客户端（生产环境用，开发阶段可选安装）
redis==5.0.0
```

---

## 十四、待你确认的事项

以上内容根据你提供的5个回答进行了完整补充。还有几个后续事项：

1. **通义千问 API Key** — 你待会发给我，我帮你配到 `.env` 模板里
2. **Java 接口文档** — 等你同事发来后，可能需要对第九章的接口做微调
3. **步骤数量** — YAML 里我按 5 步（加了质量保证计划）配的，原始文档是 4 步，需要你业务确认
4. **Prompt 模板细节** — YAML 里的 Prompt 是骨架，正式版需要你根据实际业务场景细化
