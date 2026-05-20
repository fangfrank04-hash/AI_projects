# 项目方案书AI助手 - Python主导版 v2.0

## 架构概览

```
前端(React) ←SSE流式→ Python FastAPI(+agentscope) ←本地工具→ Mock数据
                                      ↓
                                  通义千问(qwen-max)
```

- **Python主导**：所有业务编排、AI决策、会话管理在Python端
- **SSE流式**：前端通过EventSource与Python建立持久化连接，实时接收AI回复
- **agentscope框架**：ReActAgent + DashScopeChatModel + Toolkit + Skill
- **本地Mock**：开发阶段使用mock数据，不连接真实Java服务

## 项目结构

```
proposal-python-v2/
├── main.py                          # FastAPI入口 + SSE端点
├── agent_setup.py                   # ReActAgent初始化 + 工具注册
├── config.py                        # 配置加载
├── requirements.txt                 # 依赖列表
├── .env.example                     # 环境变量示例
├── start.bat                        # Windows启动脚本
├── start.sh                         # Linux/Mac启动脚本
├── utils/
│   ├── __init__.py
│   └── sse_helper.py                # SSE消息格式化
├── mcp_server/
│   ├── __init__.py
│   ├── mock_data.py                 # Mock数据（项目信息、团队成员）
│   └── server.py                    # MCP Server入口（stdio协议）
└── skills/
    └── team_duty_manager/
        └── SKILL.md                 # 团队职责维护Skill定义
```

## 快速开始

### 1. 配置环境变量

```bash
copy .env.example .env
```

编辑 `.env` 文件，填入你的DashScope API Key：

```
DASHSCOPE_API_KEY=your-dashscope-api-key-here
```

获取API Key：https://dashscope.aliyun.com/

### 2. 安装依赖

```bash
cd proposal-python-v2
pip install -r requirements.txt
```

### 3. 启动服务

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
bash start.sh
```

**手动启动:**
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 启动前端

```bash
cd ../react-frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:5173

### 5. 访问API文档

打开浏览器访问 http://localhost:8000/docs 查看Swagger文档

## SSE接口说明

### 建立连接

```javascript
const eventSource = new EventSource(
  'http://localhost:8000/api/chat/stream?projectId=PJ-202603-S-068&userName=陈杰&isPM=true'
);
```

### SSE事件类型

| 事件名 | 说明 | 数据格式 |
|--------|------|----------|
| `connected` | 连接建立成功 | `{"sessionId": "xxx"}` |
| `preview` | 初始预览数据 | `{"projectData": {...}, "teamData": [...]}` |
| `text` | AI自然语言回复 | `{"content": "..."}` |
| `update_project` | 项目信息更新 | `{"projectData": {...}}` |
| `update_team` | 团队数据更新 | `{"teamData": [...]}` |
| `fillback_complete` | 回填完成 | `{"success": true, "message": "..."}` |
| `error` | 错误提示 | `{"message": "..."}` |
| `ping` | 心跳包 | `{"time": 1234567890}` |

### 发送消息

```javascript
fetch('http://localhost:8000/api/chat/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    sessionId: 'xxx',
    message: '把产品编号改成ABC-001'
  })
});
```

## 本地开发Mock数据

项目信息和团队成员数据存储在 `mcp_server/mock_data.py` 中，内存操作，服务重启后重置。

默认项目：PJ-202603-S-068（验证主表单01221）
默认团队成员：产品经理（李江雪）、项目经理（陈杰）

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| Web框架 | FastAPI | 0.110+ |
| Agent框架 | agentscope | 最新版 |
| LLM | 通义千问 | qwen-max |
| 模型格式化 | DashScopeChatFormatter | agentscope内置 |
| 记忆 | InMemoryMemory | agentscope内置 |
| 前端 | React + Vite | 18 / 5.x |
| 通信 | SSE (EventSource) | 原生 |

## 注意事项

1. **API Key安全**：`.env` 文件不要提交到Git
2. **本地开发**：使用mock数据，不连接真实Java服务
3. **权限控制**：只有isPM=true的用户可以修改数据
4. **可编辑字段**：只有productNo和productName可以修改

## 下一步（V3规划）

- [ ] 接入真实Java数据服务（通过MCP HTTP协议）
- [ ] 实现步骤2-5（管控方案、进度计划、资源计划、质量保证）
- [ ] 方案书检查功能
- [ ] 生产环境SSO/LDAP认证
