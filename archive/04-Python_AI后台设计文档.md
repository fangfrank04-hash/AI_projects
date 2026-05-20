# Python AI后台设计文档 - 项目方案书自动填写系统

> **文档版本**：v1.2（MVP版）  
> **更新日期**：2026-05-05  
> **开发策略**：先MVP后优化——标注 `[MVP]` 为初版必做，标注 `[V2]` 为二次开发优化项

---

## 0. 开发阶段规划（新增）

### 0.1 MVP目标（本次开发）

**目标**：快速产出可运行的Demo，给同事演示核心流程  
**时间**：1-2天  
**范围**：
- ✅ FastAPI服务启动
- ✅ 5个生成接口调通（/generate/team-responsibilities 等）
- ✅ 1个对话接口调通（/chat）
- ✅ LLM返回JSON格式数据
- ✅ 会话能存能取（内存版）
- ✅ Swagger文档可访问

**明确不做（V2再做）**：
- ❌ JWT校验（内网Demo，信任Java已校验）
- ❌ 方案书检查接口（FR-007）
- ❌ LLM重试/熔断机制
- ❌ 详细错误分类（统一500）
- ❌ 日志系统（print调试）
- ❌ Prompt安全加固
- ❌ Redis会话（内存够用）

### 0.2 V2优化清单（后续迭代）

| 优先级 | 优化项 | 说明 | 关联章节 |
|--------|--------|------|----------|
| 🔴 P0 | JWT Token校验中间件 | Java传递JWT，Python需校验Token有效性 | 十一、协作约定 |
| 🔴 P0 | 方案书检查接口 `/ai/check` | PRD FR-007要求，5步完成后自动检查完整性 | 六、API路由 |
| 🔴 P0 | API Key安全 | `.env.example` 使用占位符，禁止硬编码真实Key | 八、环境变量 |
| 🟡 P1 | LLM重试机制 | 超时/格式错误时自动重试（最多3次，指数退避） | 五、LLM服务 |
| 🟡 P1 | 熔断机制 | 连续失败N次后暂停调用，返回友好提示 | 五、LLM服务 |
| 🟡 P1 | 错误分类处理 | 区分400/422/500/503，不同错误不同处理 | 六、API路由 |
| 🟡 P1 | 日志系统 | 使用Python logging，记录请求/响应/LLM耗时 | 全模块 |
| 🟡 P1 | Prompt安全加固 | 使用Jinja2 SandboxedEnvironment防注入 | 五、Prompt服务 |
| 🟢 P2 | Redis会话存储 | 多进程/多机部署时共享会话 | 五、会话服务 |
| 🟢 P2 | CORS按环境配置 | 生产环境限制具体域名 | 七、入口文件 |
| 🟢 P2 | 共享Pydantic模型 | 提取ProjectData等公共模型到models.py | 六、API路由 |

---

## 一、技术选型

| 技术项 | 选型 | 版本 | 说明 |
|--------|------|------|------|
| 框架 | FastAPI | ^0.110.0 | 高性能异步Python Web框架 |
| ASGI服务器 | Uvicorn | ^0.27.0 | 异步服务器 |
| HTTP客户端 | httpx | ^0.26.0 | 异步HTTP请求 |
| LLM SDK | OpenAI兼容SDK | ^1.12.0 | 调用通义千问（OpenAI兼容接口） |
| 配置解析 | PyYAML | ^6.0.1 | 解析YAML配置文件 |
| 数据校验 | Pydantic | v2 | FastAPI内置，数据模型校验 |
| 环境变量 | python-dotenv | ^1.0.0 | 加载.env文件 |
| 会话存储(开发) | 本地内存 | - | 开发阶段使用 |
| 会话存储(生产) | Redis | redis-py | 生产环境使用 |

**选型理由**：
- FastAPI原生支持异步，性能高，自动生成交互式API文档
- OpenAI兼容SDK可以直接调用通义千问的OpenAI兼容接口
- YAML配置驱动架构，不同业务通过配置文件适配

---

## 二、项目结构

```
proposal_ai_service/
├── main.py                     # 入口文件
├── config.py                   # 配置加载
├── models.py                   # Pydantic数据模型
├── engine.py                   # ChatEngine核心引擎
├── routers/                    # API路由
│   ├── __init__.py
│   ├── generate.py            # 生成接口（5个步骤）
│   └── chat.py                # 对话接口
├── services/                   # 业务服务
│   ├── __init__.py
│   ├── llm_service.py         # LLM调用服务
│   ├── prompt_service.py      # Prompt模板渲染
│   └── session_service.py     # 会话管理服务
├── config/                     # 配置文件
│   ├── steps.yaml             # 步骤定义（配置驱动核心）
│   └── prompts/               # Prompt模板目录
│       ├── team_responsibilities.txt
│       ├── control_plan.txt
│       ├── schedule.txt
│       ├── resource_plan.txt
│       └── quality_plan.txt
├── utils/                      # 工具函数
│   ├── __init__.py
│   └── json_utils.py          # JSON解析工具
├── .env                        # 环境变量（不提交Git）
├── .env.example                # 环境变量示例
└── requirements.txt            # 依赖列表
```

