# 项目方案书 AI 自动填写系统

三服务架构的 AI 辅助项目方案书自动填写系统：前端 → Java 后台 → Python AI → 通义千问。

## 架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                          用户浏览器 (React 18)                        │
│                     http://localhost:3000                             │
│              项目方案书页面 + AI 聊天机器人（右下角）                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTP (JWT Bearer Token)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      Java 后台 (Spring Boot 3.2)                     │
│                     http://localhost:8080                             │
│                                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────────┐  │
│  │ Controller   │  │  Service      │  │  Security (JWT Filter)       │  │
│  │ AuthController│  │ ProposalService│ │  ┌──────────┐ ┌──────────┐ │  │
│  │ ProposalCtrl  │  │ ProjectService │  │  │TokenSvc  │ │JwtFilter │ │  │
│  │ KnowledgeCtrl │  │ KnowledgeSvc   │  │  └──────────┘ └──────────┘ │  │
│  │ HistoryCtrl   │  │ HistorySvc     │  │                            │  │
│  │ ProjectCtrl   │  │ OperationLogSvc│  │  [V2] SSO / Redis          │  │
│  └─────────────┘  └──────┬─────────┘  └─────────────────────────────┘  │
│                          │                                            │
│                    ┌─────┴─────┐                                      │
│                    │   JPA     │                                      │
│                    │  (H2/MySQL)                                     │
│                    └───────────┘                                      │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ WebClient (HTTP)
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      Python AI 服务 (FastAPI)                         │
│                     http://localhost:8000                             │
│                                                                      │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────────────┐   │
│  │ routers/         │  │ services/       │  │ config/               │   │
│  │  generate.py     │  │ llm_service.py  │  │ steps.yaml (工作流定义) │   │
│  │  chat.py         │  │ prompt_svc.py   │  │ prompts/ (Jinja2模板) │   │
│  └─────────────────┘  │ session_svc.py  │  └──────────────────────┘   │
│                       └────────┬───────┘                             │
│                                │ OpenAI SDK                           │
└────────────────────────────────┼─────────────────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   通义千问 (DashScope)     │
                    │   qwen-plus / qwen-max    │
                    └─────────────────────────┘
```

### 数据流

```
用户点击 → 前端 POST /api/project/{id}/ai/generate/{step}
         → Java PromptBuilder 组装数据
         → WebClient POST → Python /ai/generate/{step}
         → Engine 加载 prompt 模板 + YAML 步骤配置
         → LLM Service 调用 通义千问
         → 返回 JSON → Java 保存到数据库 → 返回前端展示
```

## 项目结构

```
project-proposal-ai/
├── README.md                    # 本文件
├── test-e2e.sh                  # 端到端集成测试脚本
├── proposal-python/             # Python AI 服务 (FastAPI)
│   ├── main.py                  # 入口，7 条路由
│   ├── config.py                # 工作流配置加载
│   ├── models.py                # Pydantic 数据模型
│   ├── engine.py                # 对话引擎
│   ├── routers/                 # API 路由
│   ├── services/                # LLM / Prompt / Session
│   ├── config/                  # YAML + prompt 模板
│   └── utils/                   # JSON 工具
├── proposal-java/               # Java 后台 (Spring Boot)
│   └── src/main/
│       ├── java/com/ccdc/proposal/
│       │   ├── config/          # Security / WebClient / Cache
│       │   ├── controller/      # REST 控制器
│       │   ├── dto/             # 数据传输对象
│       │   ├── entity/          # JPA 实体
│       │   ├── exception/       # 全局异常处理
│       │   ├── repository/      # JPA Repository
│       │   ├── security/        # JWT / Token
│       │   └── service/         # 业务逻辑 + AI 客户端
│       └── resources/
│           ├── application.yml
│           ├── application-dev.yml
│           ├── application-prod.yml
│           ├── schema.sql
│           └── data.sql
└── react-frontend/              # 前端 (React 18 + Vite + Tailwind)
    ├── index.html
    ├── vite.config.js           # 代理 /api → localhost:8080
    ├── tailwind.config.js
    └── src/
        ├── App.jsx              # 主组件（方案书页面 + AI 聊天机器人）
        ├── main.jsx             # React 入口
        └── index.css            # Tailwind + 全局样式
```

## 快速启动

### 1. 环境要求

| 服务 | 依赖 | 版本要求 |
|------|------|----------|
| Python AI | Python + pip | >= 3.11 |
| Java 后台 | JDK + Maven | JDK 17+, Maven 3.8+ |
| 前端 | Node.js + npm | Node 18+, npm 9+ |

### 2. 启动 Python AI 服务

```bash
cd proposal-python

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 DashScope API Key
# DASHSCOPE_API_KEY=your-real-api-key

# 安装依赖
pip install -r requirements.txt

