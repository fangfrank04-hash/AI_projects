# Claude Code 执行计划 - 项目方案书AI自动填写系统

> 本文档用于指导 Claude Code 执行下午的全部开发任务
> 更新时间: 2026-05-07 下午

---

## 一、任务背景

### 1.1 当前系统状态

| 模块 | 状态 | 说明 |
|------|------|------|
| Java接口代码 | ✅ 已完成 | `proposal-java/` RestActionController 实现了所有接口 |
| Java接口文档 | ✅ 已完成 | `03-Java后台设计文档.md` 定义清晰 |
| Mock假数据 | ✅ 已造好 | `mock_data.py` 有完整假数据 |
| MCP Server | ✅ 已完成 | `server.py` 定义了工具 |
| JavaClient封装 | ✅ 已完成 | `java_client.py` HTTP调用封装 |
| Python后台框架 | ✅ 已完成 | `proposal-python-v2/` FastAPI + AgentScope |
| 前端代码 | ✅ 已完成 | `react-frontend/` SSE客户端 |

### 1.2 架构概览

```
前端(React)
    │ SSE
    ▼
Python FastAPI(+AgentScope) ──→ 通义千问
    │
    ├─ DEV_MODE=true → mock_data.py (当前走这里)
    │
    └─ DEV_MODE=false → java_client.py → Java接口
                              │
                              ▼
                    Java Spring Boot (H2/MySQL)
```

### 1.3 关键路径

```
项目根目录: D:\AI_projects\zhongzhai_pro\project-proposal-ai

Java后台:   proposal-java/          (端口: 8088)
Python后台: proposal-python-v2/     (端口: 8000)
前端:       react-frontend/          (端口: 5173)
```

---

## 二、下午任务清单

### 阶段一：环境准备与依赖安装

#### 任务 1.1：安装 Python 依赖

```bash
cd D:\AI_projects\zhongzhai_pro\project-proposal-ai\proposal-python-v2
pip install -r requirements.txt
```

**预期依赖**:
- fastapi >= 0.110.0
- uvicorn[standard] >= 0.27.0
- agentscope
- mcp
- pydantic >= 2.5.0
- python-dotenv >= 1.0.0
- httpx (java_client.py 需要)

**如果安装失败**:
- 检查网络连接
- 尝试使用国内镜像: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

#### 任务 1.2：安装 Node.js 依赖（前端）

```bash
cd D:\AI_projects\zhongzhai_pro\project-proposal-ai\react-frontend
npm install
```

### 阶段二：Mock数据验证（先验证流程）

#### 任务 2.1：启动 Python 服务（Mock模式）

```bash
cd D:\AI_projects\zhongzhai_pro\project-proposal-ai\proposal-python-v2

# 设置环境变量
set DASHSCOPE_API_KEY=你的通义千问API_KEY
set DEV_MODE=true

# 启动服务
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**验证方法**:
1. 浏览器打开 http://localhost:8000/health
2. 应返回: `{"status":"ok","service":"proposal-ai-python-v2","version":"2.0.0",...}`
3. 打开 http://localhost:8000/docs 查看 API 文档

#### 任务 2.2：验证 SSE 连接

**方法1：使用浏览器**
1. 打开前端页面
2. 检查浏览器控制台是否有 SSE 连接日志
3. 检查是否显示项目数据预览

**方法2：使用 curl**
```bash
# 注意：SSE 不能用 curl 直接测试，需要用 EventSource 或前端测试
```

**方法3：编写测试脚本**
```python
# test_sse.py
import sseclient
import requests

response = requests.get(
    'http://localhost:8000/api/chat/stream',
    params={'projectId': 'PJ-202603-S-068', 'userName': '测试用户', 'isPM': 'true'},
    stream=True
)
client = sseclient.SSEClient(response)
for event in client.events():
    print(f"事件: {event.event}, 数据: {event.data}")
```

#### 任务 2.3：验证 Agent 工具调用

**发送测试消息**:
```bash
# 发送消息测试
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"test-session","message":"你好"}'
```

**预期行为**:
1. SSE 推送 preview 事件（项目数据和团队数据）
2. SSE 推送 text 事件（AI 问候语）
3. 如果发送修改指令，应返回 update_project 或 update_team 事件

### 阶段三：启动 Java 服务（可选，先跳过）

> 如果 Mock 验证通过，可以跳过此阶段，先完成其他任务

#### 任务 3.1：启动 Java 服务

```bash
cd D:\AI_projects\zhongzhai_pro\project-proposal-ai\proposal-java

