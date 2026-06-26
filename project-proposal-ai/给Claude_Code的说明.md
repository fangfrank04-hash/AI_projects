# 📋 给 Claude Code (AI助手) 的项目说明

> 本文件用于指导 Claude Code 等AI助手理解项目并执行任务

---

## 一、项目概览

**项目名称**: 项目方案书AI自动填写系统
**架构版本**: Python主导 v2.0
**项目路径**: `D:\AI_projects\zhongzhai_pro\project-proposal-ai`
**当前阶段**: V1开发 - 步骤1（团队职责维护）

---

## 二、必读文档清单

### 2.1 🚀 执行计划（必读！）

> 如果你要执行开发任务，**首先阅读**：
> - `Claude_Code_执行计划.md` - 包含完整的任务清单、执行顺序、验收标准

### 2.2 核心设计文档（按顺序阅读）

| 序号 | 文件名 | 必须阅读 | 说明 |
|------|--------|----------|------|
| 1 | `项目状态总览-v2.md` | ✅ 是 | 全局视图：架构、范围、进度、验收标准 |
| 2 | `01-产品需求文档(PRD)-v2.md` | ✅ 是 | 产品需求：功能点、用户故事、交互流程 |
| 3 | `02-架构设计文档-v2.md` | ✅ 是 | 技术架构：目录结构、接口契约、时序图 |
| 4 | `05-MCP服务设计文档.md` | ✅ 是 | MCP协议设计（Java数据服务调用） |
| 5 | `03-Java后台设计文档.md` | ✅ 是 | Java数据服务接口设计 |
| 6 | `数据库设计文档.md` | ✅ 是 | 数据模型设计 |

### 2.3 代码实现文档

| 序号 | 文件名 | 必须阅读 | 说明 |
|------|--------|----------|------|
| 1 | `proposal-python-v2/README.md` | ✅ 是 | Python后台启动说明 |
| 2 | `proposal-python-v2/main.py` | ✅ 是 | FastAPI入口，接口定义 |
| 3 | `proposal-python-v2/agent_setup.py` | ✅ 是 | Agent初始化、工具注册 |
| 4 | `proposal-python-v2/skills/team_duty_manager/SKILL.md` | ✅ 是 | AI执行流程定义 |
| 5 | `react-frontend/src/App.jsx` | ✅ 是 | 前端交互逻辑 |

### 2.4 参考文档

| 文件名 | 阅读时机 | 说明 |
|--------|----------|------|
| `补全后的前端代码.md` | 改前端样式时参考 | 前端交互样例 |
| `Java接口.jpg` / `java接口2.jpg` | 接真实Java时参考 | Java接口截图 |
| `archive/04-Python_AI后台设计文档.md` | 理解历史设计时参考 | 旧版本（已废弃） |

---

## 三、当前开发范围（V1）

### 3.1 聚焦功能：步骤1 - 团队职责

```
✅ 项目基本信息
   - 查询项目信息
   - AI编辑（仅限：产品编号productNo、产品名称productName）
   - 一键回填

✅ 项目团队信息维护
   - 查询团队成员
   - AI编辑职责（增删改成员职责）
   - 新增/删除成员
   - 一键回填

⏸️ 延后至V2：步骤2-5（建设目标、技术方案、实施计划、效益分析）
```

### 3.2 架构要点

```
前端 ←SSE→ Python FastAPI(+agentscope) → 通义千问
                    ↓ 本地工具调用
                Mock数据 (后续替换为Java MCP服务)
```

**关键点**:
- 本地开发使用Mock数据，不连接真实Java服务
- 所有修改操作需检查`isPM`权限标志
- SSE流式输出，支持多种事件类型（preview/text/update_project等）

---

## 四、代码目录结构

```
project-proposal-ai/
├── 01-产品需求文档(PRD)-v2.md          # 产品需求
├── 02-架构设计文档-v2.md               # 技术架构
├── 03-Java后台设计文档.md              # Java数据服务
├── 05-MCP服务设计文档.md               # MCP协议设计
├── 数据库设计文档.md                   # 数据模型
├── 项目状态总览-v2.md                  # 项目总览
├── 给Claude_Code的说明.md             # AI助手说明（本文档）
├── proposal-python-v2/                # Python后台（主版本）
│   ├── main.py                        # FastAPI入口
│   ├── agent_setup.py                 # Agent初始化
│   ├── config.py                      # 配置
│   ├── requirements.txt               # 依赖
│   ├── skills/
│   │   └── team_duty_manager/
│   │       └── SKILL.md               # AI执行流程
│   ├── mcp_server/                    # MCP服务
│   │   ├── server.py                  # MCP Server
│   │   ├── java_client.py            # Java客户端
│   │   └── mock_data.py              # Mock数据
│   └── utils/
│       └── sse_helper.py              # SSE工具
├── react-frontend/                    # React前端
│   └── src/
│       ├── App.jsx                    # 主组件
│       └── api/
│           └── sseClient.js           # SSE客户端
├── archive/                           # 归档（旧版本文档）
└── 补全后的前端代码.md                  # 前端参考
```

---

## 五、常用命令

### 5.1 Python后台

```bash
# 进入目录
cd D:\AI_projects\zhongzhai_pro\project-proposal-ai\proposal-python-v2

# 安装依赖
pip install -r requirements.txt

# 启动服务（开发模式）
python main.py

# 或使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.2 前端

```bash
# 进入目录
cd D:\AI_projects\zhongzhai_pro\project-proposal-ai\react-frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

---

## 六、AI执行任务时的注意事项

### 6.1 必须遵循的规则

1. **权限控制**: 所有修改操作必须检查`isPM`标志，非PM用户只能查看
2. **字段限制**: 项目基本信息中只有`productNo`和`productName`可修改
3. **错误处理**: 工具调用失败时向用户报告，不自动重试超过2次
4. **数据一致性**: 修改后重新获取数据，确保前端显示最新状态

### 6.2 修改代码前

1. 先阅读相关设计文档，确认需求
2. 理解现有代码结构再修改
3. 保持与现有代码风格一致
4. 添加必要的注释

### 6.3 遇到问题

1. 检查Mock数据是否正确
2. 确认SSE连接是否正常
3. 查看Python服务的日志输出
4. 必要时查看Java接口截图确认字段

---

## 七、关键接口说明

### 7.1 Python FastAPI接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/chat/stream` | GET | SSE流式连接 |
| `POST /api/chat/message` | POST | 发送消息 |
| `POST /api/chat/fillback` | POST | 一键回填 |
| `GET /health` | GET | 健康检查 |

### 7.2 SSE事件类型

| 事件 | 方向 | 说明 |
|------|------|------|
| `connected` | →Client | 连接成功 |
| `preview` | →Client | 初始数据预览 |
| `text` | →Client | AI文本回复 |
| `update_project` | →Client | 项目数据更新 |
| `update_team` | →Client | 团队数据更新 |
| `fillback_complete` | →Client | 回填完成 |
| `error` | →Client | 错误信息 |
| `ping` | →Client | 心跳 |

---

## 八、联系方式

- **产品经理**: 许清楚
- **技术栈**: Python(FastAPI+AgentScope) + React + SSE + 通义千问
- **Java入口**: `POST http://25.50.238.23:8088/portal/RestAction.invoke.do?url=xxx`

---

*本文档由AI助手维护，如有变更请及时更新*