---

## 三、配置驱动架构（核心设计）

### 3.1 为什么用配置驱动？

**问题**：不同部门的项目方案书填写流程不同（步骤不同、字段不同、规则不同）。

**解决方案**：
- 把**流程定义**抽出来放到YAML配置文件
- 引擎代码**只负责执行流程**，不关心具体业务
- 新增部门时，**只改配置，不改代码**

### 3.2 步骤配置文件（steps.yaml）

```yaml
# config/steps.yaml
# 这个文件定义了AI自动填写的完整流程
# 每个步骤包含：名称、需要的输入、Prompt模板、输出格式

workflow:
  name: "项目方案书自动填写"
  description: "5步确认流程，依次填写团队职责、管控方案、进度计划、资源计划、质量计划"
  
  # 步骤列表
  steps:
    - id: 1
      name: "team_responsibilities"
      display_name: "项目团队职责"
      description: "根据项目级别和团队信息，自动分配各角色职责"
      
      # 需要的输入数据（Java传过来的）
      inputs:
        - name: "project_data"
          type: "object"
          required: true
          description: "项目基本信息"
        - name: "team_data"
          type: "array"
          required: true
          description: "团队成员列表"
        - name: "knowledge_rules"
          type: "object"
          required: true
          description: "知识库规则"
        - name: "history_data"
          type: "object"
          required: false
          description: "历史数据"
      
      # Prompt模板路径
      prompt_template: "prompts/team_responsibilities.txt"
      
      # 输出格式定义（用于校验LLM返回的数据）
      output_schema:
        type: "array"
        items:
          type: "object"
          properties:
            role:
              type: "string"
              description: "角色名称"
            name:
              type: "string"
              description: "人员姓名"
            responsibilities:
              type: "array"
              items:
                type: "string"
              description: "职责列表"
      
      # 用户可输入的指令示例（用于前端placeholder）
      command_examples:
        - "给产品经理增加需求分析职责"
        - "把测试负责人的职责改一下"
        - "增加安全评审职责"

    - id: 2
      name: "control_plan"
      display_name: "管控方案"
      description: "根据项目级别判断可裁剪阶段"
      inputs:
        - name: "project_data"
          type: "object"
          required: true
        - name: "knowledge_rules"
          type: "object"
          required: true
        - name: "history_data"
          type: "object"
          required: false
      prompt_template: "prompts/control_plan.txt"
      output_schema:
        type: "array"
        items:
          type: "object"
          properties:
            phase:
              type: "string"
              description: "阶段名称"
            required:
              type: "boolean"
              description: "是否必须执行"
            result:
              type: "string"
              enum: ["执行", "裁剪"]
              description: "执行结果"
            reason:
              type: "string"
              description: "裁剪说明（如果裁剪）"
      command_examples:
        - "裁剪项目评审阶段"
        - "把需求分析改回执行"
        - "所有阶段都执行"

    - id: 3
      name: "schedule"
      display_name: "项目进度计划"
      description: "根据立项批复日和周期计算里程碑"
      inputs:
        - name: "project_data"
          type: "object"
          required: true
        - name: "approve_date"
          type: "string"
          required: true
          description: "立项批复日"
        - name: "project_cycle"
          type: "string"
          required: true
          description: "项目周期"
        - name: "knowledge_rules"
          type: "object"
          required: true
      prompt_template: "prompts/schedule.txt"
      output_schema:
        type: "array"
        items:
          type: "object"
          properties:
            milestone:
              type: "string"
              description: "里程碑名称"
            start_date:
              type: "string"
              description: "计划开始日期"
            end_date:
              type: "string"
              description: "计划结束日期"
      command_examples:
        - "把开发阶段延长到30天"
        - "立项批复日改成2026-06-01"
        - "重新计算里程碑"

    - id: 4
      name: "resource_plan"
      display_name: "项目资源计划"
      description: "根据工作量数据分配到各成员"
      inputs:
        - name: "project_data"
          type: "object"
          required: true
        - name: "team_data"
          type: "array"
          required: true
        - name: "input"
          type: "object"
          required: true
          description: "用户输入的工作量数据"
        - name: "knowledge_rules"
          type: "object"
          required: true
        - name: "history_data"
          type: "object"
          required: false
      prompt_template: "prompts/resource_plan.txt"
      output_schema:
        type: "object"
        properties:
          total_workload:
            type: "string"
          total_duration:
            type: "string"
          internal_workload:
            type: "string"
          personnel_outsourcing:
            type: "string"
          project_outsourcing:
            type: "string"
          personnel:
            type: "array"
            items:
              type: "object"
              properties:
                role:
                  type: "string"
                name:
                  type: "string"
                workload:
                  type: "string"
      command_examples:
        - "把自有人员工作量改成60"
        - "增加一个架构师"
        - "重新分配工作量"

    - id: 5
      name: "quality_plan"
      display_name: "质量保证计划"
      description: "根据项目级别生成质量目标、评审机制、测试策略"
      inputs:
        - name: "project_data"
          type: "object"
          required: true
        - name: "knowledge_rules"
          type: "object"
          required: true
        - name: "history_data"
          type: "object"
          required: false
      prompt_template: "prompts/quality_plan.txt"
      output_schema:
        type: "object"
        properties:
          quality_goals:
            type: "string"
          review_mechanism:
            type: "array"
            items:
              type: "object"
              properties:
                name:
                  type: "string"
                required:
                  type: "boolean"
                frequency:
                  type: "string"
          test_strategy:
            type: "array"
            items:
              type: "object"
              properties:
                name:
                  type: "string"
                enabled:
                  type: "boolean"
          risk_control:
            type: "string"
      command_examples:
        - "增加性能测试"
        - "把测试覆盖率改成90%"
        - "增加代码审查环节"
```