# 启动服务（开发模式，支持热重载）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 验证
curl http://localhost:8000/health
# 返回: {"status":"ok","service":"proposal-ai"}
```

### 3. 启动 Java 后台

```bash
cd proposal-java

# 开发环境（H2 文件数据库，端口 8080）
mvn spring-boot:run -Dspring-boot.run.profiles=dev

# 生产环境（MySQL，需要先配置 application-prod.yml）
# mvn spring-boot:run -Dspring-boot.run.profiles=prod

# 验证
curl http://localhost:8080/api/auth/test-token
# 返回: {"token":"eyJ..."}
```

### 4. 启动前端

```bash
cd react-frontend

# 安装依赖（首次）
npm install

# 启动开发服务器（端口 3000）
npm run dev

# 浏览器打开 http://localhost:3000
```

> 前端 Vite 已配置代理：`/api/*` → `http://localhost:8080`，开发时无需额外配置。

### 5. 验证全链路

```bash
# 获取 JWT token
TOKEN=$(curl -s http://localhost:8080/api/auth/test-token | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 调用 AI 生成步骤1（团队职责）
curl -X POST http://localhost:8080/api/project/P001/ai/generate/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# 预期返回: {"stepId":1,"content":[...团队职责数据...],"sessionId":"..."}
```

## 环境变量配置

### Python AI 服务 (.env)

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DASHSCOPE_API_KEY` | 通义千问 API Key | `sk-placeholder` |
| `LLM_MODEL` | 模型名称 | `qwen-plus` |
| `LLM_BASE_URL` | API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

### Java 后台 (application-{profile}.yml)

| 变量 | 开发环境 (dev) | 生产环境 (prod) |
|------|---------------|-----------------|
| 数据库 | H2 (file:./data/proposal_db) | MySQL |
| 端口 | 8080 | 8080 |
| SSO | 禁用（简单 JWT） | 启用 |
| CORS | 允许所有来源 | 白名单 |
| AI 服务地址 | http://localhost:8000 | 配置 `ai.service.url` |

## 开发 vs 生产环境切换

### Java 后台

```bash
# 开发：H2 数据库，自动建表，seed data
mvn spring-boot:run -Dspring-boot.run.profiles=dev

# 生产：MySQL，禁用自动建表，启用 SSO
mvn spring-boot:run -Dspring-boot.run.profiles=prod
```

### Python AI 服务

```bash
# 开发：热重载，debug 日志
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# 生产：多 worker，info 日志
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info
```

### 前端

```bash
# 开发：Vite dev server + HMR
npm run dev

# 生产构建
npm run build
# 输出到 dist/，部署到 Nginx/CDN
```

## API 接口清单

### Java 后台 (port 8080)

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/auth/sso-login` | SSO 登录 [V2] | 否 |
| GET | `/api/auth/test-token` | 获取测试 token [MVP] | 否 |
| GET | `/api/project/{id}/proposal` | 获取方案书 | JWT |
| POST | `/api/project/{id}/ai/generate/{step}` | AI 生成步骤 (1-5) | JWT + PM |
| POST | `/api/project/{id}/ai/chat` | AI 对话 | JWT + PM |
| POST | `/api/project/{id}/ai/check` | AI 方案书检查 | JWT + PM |
| PUT | `/api/project/{id}/proposal` | 更新/确认步骤 | JWT + PM |
| PUT | `/api/project/{id}/confirm` | 确认方案书 | JWT + PM |

### Python AI 服务 (port 8000)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/ai/generate/team-responsibilities` | 生成团队职责 |
| POST | `/ai/generate/control-plan` | 生成管控方案 |
| POST | `/ai/generate/schedule` | 生成进度计划 |
| POST | `/ai/generate/resource-plan` | 生成资源计划 |
| POST | `/ai/generate/quality-plan` | 生成质量保证计划 |
| POST | `/ai/chat` | 通用对话 |

## 5 步方案书填写流程

```
步骤1: 项目团队职责 → 自动分配每个成员的职责
步骤2: 管控方案      → 根据项目级别裁剪阶段（开发/测试不可裁剪）
步骤3: 进度计划      → 根据立项批复日和周期生成里程碑时间
步骤4: 资源计划      → 分配工作量（总工作量/总工期/自有/外包）
步骤5: 质量保证      → 质量目标 + 评审机制 + 测试策略 + 质量指标
```

每一步：AI 生成预览 → 项目经理确认/修改 → 一键回填 → 进入下一步。

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 前端 | React + Vite + Tailwind CSS + lucide-react | 18 / 5 / 3.4 / 0.263 |
| Java | Spring Boot + JPA + Security + WebFlux | 3.2.5 |
| 数据库 | H2 (dev) / MySQL (prod) | - |
| Python | FastAPI + OpenAI SDK + Jinja2 + PyYAML | >= 3.11 |
| LLM | 通义千问 (DashScope) | qwen-plus |
| 认证 | JWT (jjwt 0.12.5) | MVP: 简单模式 |
