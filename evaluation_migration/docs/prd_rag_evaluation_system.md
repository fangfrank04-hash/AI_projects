# RAG 评测系统 — 产品需求文档（PRD）

> 版本：v1.0 | 日期：2025-07-11 | 作者：Alice (Product Manager)

---

## 1. 项目信息

| 项 | 值 |
|---|-----|
| 语言 | 中文 |
| 编程语言 | Python 3.10+ |
| 项目名称 | `rag_evaluation_system` |
| 框架 | Quart (HTTP)，复用 ragflow 现有 LLMBundle |
| 依赖方案 | 方案A：ragas + langchain；方案B：纯 LLMBundle |

**原始需求**：为 ragflow 提供完整的 RAG 评测能力——管理评测数据集、执行评测任务、计算 Faithfulness / Context Precision / Context Recall / Answer Relevancy 四个 LLM-as-Judge 指标，并通过 HTTP API 暴露。同时提供 RAGAS 库方案和手工方案两种实现路径，共用一个公共接口基类。

---

## 2. 产品定义

### 2.1 产品目标

1. **可评测**：让 ragflow 用户能对任意 Dialog 配置进行标准化 RAG 质量评测，获得 Faithfulness、Context Precision、Context Recall、Answer Relevancy 四个核心指标分数。
2. **可对比**：支持多次评测 Run 之间的横向对比，用户能通过指标变化判断配置调整是否有效。
3. **可扩展**：通过统一的 `BaseEvaluator` 抽象基类，使 RAGAS 方案和手工 LLM-as-Judge 方案可互换，且未来可接入更多评测后端而无需改动上层调用代码。

### 2.2 用户故事

| # | 角色 | 场景 | 价值 |
|---|------|------|------|
| US-1 | 知识库管理员 | 我创建了一个评测数据集（20 条 question + reference_answer），绑定到某个知识库，然后对当前的 Dialog 配置发起一次评测 Run，获得 Faithfulness 和 Answer Relevancy 的均分，确认我的 RAG pipeline 没有严重幻觉问题。 | 验证 RAG 质量基线 |
| US-2 | 算法工程师 | 我调整了 chunk_size 和 top_k 参数，发起第 2 次评测 Run 并与第 1 次 Run 的 Context Precision / Context Recall 做对比，发现 top_k=10 时 Precision 下降 12%，于是决定保持 top_k=5。 | 数据驱动参数调优 |
| US-3 | 测试工程师 | 我通过 POST `/api/evaluation/datasets/{id}/cases/import` 批量导入 200 条测试用例（JSON 格式），再调用 POST `/api/evaluation/runs` 发起评测，无需登录 ragflow Web UI 即可完成自动化评测。 | CI/CD 集成自动化评测 |

---

## 3. 需求池

### P0 — 必须交付（首个版本）

| ID | 需求 | 说明 |
|----|------|------|
| P0-1 | `BaseEvaluator` 抽象基类 | 定义 `evaluate(data: dict) -> dict` 统一入口，四个指标名作为输出 key。两个方案（RAGAS / LLMJudge）以此为父类实现。 |
| P0-2 | 方案B：`LLMJudgeEvaluator` | 手工实现 4 个 LLM-as-Judge 指标（见 3.1 节），复用 ragflow 现有 `LLMBundle.chat()` 调用 LLM。 |
| P0-3 | `evaluation_api.py` HTTP 接口 | 基于 Quart 提供数据集 CRUD、测试用例 CRUD、评测 Run 管理、结果查询的 RESTful API。 |
| P0-4 | 评测 Run 执行管道 | 遍历数据集中所有用例 → 调用 RAG pipeline 获取 answer + contexts → 调用 Evaluator 计算指标 → 存入 `EvaluationResult`。 |
| P0-5 | 4 个指标均正确计算 | Faithfulness（0-1）、Context Precision（0-1）、Context Recall（0-1，需 ground_truth）、Answer Relevancy（0-1），单条用例所有指标输出到 `metrics` JSON 字段。 |
| P0-6 | 测试脚本 + Mock 数据 | `tests/test_evaluation.py` + 10 条 mock 用例（含 ground_truth），覆盖 4 个指标的计算逻辑。 |

### P1 — 重要（第二个版本）