# 方式1：使用 Maven
mvn spring-boot:run -Dspring-boot.run.profiles=dev

# 方式2：使用 jar
# java -jar target/proposal-java-1.0.0.jar --spring.profiles.active=dev
```

**验证方法**:
```bash
curl -X POST "http://localhost:8088/portal/RestAction.invoke.do?url=/itmp/pmProjectService/findProjectById" \
  -d "param={\"id\":\"PJ-202603-S-068\"}"
```

**预期响应**:
```json
{
  "id": "PJ-202603-S-068",
  "name": "验证主表单01221",
  "dept": "信息科技部",
  ...
}
```

### 阶段四：问题修复

#### 常见问题与解决方案

**问题1：agentscope 安装失败**
```
解决: pip install agentscope -i https://pypi.tuna.tsinghua.edu.cn/simple
或查看 agentscope 官方文档获取正确安装方式
```

**问题2：端口被占用**
```
解决: 
- 8000 被占用: uvicorn main:app --port 8001
- 8088 被占用: netstat -ano | findstr 8088，然后结束对应进程
```

**问题3：Agent 报 API Key 错误**
```
解决: 确保设置了正确的 DASHSCOPE_API_KEY 环境变量
```

**问题4：SSE 连接失败**
```
解决: 
- 检查 Python 服务是否正常运行
- 检查 CORS 配置是否正确
- 检查防火墙设置
```

### 阶段五：前端集成测试

#### 任务 5.1：启动前端

```bash
cd D:\AI_projects\zhongzhai_pro\project-proposal-ai\react-frontend
npm run dev
```

#### 任务 5.2：验证完整流程

1. **连接测试**: 打开页面，检查 SSE 是否连接成功
2. **数据展示**: 检查项目信息和团队成员是否正确显示
3. **AI对话**: 输入"你好"或"介绍一下"
4. **数据修改**: 输入"把产品编号改成ABC-123"
5. **一键回填**: 点击回填按钮，检查数据是否同步

### 阶段六：代码优化（如有时间）

#### 任务 6.1：检查代码完整性

1. 检查所有工具函数是否正确注册
2. 检查错误处理是否完善
3. 检查日志输出是否清晰

#### 任务 6.2：补充文档

1. 更新 `给Claude_Code的说明.md`
2. 更新 `项目状态总览-v2.md`

---

## 三、执行顺序建议

```
下午时间安排建议:

14:00-14:30  任务1-2：安装依赖、启动服务
14:30-15:00  任务2：Mock验证、修复问题
15:00-15:30  任务3：启动Java服务、验证接口
15:30-16:00  任务4：端到端联调
16:00-16:30  任务5：前端测试
16:30-17:00  任务6：收尾优化
```

---

## 四、验收标准

### 4.1 Python 服务验收

- [ ] `/health` 接口返回正常
- [ ] SSE 连接能建立
- [ ] `preview` 事件推送项目数据
- [ ] AI 能正确理解并回复消息

### 4.2 Java 服务验收

- [ ] `/itmp/pmProjectService/findProjectById` 返回项目数据
- [ ] `/itmp/pmProjectMemberService/findPmProjectMemberList` 返回团队数据
- [ ] 更新接口能正确修改数据

### 4.3 端到端验收

- [ ] 前端能显示项目基本信息
- [ ] 前端能显示团队成员列表
- [ ] AI 能根据自然语言修改数据
- [ ] 修改后数据能同步到前端
- [ ] 一键回填功能正常

---

## 五、关键文件参考

| 文件 | 说明 |
|------|------|
| `proposal-python-v2/main.py` | FastAPI 入口 |
| `proposal-python-v2/agent_setup.py` | Agent 配置 |
| `proposal-python-v2/skills/team_duty_manager/SKILL.md` | AI 技能定义 |
| `proposal-python-v2/mcp_server/mock_data.py` | Mock 数据 |
| `proposal-python-v2/mcp_server/java_client.py` | Java 调用封装 |
| `proposal-java/src/main/java/com/ccdc/proposal/controller/RestActionController.java` | Java 接口实现 |
| `03-Java后台设计文档.md` | Java 接口文档 |

---

## 六、联系方式

- **产品经理**: 许清楚
- **技术问题**: 查看 `给Claude_Code的说明.md` 了解更多背景

---

*本文档由 AI 助手生成，用于指导 Claude Code 执行任务*