### 3.3 配置加载器

```python
# config.py
"""
配置加载模块
负责读取YAML配置文件，提供给引擎使用
"""
import yaml
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# 配置文件路径
CONFIG_DIR = Path(__file__).parent / "config"
STEPS_CONFIG_PATH = CONFIG_DIR / "steps.yaml"

class StepConfig:
    """单个步骤的配置"""
    def __init__(self, config_dict: Dict[str, Any]):
        self.id = config_dict["id"]
        self.name = config_dict["name"]
        self.display_name = config_dict["display_name"]
        self.description = config_dict["description"]
        self.inputs = config_dict.get("inputs", [])
        self.prompt_template = config_dict["prompt_template"]
        self.output_schema = config_dict.get("output_schema", {})
        self.command_examples = config_dict.get("command_examples", [])

class WorkflowConfig:
    """工作流配置"""
    def __init__(self, config_path: str = None):
        self.config_path = config_path or STEPS_CONFIG_PATH
        self.steps: Dict[int, StepConfig] = {}
        self.name = ""
        self.description = ""
        self._load()
    
    def _load(self):
        """加载YAML配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        self.name = config["workflow"]["name"]
        self.description = config["workflow"]["description"]
        
        for step_dict in config["workflow"]["steps"]:
            step = StepConfig(step_dict)
            self.steps[step.id] = step
    
    def get_step(self, step_id: int) -> Optional[StepConfig]:
        """获取指定步骤的配置"""
        return self.steps.get(step_id)
    
    def get_all_steps(self) -> List[StepConfig]:
        """获取所有步骤"""
        return list(self.steps.values())
    
    def get_step_count(self) -> int:
        """获取步骤总数"""
        return len(self.steps)

# 全局配置实例（单例模式）
_workflow_config = None

def get_workflow_config() -> WorkflowConfig:
    """获取工作流配置（单例）"""
    global _workflow_config
    if _workflow_config is None:
        _workflow_config = WorkflowConfig()
    return _workflow_config
```

---

## 四、核心引擎设计

### 4.1 ChatEngine类