| ID | 需求 | 说明 |
|----|------|------|
| P1-1 | 方案A：`RagasEvaluator` | 封装 ragas 库，与 `LLMJudgeEvaluator` 同接口，用户可在创建 Run 时选择 `method: "ragas"` 或 `"llm_judge"`。 |
| P1-2 | 批量导入/导出测试用例 | 支持 JSON 文件导入和 CSV 导出。 |
| P1-3 | 评测结果聚合摘要 | 每次 Run 完成后自动计算 `metrics_summary`（avg/min/max/std），存入 `EvaluationRun.metrics_summary`。 |
| P1-4 | 依赖管理 | 方案A 的 `requirements-ragas.txt` 与方案B 的 `requirements-llmjudge.txt` 分开管理，支持内网打包迁移。 |
| P1-5 | 配置推荐 | 基于评测结果自动给出 chunk_size / top_k / similarity_threshold 调整建议（复用已有 `get_recommendations` 逻辑并增强）。 |

### P2 — 可选（未来版本）

| ID | 需求 | 说明 |
|----|------|------|
| P2-1 | 评测进度回调 | WebSocket 推送 Run 执行进度（当前 n/N）。 |
| P2-2 | 异步评测 | 大数量级评测（500+ 条）通过任务队列异步执行，避免 HTTP 超时。 |
| P2-3 | 可视化 Dashboard | 前端展示指标趋势图、Run 对比雷达图。 |
| P2-4 | 自定义指标插件 | 允许用户注册自定义 Python 函数作为评测指标。 |

### 3.1 四个 LLM-as-Judge 指标说明

| 指标 | 含义 | 需要 ground_truth | 计算方式 |
|------|------|:---:|---------|
| **Faithfulness** | 答案是否忠实于 contexts，有无幻觉 | ❌ | 两阶段：① LLM 从 answer 提取 claims 列表；② 逐条判定每个 claim 是否能从 contexts 推断，比例=faithful/total |
| **Context Precision** | 检索到的文档是否相关且有正确的排序 | ❌ | 逐条判定每个 context 与 question 的相关性（0/1），位置加权：precision@k = (relevant_count_in_top_k) / k |
| **Context Recall** | contexts 是否覆盖了 ground_truth 所需信息 | ✅ | 将 ground_truth 拆成原子句，逐句判定是否能从 contexts 中推断，比例=covered/total |
| **Answer Relevancy** | 答案是否紧扣问题，而非答非所问 | ❌ | 从 answer 反向生成 n 个问题，计算生成问题与原始 question 的语义相似度均值 |

---

## 4. 接口设计概要

### 4.1 RESTful API 列表

所有接口前缀：`/api/v1/evaluation`

#### 数据集管理

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/datasets` | 创建评测数据集 |
| `GET` | `/datasets` | 获取数据集列表（支持分页） |
| `GET` | `/datasets/{dataset_id}` | 获取单个数据集详情 |
| `PUT` | `/datasets/{dataset_id}` | 更新数据集信息 |
| `DELETE` | `/datasets/{dataset_id}` | 删除数据集（软删除） |

#### 测试用例管理

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/datasets/{dataset_id}/cases` | 添加单条测试用例 |
| `GET` | `/datasets/{dataset_id}/cases` | 获取数据集下所有用例 |
| `POST` | `/datasets/{dataset_id}/cases/import` | 批量导入测试用例（JSON body） |
| `DELETE` | `/datasets/{dataset_id}/cases/{case_id}` | 删除单条用例 |