```python
# engine.py
"""
ChatEngine - AI填写引擎核心类

职责：
1. 加载步骤配置
2. 渲染Prompt模板
3. 调用LLM生成内容
4. 校验输出格式
5. 管理会话状态

设计原则：
- 配置驱动：步骤定义在YAML中，引擎只负责执行
- 无状态：不存储业务数据，数据由Java传入
- 可复用：不同部门只需换配置文件，引擎代码不变
"""
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from config import get_workflow_config, StepConfig
from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.session_service import SessionService
from utils.json_utils import extract_json, validate_json_schema

class ChatEngine:
    """
    AI填写引擎
    
    用法：
        engine = ChatEngine()
        result = await engine.generate_step(1, input_data)
    """
    
    # [MVP] System Message 角色设定
    SYSTEM_MESSAGE = """你是一位资深项目管理专家，擅长编写项目方案书。
你熟悉金融行业的项目管理规范，能够根据项目级别（S/A/B/C级）自动判断管控要求。
你的回答必须严格遵循JSON格式，不要包含任何解释性文字。"""
    
    def __init__(self):
        # 加载配置
        self.workflow_config = get_workflow_config()
        
        # 初始化服务
        self.llm_service = LLMService()
        self.prompt_service = PromptService()
        self.session_service = SessionService()
    
    async def generate_step(self, step_id: int, input_data: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
        """
        生成指定步骤的内容
        
        参数：
            step_id: 步骤ID (1-5)
            input_data: Java传来的输入数据
            session_id: 会话ID（用于多轮对话上下文）
        
        返回：
            {
                "step_id": 1,
                "step_name": "team_responsibilities",
                "content": {...},  # 生成的内容
                "session_id": "xxx"  # 会话ID
            }
        """
        # 1. 获取步骤配置
        step_config = self.workflow_config.get_step(step_id)
        if not step_config:
            raise ValueError(f"步骤 {step_id} 不存在")
        
        # 2. 校验输入数据
        self._validate_inputs(step_config, input_data)
        
        # 3. 渲染Prompt
        prompt = self.prompt_service.render(step_config, input_data)
        
        # 4. 调用LLM生成 [MVP] 启用System Message + 强制JSON
        response = await self.llm_service.generate(
            prompt=prompt, 
            session_id=session_id,
            system_message=self.SYSTEM_MESSAGE,
            force_json=True  # 强制JSON输出，提高格式稳定性
        )
        
        # 5. 解析JSON（LLM返回的是文本，需要提取JSON）
        content = extract_json(response)
        
        # 6. 校验输出格式
        if step_config.output_schema:
            validate_json_schema(content, step_config.output_schema)
        
        # 7. 保存会话（用于后续对话修改）
        new_session_id = self.session_service.save_session(
            session_id=session_id,
            step_id=step_id,
            input_data=input_data,
            output_data=content
        )
        
        return {
            "step_id": step_id,
            "step_name": step_config.name,
            "content": content,
            "session_id": new_session_id
        }
    
    async def chat(self, message: str, session_id: str, current_step: int) -> Dict[str, Any]:
        """
        处理用户的修改指令
        
        参数：
            message: 用户输入的指令
            session_id: 会话ID
            current_step: 当前步骤
        
        返回：
            {
                "message": "AI回复文本",
                "updated_data": {...}  # 修改后的数据
            }
        """
        # 1. 获取会话历史
        session = self.session_service.get_session(session_id)
        if not session:
            return {
                "message": "会话已过期，请重新开始",
                "updated_data": None
            }
        
        # 2. 获取步骤配置
        step_config = self.workflow_config.get_step(current_step)
        
        # 3. 构建对话Prompt（包含历史上下文）
        prompt = self.prompt_service.render_chat(
            step_config=step_config,
            original_data=session["output_data"],
            user_message=message
        )
        
        # 4. 调用LLM [MVP] 对话也启用System Message + 强制JSON
        response = await self.llm_service.generate(
            prompt=prompt,
            session_id=session_id,
            system_message=self.SYSTEM_MESSAGE,
            force_json=True
        )
        
        # 5. 解析结果
        try:
            result = extract_json(response)
            return {
                "message": result.get("message", "已更新"),
                "updated_data": result.get("data")
            }
        except:
            # 如果LLM没有返回JSON，直接返回文本
            return {
                "message": response,
                "updated_data": None
            }
    
    def _validate_inputs(self, step_config: StepConfig, input_data: Dict[str, Any]):
        """校验输入数据是否完整"""
        for input_def in step_config.inputs:
            name = input_def["name"]
            required = input_def.get("required", False)
            
            if required and (name not in input_data or input_data[name] is None):
                raise ValueError(f"步骤 '{step_config.display_name}' 缺少必填参数: {name}")
```

---

## 五、服务层设计

### 5.1 LLM服务 [MVP]

> **V2优化**：增加重试机制、熔断机制、详细日志记录（见0.2节）

```python
# services/llm_service.py
"""
LLM调用服务
负责与通义千问（或其他LLM）通信

[MVP] 基础版本：直接调用，异常抛出
[V2] 优化方向：
  - 增加重试机制（超时/格式错误时自动重试，最多3次，指数退避）
  - 增加熔断机制（连续失败5次后暂停30秒）
  - 增加请求/响应日志（记录耗时、Token用量）
"""
import os
from typing import Optional
from openai import AsyncOpenAI

class LLMService:
    """
    LLM服务
    
    用法：
        llm = LLMService()
        response = await llm.generate("请生成团队职责...", session_id="xxx")
    """
    
    def __init__(self):
        # 从环境变量读取配置
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = os.getenv("LLM_MODEL", "qwen-plus")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))
        
        # 初始化客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    async def generate(self, prompt: str, session_id: Optional[str] = None, 
                       system_message: str = None, force_json: bool = False) -> str:
        """
        调用LLM生成文本
        
        参数：
            prompt: 提示词
            session_id: 会话ID（用于保持上下文）
            system_message: 系统角色设定（如"你是一位项目管理专家"）
            force_json: 是否强制返回JSON格式
        
        返回：
            LLM生成的文本
        """
        try:
            # [MVP] 构建消息列表，支持System Message
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            # [MVP] 调用API参数
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            # [MVP] 强制JSON输出（降低随机性，提高格式稳定性）
            if force_json:
                api_params["response_format"] = {"type": "json_object"}
                api_params["temperature"] = 0.3  # JSON生成时降低随机性
            
            response = await self.client.chat.completions.create(**api_params)
            
            # [V2] 记录Token用量
            # usage = response.usage
            # log.info(f"Token用量: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}")
            
            # 提取生成的文本
            return response.choices[0].message.content
            
        except Exception as e:
            # [MVP] 直接抛出异常，由上层处理
            # [V2] 此处增加重试逻辑和熔断判断
            raise Exception(f"LLM调用失败: {str(e)}")
```

### 5.2 Prompt服务 [MVP]

> **V2优化**：使用SandboxedEnvironment防止模板注入攻击（见0.2节）

```python
# services/prompt_service.py
"""
Prompt模板渲染服务
负责读取模板文件，替换变量，生成最终Prompt

[MVP] 基础版本：标准Jinja2渲染
[V2] 优化方向：
  - 使用Jinja2.SandboxedEnvironment防止模板注入
  - 对输入数据进行HTML转义（如果Prompt包含用户输入）
"""
import os
from pathlib import Path
from typing import Dict, Any
from jinja2 import Template  # [V2] 替换为: from jinja2 import SandboxedEnvironment

from config import StepConfig

class PromptService:
    """
    Prompt服务
    
    用法：
        prompt_service = PromptService()
        prompt = prompt_service.render(step_config, input_data)
    """
    
    def __init__(self):
        self.config_dir = Path(__file__).parent.parent / "config"
    
    def render(self, step_config: StepConfig, input_data: Dict[str, Any]) -> str:
        """
        渲染Prompt模板
        
        参数：
            step_config: 步骤配置
            input_data: 输入数据
        
        返回：
            渲染后的Prompt文本
        """
        # 1. 读取模板文件
        template_path = self.config_dir / step_config.prompt_template
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt模板不存在: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # 2. 使用Jinja2渲染 [MVP]
        template = Template(template_content)
        # [V2] 安全版本：
        # env = SandboxedEnvironment()
        # template = env.from_string(template_content)
        
        # 3. 准备上下文数据
        context = {
            "step_name": step_config.display_name,
            "step_description": step_config.description,
            **input_data  # 展开所有输入数据
        }
        
        return template.render(**context)
    
    def render_chat(self, step_config: StepConfig, original_data: Any, user_message: str) -> str:
        """
        渲染对话Prompt（用于处理用户修改指令）
        
        参数：
            step_config: 步骤配置
            original_data: 原始生成的数据
            user_message: 用户输入的指令
        
        返回：
            对话Prompt
        """
        prompt = f"""你正在协助用户修改【{step_config.display_name}】的内容。

当前数据：
{json.dumps(original_data, ensure_ascii=False, indent=2)}

用户指令：{user_message}

请根据用户指令修改数据，并返回修改后的完整数据。

重要约束：
1. 返回格式必须是JSON，不要包含任何其他文字
2. 保持原有数据结构不变，只修改用户指定的部分
3. 如果用户指令不明确，保持原数据不变

返回格式：
{{
    "message": "修改说明（如：已将产品经理职责更新）",
    "data": {{修改后的完整数据}}
}}
"""
        return prompt
```

### 5.3 会话服务 [MVP]

> **V2优化**：支持Redis存储，解决多进程会话隔离问题（见0.2节）

```python
# services/session_service.py
"""
会话管理服务
开发阶段用内存存储，生产环境用Redis

[MVP] 基础版本：内存字典存储（单进程可用）
[V2] 优化方向：
  - 支持Redis后端（多进程/多机共享）
  - 支持文件存储后端（开发阶段多进程备用方案）
  - 增加会话持久化（服务重启不丢失）
"""
import uuid
import time
from typing import Dict, Any, Optional

class SessionService:
    """
    会话管理服务
    
    用法：
        session = SessionService()
        session_id = session.save_session(None, 1, input_data, output_data)
        history = session.get_session(session_id)
    """
    
    def __init__(self):
        # [MVP] 开发阶段：使用内存存储
        # [V2] 生产阶段：根据环境变量切换为Redis
        # if os.getenv("SESSION_STORAGE") == "redis":
        #     self._backend = RedisBackend()
        # else:
        #     self._backend = MemoryBackend()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._expire_seconds = 3600  # 会话过期时间：1小时
    
    def save_session(self, session_id: Optional[str], step_id: int, 
                     input_data: Dict, output_data: Any) -> str:
        """
        保存会话
        
        参数：
            session_id: 现有会话ID（None则创建新会话）
            step_id: 步骤ID
            input_data: 输入数据
            output_data: 输出数据
        
        返回：
            会话ID
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # 获取或创建会话
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "id": session_id,
                "created_at": time.time(),
                "history": []
            }
        
        # 添加步骤记录
        self._sessions[session_id]["history"].append({
            "step_id": step_id,
            "input": input_data,
            "output": output_data,
            "timestamp": time.time()
        })
        
        self._sessions[session_id]["updated_at"] = time.time()
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话
        
        参数：
            session_id: 会话ID
        
        返回：
            会话数据，不存在或已过期则返回None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        # 检查是否过期
        if time.time() - session["updated_at"] > self._expire_seconds:
            del self._sessions[session_id]
            return None
        
        return session
    
    def get_last_output(self, session_id: str) -> Optional[Any]:
        """获取会话最后一次的输出数据"""
        session = self.get_session(session_id)
        if not session or not session["history"]:
            return None
        return session["history"][-1]["output"]
    
    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
```