#### 评测执行

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/runs` | 创建并启动评测 Run |
| `GET` | `/runs` | 获取评测 Run 列表 |
| `GET` | `/runs/{run_id}` | 获取 Run 详情（含状态） |
| `GET` | `/runs/{run_id}/results` | 获取 Run 的所有结果详情 |
| `GET` | `/runs/{run_id}/results/{result_id}` | 获取单条结果详情 |

### 4.2 核心数据结构

#### 测试用例（EvaluationCase）

```json
{
  "id": "uuid",
  "dataset_id": "uuid",
  "question": "ragflow 支持哪些向量数据库？",
  "reference_answer": "ragflow 支持 Elasticsearch、Milvus、Qdrant 等向量数据库",
  "relevant_doc_ids": ["doc_001", "doc_002"],
  "relevant_chunk_ids": ["chunk_a", "chunk_b"],
  "metadata": {"source": "manual", "tags": ["basic"]}
}
```

#### 评测请求（创建 Run）

```json
{
  "dataset_id": "uuid",
  "dialog_id": "uuid",
  "name": "v1.2 baseline",
  "method": "llm_judge",
  "metrics": ["faithfulness", "context_precision", "context_recall", "answer_relevancy"]
}
```

其中 `method` 取值为 `"ragas"` | `"llm_judge"`，控制使用哪个 Evaluator。

#### 评测结果（EvaluationResult）

```json
{
  "id": "uuid",
  "run_id": "uuid",
  "case_id": "uuid",
  "question": "ragflow 支持哪些向量数据库？",
  "generated_answer": "ragflow 支持 Elasticsearch 和 Milvus。",
  "retrieved_chunks": [
    {"chunk_id": "chunk_a", "content": "ragflow 集成了 Elasticsearch..."},
    {"chunk_id": "chunk_c", "content": "如何使用 pip 安装 ragflow..."}
  ],
  "metrics": {
    "faithfulness": 0.85,
    "context_precision": 0.60,
    "context_recall": 0.66,
    "answer_relevancy": 0.92
  },
  "execution_time": 2.34,
  "token_usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 340
  }
}
```

#### 评测 Run（EvaluationRun）

```json
{
  "id": "uuid",
  "dataset_id": "uuid",
  "dialog_id": "uuid",
  "name": "v1.2 baseline",
  "method": "llm_judge",
  "config_snapshot": {"top_k": 5, "chunk_size": 512, "model": "gpt-4o-mini"},
  "metrics_summary": {
    "total_cases": 20,
    "avg_faithfulness": 0.81,
    "avg_context_precision": 0.72,
    "avg_context_recall": 0.68,
    "avg_answer_relevancy": 0.85,
    "avg_execution_time": 2.1
  },
  "status": "COMPLETED",
  "created_by": "user_001",
  "create_time": 1720684800,
  "complete_time": 1720685100
}
```

### 4.3 BaseEvaluator 抽象基类设计

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseEvaluator(ABC):
    """评测器抽象基类。方案A(RagasEvaluator)和方案B(LLMJudgeEvaluator)均继承此类。"""

    @abstractmethod
    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        执行评测。

        Args:
            question: 用户原始问题
            answer: RAG 系统生成的答案
            contexts: 检索到的上下文文档列表
            ground_truth: 人工标注正确答案（可选，Context Recall 需要）
            metrics: 需要计算的指标列表，None 表示全部计算

        Returns:
            {"faithfulness": 0.85, "context_precision": 0.60, ...}
        """
        ...

    @staticmethod
    def aggregate(results: List[Dict[str, float]]) -> Dict[str, float]:
        """聚合多条结果的指标均值。"""
        ...
```

---

## 5. 待确认问题

| # | 问题 | 影响 |
|---|------|------|
| Q1 | 方案A（RAGAS）是否需要在 v1.0 交付，还是仅方案B 即可？ | 影响开发工作量约 2-3 天。若仅方案B，P1-1 可推迟。 |
| Q2 | 评测 Run 是同步执行还是异步执行？同步方案简单但大数据集（200+）时 HTTP 可能超时。 | 若需异步，需要引入任务队列（Celery/Redis），P2-2 提升为 P0。 |
| Q3 | LLM-as-Judge 所用的模型是复用 ragflow 的 Chat 模型配置，还是需要独立指定 Judge 模型？ | 若需独立模型，Run 创建请求需增加 `judge_model_config` 字段。 |
| Q4 | 评测数据集是否需要与 ragflow 现有 Knowledge Base 强绑定？还是可以独立存在？ | 已有 `EvaluationDataset.kb_ids` 字段，若不绑定，导入用例时无需校验 kb 存在性。 |
| Q5 | 方案B 的 Faithfulness 两阶段 LLM 调用是否需要支持流式输出？ | 流式会增加实现复杂度但对评测场景价值有限，建议首版不支持。 |
| Q6 | 内网环境 ragas + 依赖的安装方式偏好？（pip download 打包 vs conda 离线包 vs 内网镜像源） | 影响 `requirements-ragas.txt` 的注释说明和交付物。 |