---

## 六、API路由设计 [MVP]

> **V2优化**：增加 `/ai/check` 检查接口、JWT校验中间件、错误分类处理（见0.2节）

### 6.1 生成接口

```python
# routers/generate.py
"""
生成接口路由
提供5个步骤的生成接口 + 检查接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from engine import ChatEngine

router = APIRouter(prefix="/ai", tags=["AI生成"])

# 全局引擎实例
engine = ChatEngine()

# ==================== 请求/响应模型 ====================

class ProjectData(BaseModel):
    """项目数据"""
    id: str
    name: str
    level: str
    dept: Optional[str] = None
    pm_name: str
    product_name: Optional[str] = None
    req_dept: Optional[str] = None

class TeamMemberData(BaseModel):
    """团队成员数据"""
    role: str
    name: str
    responsibilities: Optional[list] = None

class GenerateTeamRequest(BaseModel):
    """生成团队职责请求"""
    project_data: ProjectData
    team_data: list[TeamMemberData]
    knowledge_rules: Dict[str, Any]
    history_data: Optional[Dict[str, Any]] = None

class GenerateControlRequest(BaseModel):
    """生成管控方案请求"""
    project_data: ProjectData
    knowledge_rules: Dict[str, Any]
    history_data: Optional[Dict[str, Any]] = None

class GenerateScheduleRequest(BaseModel):
    """生成进度计划请求"""
    project_data: ProjectData
    approve_date: str
    project_cycle: str
    knowledge_rules: Dict[str, Any]

class ResourceInput(BaseModel):
    """资源输入"""
    total_workload: str
    total_duration: str
    internal_workload: str
    personnel_outsourcing: str
    project_outsourcing: str

class GenerateResourceRequest(BaseModel):
    """生成资源计划请求"""
    project_data: ProjectData
    team_data: list[TeamMemberData]
    input: ResourceInput
    knowledge_rules: Dict[str, Any]
    history_data: Optional[Dict[str, Any]] = None

class GenerateQualityRequest(BaseModel):
    """生成质量计划请求"""
    project_data: ProjectData
    knowledge_rules: Dict[str, Any]
    history_data: Optional[Dict[str, Any]] = None

class GenerateResponse(BaseModel):
    """生成响应"""
    step_id: int
    step_name: str
    content: Any
    session_id: str

# ==================== 接口定义 ====================

@router.post("/generate/team-responsibilities", response_model=GenerateResponse)
async def generate_team_responsibilities(request: GenerateTeamRequest):
    """
    生成项目团队职责
    
    输入：项目数据、团队数据、知识库规则、历史数据
    输出：团队职责分配表
    """
    try:
        result = await engine.generate_step(1, request.model_dump())
        return GenerateResponse(**result)
    except Exception as e:
        # [MVP] 统一返回500
        # [V2] 分类处理：
        #   - 输入校验失败 → 400 Bad Request
        #   - LLM格式错误 → 422 Unprocessable Entity
        #   - LLM服务异常 → 503 Service Unavailable
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")

@router.post("/generate/control-plan", response_model=GenerateResponse)
async def generate_control_plan(request: GenerateControlRequest):
    """
    生成管控方案
    
    输入：项目数据、知识库规则、历史数据
    输出：管控方案（各阶段执行/裁剪）
    """
    try:
        result = await engine.generate_step(2, request.model_dump())
        return GenerateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")

@router.post("/generate/schedule", response_model=GenerateResponse)
async def generate_schedule(request: GenerateScheduleRequest):
    """
    生成项目进度计划
    
    输入：项目数据、立项批复日、项目周期、知识库规则
    输出：里程碑时间表
    """
    try:
        result = await engine.generate_step(3, request.model_dump())
        return GenerateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")

@router.post("/generate/resource-plan", response_model=GenerateResponse)
async def generate_resource_plan(request: GenerateResourceRequest):
    """
    生成项目资源计划
    
    输入：项目数据、团队数据、工作量输入、知识库规则、历史数据
    输出：人员工作量分配
    """
    try:
        result = await engine.generate_step(4, request.model_dump())
        return GenerateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")

@router.post("/generate/quality-plan", response_model=GenerateResponse)
async def generate_quality_plan(request: GenerateQualityRequest):
    """
    生成质量保证计划
    
    输入：项目数据、知识库规则、历史数据
    输出：质量目标、评审机制、测试策略
    """
    try:
        result = await engine.generate_step(5, request.model_dump())
        return GenerateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")
```

### 6.3 检查接口 [V2]

> **说明**：PRD FR-007 要求5步完成后自动执行方案书完整性检查，MVP阶段暂不实现，V2补充

```python
# [V2] 新增检查接口
@router.post("/check", response_model=CheckResponse)
async def check_proposal(request: CheckRequest):
    """
    方案书完整性检查
    
    [V2] 实现内容：
    1. 必填字段完整性检查
    2. 逻辑一致性检查（日期是否合理、工作量是否匹配）
    3. 级别合规性检查（S级是否包含安全测试等）
    4. 数据格式检查
    
    输入：完整方案书数据
    输出：检查报告（通过/警告/错误）
    """
    pass  # V2实现
```

### 6.2 对话接口

```python
# routers/chat.py
"""
对话接口路由
处理用户的修改指令
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

from engine import ChatEngine

router = APIRouter(prefix="/ai", tags=["AI对话"])

engine = ChatEngine()

# ==================== 请求/响应模型 ====================

class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: Optional[str] = None
    current_step: int
    draft_data: Optional[Any] = None

class ChatResponse(BaseModel):
    """对话响应"""
    message: str
    updated_data: Optional[Any] = None

# ==================== 接口定义 ====================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    AI对话接口
    
    处理用户的自然语言指令，修改当前步骤的数据
    
    输入：
        - message: 用户指令（如"给产品经理增加需求分析职责"）
        - session_id: 会话ID（首次为空，后续携带）
        - current_step: 当前步骤（1-5）
        - draft_data: 当前草稿数据
    
    输出：
        - message: AI回复文本
        - updated_data: 修改后的数据（如果有）
    """
    try:
        result = await engine.chat(
            message=request.message,
            session_id=request.session_id,
            current_step=request.current_step
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")
```

---

## 七、入口文件 [MVP]

> **V2优化**：增加JWT校验中间件、CORS按环境配置（见0.2节）

```python
# main.py
"""
FastAPI入口文件
启动命令：uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import generate, chat

# 加载环境变量
load_dotenv()

# 创建FastAPI应用
app = FastAPI(
    title="项目方案书AI服务",
    description="基于大模型的项目方案书自动填写服务",
    version="1.0.0"
)

# 配置CORS（允许前端跨域访问）
# [MVP] 允许所有来源（开发方便）
# [V2] 按环境配置：
#   allow_origins=os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # [V2] 生产环境应配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [V2] JWT校验中间件（生产环境启用）
# from fastapi import Depends
# from services.auth_service import verify_jwt
# app.include_router(generate.router, dependencies=[Depends(verify_jwt)])
# app.include_router(chat.router, dependencies=[Depends(verify_jwt)])

# 注册路由
app.include_router(generate.router)
app.include_router(chat.router)

# 健康检查接口
@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "proposal-ai-service"}

# 启动事件
@app.on_event("startup")
async def startup_event():
    print("🚀 AI服务启动成功")
    print(f"📖 API文档: http://localhost:8000/docs")
    print(f"🔧 环境: {os.getenv('ENV', 'development')}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 八、环境变量配置

```bash
# .env.example
# 复制此文件为 .env 并填写实际值

# 环境
ENV=development

# LLM配置（通义千问）
# [MVP] 注意：此处为占位符，请替换为你的真实API Key
# [安全提醒] 永远不要将真实API Key提交到Git！
DASHSCOPE_API_KEY=your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000

# [V2] LLM重试配置
# LLM_MAX_RETRIES=3
# LLM_RETRY_DELAY=1.0
# LLM_CIRCUIT_BREAKER_THRESHOLD=5

# 会话存储（开发用内存，生产用Redis）
SESSION_STORAGE=memory
# [V2] Redis配置
# SESSION_STORAGE=redis
# REDIS_URL=redis://localhost:6379/0

# [V2] CORS配置（生产环境限制域名）
# CORS_ORIGINS=https://your-domain.com,https://admin.your-domain.com

# 日志级别
LOG_LEVEL=INFO
# [V2] 日志文件路径
# LOG_FILE=logs/app.log
```

---

## 九、依赖文件

```txt
# requirements.txt
fastapi==0.110.0
uvicorn[standard]==0.27.0
httpx==0.26.0
openai==1.12.0
pydantic==2.5.0
PyYAML==6.0.1
python-dotenv==1.0.0
Jinja2==3.1.3
redis==5.0.1
```

---

## 十、启动命令

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
copy .env.example .env
# 编辑 .env 文件，填写API Key

# 5. 启动服务（开发模式，带热重载）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 6. 访问API文档
# http://localhost:8000/docs
```

---

## 十一、与Java的协作约定 [MVP]

> **V2优化**：明确JWT传递与校验机制（见0.2节）

### 11.1 接口调用关系

```
Java (Spring Boot)          Python (FastAPI)
    |                              |
    |  POST /ai/generate/xxx       |
    |----------------------------->|
    |  {                           |
    |    "project_data": {...},    |
    |    "team_data": [...],       |
    |    "knowledge_rules": {...}  |
    |  }                           |
    |                              |
    |  {                           |
    |    "step_id": 1,             |
    |    "step_name": "team",      |
    |    "content": {...},         |
    |    "session_id": "xxx"       |
    |  }                           |
    |<-----------------------------|
```

### 11.2 关键原则

| 原则 | 说明 | MVP/V2 |
|------|------|--------|
| **Python不碰数据库** | Python只接收Java传来的数据，不调数据库 | ✅ MVP |
| **Python不调Java** | Python是纯服务，被动等待Java调用 | ✅ MVP |
| **数据完整性** | Java调用Python时传入所有需要的数据 | ✅ MVP |
| **无状态** | Python服务无状态，不依赖本地存储（会话除外） | ✅ MVP |
| **配置驱动** | 业务逻辑在YAML中，引擎代码零改动适配 | ✅ MVP |
| **JWT校验** | Java传递JWT Token，Python校验用户身份 | 🔴 V2 |

### 11.3 JWT传递方案 [V2]

```
[MVP] 当前方案：
Java → Python 的HTTP请求中不携带JWT
Python 不校验身份，信任内网调用

[V2] 推荐方案：
1. Java调用Python时，在HTTP Header中携带JWT：
   Authorization: Bearer <jwt_token>

2. Python增加JWT校验中间件：
   - 提取Header中的Token
   - 验证Token签名和过期时间
   - 解析用户信息（user_id, role等）
   - 非项目经理角色返回403

3. Python不自己颁发Token，只校验Java传来的Token
```

**[V2] 待确认问题**：
- Java端使用的JWT库和签名算法？
- Python端需要哪些公钥/密钥来验证签名？
- Token中需要包含哪些字段（user_id, role, dept等）？

---

## 十二、配置驱动架构的优势

### 12.1 当前项目

当前项目的5个步骤定义在 `config/steps.yaml` 中，引擎代码无需改动。

### 12.2 新增部门（示例）

假设新增一个部门，只需要3个步骤（团队、进度、质量）：

```yaml
# config/steps_new_dept.yaml
workflow:
  name: "新项目方案书自动填写"
  steps:
    - id: 1
      name: "team_responsibilities"
      # ... 配置
    - id: 2
      name: "schedule"
      # ... 配置
    - id: 3
      name: "quality_plan"
      # ... 配置
```

**引擎代码完全不用改**，只需要：
1. 换配置文件
2. 新增对应的Prompt模板

### 12.3 复用到其他项目

Python AI服务可以作为独立服务部署，任何项目（Java/Node/Go等）都可以调用：

```bash
# 其他项目调用Python AI服务
curl -X POST http://localhost:8000/ai/generate/team-responsibilities \
  -H "Content-Type: application/json" \
  -d '{
    "project_data": {...},
    "team_data": [...],
    "knowledge_rules": {...}
  }'
```

---

---

## 十三、AI编码助手提示（新增）

### 给AI的指令模板

当你（AI编码助手）根据本文档生成代码时，请遵循以下原则：

1. **优先实现MVP功能**：只实现标记为 `[MVP]` 的代码，跳过 `[V2]` 部分
2. **保留V2注释**：在代码中用注释标记 `[V2]` 优化点，方便后续迭代
3. **先问后猜**：遇到未明确的需求（如JWT算法、Redis配置），不要猜测，标注`# TODO: 待确认`
4. **保持简洁**：MVP阶段不过度设计，能跑通就行
5. **安全底线**：即使MVP，也不要硬编码真实API Key或密码

### 代码生成Checklist

- [ ] 所有 `.py` 文件能正常导入（无循环依赖）
- [ ] `uvicorn main:app --reload` 能启动
- [ ] `http://localhost:8000/docs` 能看到Swagger界面
- [ ] 5个生成接口和1个对话接口已注册
- [ ] `.env.example` 中API Key是占位符
- [ ] 代码中有 `[V2]` 标记的优化提示

---

**文档结束**

> **版本历史**：
> - v1.0 (2026-05-04)：初始版本
> - v1.1 (2026-05-05)：增加MVP/V2阶段规划、优化清单、AI编码提示
> - v1.2 (2026-05-05)：AI工程优化——增加System Message角色设定、强制JSON输出、对话Prompt约束
