# -*- coding: utf-8 -*-
"""
RAG 评测系统 — 测试脚本

覆盖方案A（RagasEvaluator）和方案B（LLMJudgeEvaluator）的完整测试。

用法:
    cd D:/AI_projects/zhongzhai_pro/ragflow-main
    python -m pytest tests/test_evaluation.py -v

    # 仅测试方案B（不需要 ragas 依赖）
    python -m pytest tests/test_evaluation.py -v -k "LLMJudge"

    # 仅测试方案A（需要 ragas 依赖）
    python -m pytest tests/test_evaluation.py -v -k "Ragas"

    # 仅测试 API
    python -m pytest tests/test_evaluation.py -v -k "API"
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from evaluation.base import BaseEvaluator
from evaluation.llm_judge_evaluator import LLMJudgeEvaluator

# ============================================================================
# Mock 数据加载
# ============================================================================

MOCK_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "mock_data", "eval_dataset.json"
)


def load_mock_dataset() -> Dict[str, Any]:
    """加载 mock 评测数据集。"""
    with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_mock_cases() -> List[Dict[str, Any]]:
    """加载 mock 评测用例列表。"""
    dataset = load_mock_dataset()
    return dataset.get("cases", [])


# ============================================================================
# Mock LLM Callable（模拟 LLM 响应）
# ============================================================================

class MockLLM:
    """模拟 LLM 的 callable，返回预定义的 JSON 响应。

    用于方案B 的测试，无需真实 LLM API 调用。
    """

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.call_count = 0
        self.call_history: List[List[Dict[str, str]]] = []

    def __call__(self, messages: List[Dict[str, str]]) -> str:
        """模拟 LLM 调用，根据 prompt 内容匹配响应。"""
        self.call_count += 1
        self.call_history.append(messages)

        prompt = messages[0]["content"] if messages else ""

        # 根据 prompt 特征匹配预定义响应
        for keyword, response in self.responses.items():
            if keyword in prompt:
                return response

        # 默认响应
        return '{"verdict": 1}'


def create_mock_llm() -> MockLLM:
    """创建一个配置了完整 mock 响应的 LLM。

    覆盖 Faithfulness、Context Precision、Context Recall 和 Answer Relevancy
    四个指标所需的 LLM 响应。
    """
    responses = {
        # Faithfulness Stage 1: 提取声明
        "extract all atomic factual claims": json.dumps([
            "RAG 是一种检索增强生成技术",
            "RAG 可以减少大语言模型的幻觉",
            "RAG 结合了信息检索和文本生成",
        ]),
        # Faithfulness Stage 2: 验证声明
        "verdict": '{"verdict": 1}',
        # Context Precision: 判定文档相关性
        "relevant": '{"relevant": 1}',
        # Context Recall Stage 1: 拆句
        "split the following reference answer": json.dumps([
            "RAG 是一种检索增强生成技术",
            "RAG 可以减少大语言模型的幻觉",
        ]),
        # Context Recall Stage 2: 归因验证
        "attributed": '{"attributed": 1}',
        # Answer Relevancy Stage 1: 反向生成问题
        "generate exactly": json.dumps([
            "什么是 RAG？",
            "RAG 的全称是什么？",
            "检索增强生成是什么意思？",
        ]),
        # Answer Relevancy Stage 2: 语义相似度
        "similarity": '{"similarity": 0.85}',
    }
    return MockLLM(responses=responses)


# ============================================================================
# 测试：BaseEvaluator
# ============================================================================

class TestBaseEvaluator:
    """测试 BaseEvaluator 抽象基类的工具方法。"""

    def test_aggregate_empty(self):
        """空结果聚合返回空摘要。"""
        result = BaseEvaluator.aggregate([])
        assert result["total"] == 0

    def test_aggregate_basic(self):
        """基本聚合：计算均值。"""
        results = [
            {"faithfulness": 0.8, "context_precision": 0.6, "context_recall": 0.7},
            {"faithfulness": 0.9, "context_precision": 0.5, "context_recall": 0.8},
            {"faithfulness": 0.85, "context_precision": 0.55, "context_recall": 0.9},
        ]
        summary = BaseEvaluator.aggregate(results)
        assert summary["total"] == 3
        assert abs(summary["avg_faithfulness"] - 0.85) < 0.01
        assert abs(summary["avg_context_precision"] - 0.55) < 0.01
        assert abs(summary["avg_context_recall"] - 0.80) < 0.01

    def test_aggregate_with_none(self):
        """None 值被跳过。"""
        results = [
            {"faithfulness": 0.8, "context_recall": None},
            {"faithfulness": 0.9, "context_recall": 0.7},
        ]
        summary = BaseEvaluator.aggregate(results)
        assert summary["total"] == 2
        assert summary["valid_count"]["faithfulness"] == 2
        assert summary["valid_count"]["context_recall"] == 1
        assert abs(summary["avg_faithfulness"] - 0.85) < 0.01
        assert abs(summary["avg_context_recall"] - 0.70) < 0.01

    def test_normalize_metrics_no_ground_truth(self):
        """无 ground_truth 时自动排除 context_recall。"""
        result = BaseEvaluator._normalize_metrics(
            requested=None,
            ground_truth=None,
        )
        assert "context_recall" not in result
        assert "faithfulness" in result
        assert "context_precision" in result
        assert "answer_relevancy" in result

    def test_normalize_metrics_with_ground_truth(self):
        """有 ground_truth 时包含所有指标。"""
        result = BaseEvaluator._normalize_metrics(
            requested=None,
            ground_truth="RAG 是一种技术。",
        )
        assert "context_recall" in result
        assert len(result) == 4

    def test_normalize_metrics_invalid_name(self):
        """不支持的指标名抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的指标"):
            BaseEvaluator._normalize_metrics(
                requested=["invalid_metric"],
                ground_truth=None,
            )


# ============================================================================
# 测试：LLMJudgeEvaluator（方案B）
# ============================================================================

class TestLLMJudgeEvaluator:
    """测试手工 LLM-as-Judge 评测器。"""

    @pytest.fixture
    def evaluator(self):
        """创建带 mock LLM 的评测器。"""
        return LLMJudgeEvaluator(llm_callable=create_mock_llm())

    @pytest.fixture
    def sample_data(self):
        """示例评测数据。"""
        return {
            "question": "什么是 RAG？",
            "answer": "RAG 是一种检索增强生成技术，它可以减少大语言模型的幻觉，结合了信息检索和文本生成。",
            "contexts": [
                "RAG（Retrieval-Augmented Generation）是一种检索增强生成技术。",
                "RAG 通过检索外部文档来减少 LLM 的幻觉问题。",
                "RAG 结合了信息检索和文本生成的能力。",
            ],
            "ground_truth": "RAG 是一种检索增强生成技术。RAG 可以减少大语言模型的幻觉。",
        }

    def test_evaluate_all_metrics(self, evaluator, sample_data):
        """测试所有指标计算。"""
        result = evaluator.evaluate(
            question=sample_data["question"],
            answer=sample_data["answer"],
            contexts=sample_data["contexts"],
            ground_truth=sample_data["ground_truth"],
        )
        assert isinstance(result, dict)
        assert "faithfulness" in result
        assert "context_precision" in result
        assert "context_recall" in result
        assert "answer_relevancy" in result
        # 所有值应在 0~1 之间（或 None）
        for key, val in result.items():
            if val is not None:
                assert 0.0 <= val <= 1.0, f"{key} = {val} 不在 [0, 1] 范围内"

    def test_evaluate_without_ground_truth(self, evaluator, sample_data):
        """无 ground_truth 时 context_recall 为 None。"""
        result = evaluator.evaluate(
            question=sample_data["question"],
            answer=sample_data["answer"],
            contexts=sample_data["contexts"],
            ground_truth=None,
        )
        assert result["context_recall"] is None
        assert result["faithfulness"] is not None

    def test_faithfulness_calculation(self, evaluator, sample_data):
        """Faithfulness: 验证声明提取 + 支撑判定。"""
        faithfulness = evaluator._faithfulness(
            question=sample_data["question"],
            answer=sample_data["answer"],
            contexts=sample_data["contexts"],
        )
        assert isinstance(faithfulness, float)
        assert 0.0 <= faithfulness <= 1.0

    def test_context_precision_calculation(self, evaluator, sample_data):
        """Context Precision: 位置加权验证。"""
        precision = evaluator._context_precision(
            question=sample_data["question"],
            contexts=sample_data["contexts"],
        )
        assert isinstance(precision, float)
        assert 0.0 <= precision <= 1.0

    def test_context_precision_empty_contexts(self, evaluator):
        """空 contexts 返回 0.0。"""
        precision = evaluator._context_precision(
            question="test",
            contexts=[],
        )
        assert precision == 0.0

    def test_context_recall_calculation(self, evaluator, sample_data):
        """Context Recall: ground_truth 拆句 + 归因。"""
        recall = evaluator._context_recall(
            ground_truth=sample_data["ground_truth"],
            contexts=sample_data["contexts"],
        )
        assert isinstance(recall, float)
        assert 0.0 <= recall <= 1.0

    def test_context_recall_no_ground_truth(self, evaluator):
        """无 ground_truth 返回 None。"""
        recall = evaluator._context_recall(
            ground_truth=None,
            contexts=["context"],
        )
        assert recall is None

    def test_context_recall_empty_ground_truth(self, evaluator):
        """空字符串 ground_truth 返回 None。"""
        recall = evaluator._context_recall(
            ground_truth="   ",
            contexts=["context"],
        )
        assert recall is None

    def test_context_recall_empty_contexts(self, evaluator, sample_data):
        """空 contexts 返回 0.0。"""
        recall = evaluator._context_recall(
            ground_truth=sample_data["ground_truth"],
            contexts=[],
        )
        assert recall == 0.0

    def test_answer_relevancy_calculation(self, evaluator, sample_data):
        """Answer Relevancy: 反向生成问题 + 相似度。"""
        relevancy = evaluator._answer_relevancy(
            question=sample_data["question"],
            answer=sample_data["answer"],
        )
        assert isinstance(relevancy, float)
        assert 0.0 <= relevancy <= 1.0

    def test_json_parse_with_markdown(self, evaluator):
        """JSON 解析：支持 Markdown 代码块。"""
        response = '''```json
{"verdict": 1}
```'''
        result = evaluator._parse_json_field(response, "verdict", default=0)
        assert result == 1

    def test_json_parse_plain(self, evaluator):
        """JSON 解析：纯 JSON。"""
        response = '{"verdict": 0}'
        result = evaluator._parse_json_field(response, "verdict", default=1)
        assert result == 0

    def test_json_parse_with_extra_text(self, evaluator):
        """JSON 解析：含额外文本的 JSON。"""
        response = 'Based on the context, here is my verdict:\n{"verdict": 1}'
        result = evaluator._parse_json_field(response, "verdict", default=0)
        assert result == 1

    def test_json_array_parse(self, evaluator):
        """JSON 数组解析。"""
        response = '["claim 1", "claim 2", "claim 3"]'
        result = evaluator._parse_json_array(response)
        assert len(result) == 3
        assert result[0] == "claim 1"

    def test_llm_call_count(self, evaluator, sample_data):
        """验证 LLM 被调用了（非零次数）。"""
        evaluator.evaluate(**sample_data)
        assert evaluator._llm_call.call_count > 0

    def test_mock_dataset_loading(self):
        """验证 mock 数据集正确加载。"""
        dataset = load_mock_dataset()
        assert dataset["name"] == "RAG 评测示例数据集"
        cases = load_mock_cases()
        assert len(cases) == 10

    def test_mock_dataset_structure(self):
        """验证 mock 数据集每条记录的必填字段。"""
        cases = load_mock_cases()
        for case in cases:
            assert "question" in case, f"用例缺少 question: {case}"
            assert len(case["question"]) > 0
            assert "metadata" in case
            assert "difficulty" in case["metadata"]



# ============================================================================
# 测试：RagasEvaluator（方案A — 可选，需要 ragas 库）
# ============================================================================

@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("ragas"),  # type: ignore
    reason="RAGAS 库未安装，跳过方案A测试",
)
class TestRagasEvaluator:
    """测试基于 RAGAS 库的评测器。

    运行前请确保已安装 ragas:
        pip install ragas datasets langchain langchain-openai
    并设置 OPENAI_API_KEY 环境变量。
    """

    @pytest.fixture
    def ragas_evaluator(self):
        """创建 RagasEvaluator。"""
        from evaluation.ragas_evaluator import RagasEvaluator

        # 使用 langchain_openai（需要 OPENAI_API_KEY）
        try:
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        except ImportError:
            pytest.skip("langchain-openai 未安装")

        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY 未设置")

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        return RagasEvaluator(llm=llm, embeddings=embeddings)

    def test_evaluate_single(self, ragas_evaluator):
        """单条评测：计算四个指标。"""
        result = ragas_evaluator.evaluate(
            question="什么是 RAG？",
            answer="RAG 是检索增强生成技术，通过检索外部知识来增强 LLM。",
            contexts=[
                "RAG（Retrieval-Augmented Generation）是一种将检索与生成结合的技术。",
                "RAG 通过从外部知识库检索相关文档来增强大语言模型的回答。",
            ],
            ground_truth="RAG 是一种检索增强生成技术。它通过检索外部知识来增强 LLM。",
        )
        assert "faithfulness" in result
        assert "context_precision" in result
        assert isinstance(result["faithfulness"], (int, float))

    def test_evaluate_batch(self, ragas_evaluator):
        """批量评测。"""
        from evaluation.ragas_evaluator import RagasEvaluator

        result = RagasEvaluator.evaluate_batch(
            questions=["什么是 RAG？", "什么是向量数据库？"],
            answers=[
                "RAG 是检索增强生成技术。",
                "向量数据库存储和检索高维向量数据。",
            ],
            contexts_list=[
                ["RAG 是检索增强生成技术。"],
                ["向量数据库存储向量数据。"],
            ],
            ground_truths=[
                "RAG 是检索增强生成技术。",
                "向量数据库用于存储向量数据。",
            ],
            llm=ragas_evaluator._llm,
            embeddings=ragas_evaluator._embeddings,
        )
        assert "scores" in result
        assert "aggregate" in result
        assert len(result["scores"]) == 2


# ============================================================================
# 测试：evaluation_api（HTTP 接口）
# ============================================================================

class TestEvaluationAPI:
    """测试 RESTful API 端点。"""

    @pytest.fixture
    def client(self):
        """创建测试客户端。
        
        使用独立的 Quart Blueprint 测试，不依赖 ragflow 完整的依赖链。
        测试通过 importlib 直接加载 evaluation_api 模块中的 Blueprint。
        """
        import importlib.util
        from quart import Quart

        module_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "api",
            "apps",
            "restful_apis",
            "evaluation_api.py",
        )

        spec = importlib.util.spec_from_file_location(
            "eval_api_test", os.path.abspath(module_path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        app = Quart(__name__)
        app.register_blueprint(mod.evaluation_bp)
        return app.test_client()

    async def _post_json(self, client, path: str, data: dict):
        """发送 POST 请求。"""
        response = await client.post(
            path,
            json=data,
            headers={"Content-Type": "application/json"},
        )
        return response

    async def _get(self, client, path: str):
        """发送 GET 请求。"""
        return await client.get(path)

    async def _delete(self, client, path: str):
        """发送 DELETE 请求。"""
        return await client.delete(path)

    async def _put(self, client, path: str, data: dict):
        """发送 PUT 请求。"""
        return await client.put(
            path,
            json=data,
            headers={"Content-Type": "application/json"},
        )

    @pytest.mark.asyncio
    async def test_create_dataset(self, client):
        """创建数据集。"""
        response = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "测试数据集", "description": "一个测试数据集"},
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data["code"] == 0
        assert data["data"]["name"] == "测试数据集"

    @pytest.mark.asyncio
    async def test_create_dataset_empty_name(self, client):
        """空名称被拒绝。"""
        response = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "   "},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_datasets(self, client):
        """列出数据集。"""
        # 先创建一个
        await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "列表测试"},
        )
        response = await self._get(client, "/api/v1/evaluation/datasets")
        assert response.status_code == 200
        data = await response.get_json()
        assert data["data"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_dataset(self, client):
        """获取数据集详情。"""
        # 创建
        r = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "详情测试"},
        )
        ds_id = (await r.get_json())["data"]["id"]

        # 获取
        response = await self._get(client, f"/api/v1/evaluation/datasets/{ds_id}")
        assert response.status_code == 200
        data = await response.get_json()
        assert data["data"]["name"] == "详情测试"

    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, client):
        """获取不存在的数据集返回 404。"""
        response = await self._get(client, "/api/v1/evaluation/datasets/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_dataset(self, client):
        """更新数据集。"""
        r = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "旧名称"},
        )
        ds_id = (await r.get_json())["data"]["id"]

        response = await self._put(
            client,
            f"/api/v1/evaluation/datasets/{ds_id}",
            {"name": "新名称"},
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data["data"]["name"] == "新名称"

    @pytest.mark.asyncio
    async def test_delete_dataset(self, client):
        """删除数据集。"""
        r = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "待删除"},
        )
        ds_id = (await r.get_json())["data"]["id"]

        response = await self._delete(client, f"/api/v1/evaluation/datasets/{ds_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_add_case(self, client):
        """添加测试用例。"""
        r = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "用例测试"},
        )
        ds_id = (await r.get_json())["data"]["id"]

        response = await self._post_json(
            client,
            f"/api/v1/evaluation/datasets/{ds_id}/cases",
            {"question": "什么是测试？", "reference_answer": "测试是..."},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_import_cases(self, client):
        """批量导入测试用例。"""
        r = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "导入测试"},
        )
        ds_id = (await r.get_json())["data"]["id"]

        response = await self._post_json(
            client,
            f"/api/v1/evaluation/datasets/{ds_id}/cases/import",
            {
                "cases": [
                    {"question": "Q1?", "reference_answer": "A1"},
                    {"question": "Q2?", "reference_answer": "A2"},
                    {"question": "  ", "reference_answer": ""},  # 空问题应跳过
                ]
            },
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data["data"]["imported"] == 2  # 空问题被跳过

    @pytest.mark.asyncio
    async def test_create_and_get_run(self, client):
        """创建 Run 并获取结果。"""
        # 创建数据集 + 用例
        r = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "Run 测试"},
        )
        ds_id = (await r.get_json())["data"]["id"]

        await self._post_json(
            client,
            f"/api/v1/evaluation/datasets/{ds_id}/cases",
            {"question": "test question?"},
        )

        # 创建 Run
        r = await self._post_json(
            client,
            "/api/v1/evaluation/runs",
            {"dataset_id": ds_id, "name": "测试 Run", "method": "llm_judge"},
        )
        assert r.status_code == 200
        run_data = (await r.get_json())["data"]
        run_id = run_data["run"]["id"]
        assert run_data["run"]["status"] == "COMPLETED"

        # 获取 Run 详情
        response = await self._get(client, f"/api/v1/evaluation/runs/{run_id}")
        assert response.status_code == 200

        # 获取结果列表
        response = await self._get(
            client, f"/api/v1/evaluation/runs/{run_id}/results"
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data["data"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_run_missing_dataset(self, client):
        """使用不存在的数据集创建 Run 返回 404。"""
        response = await self._post_json(
            client,
            "/api/v1/evaluation/runs",
            {"dataset_id": "nonexistent"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_full_workflow(self, client):
        """完整工作流：创建数据集 → 导入用例 → 运行评测 → 查看结果。"""
        # 1. 创建数据集
        r = await self._post_json(
            client,
            "/api/v1/evaluation/datasets",
            {"name": "完整工作流测试"},
        )
        ds_id = (await r.get_json())["data"]["id"]

        # 2. 批量导入用例
        cases = load_mock_cases()[:5]  # 只取前 5 条加速测试
        r = await self._post_json(
            client,
            f"/api/v1/evaluation/datasets/{ds_id}/cases/import",
            {"cases": [
                {"question": c["question"], "reference_answer": c.get("reference_answer")}
                for c in cases
            ]},
        )
        assert (await r.get_json())["data"]["imported"] == 5

        # 3. 运行评测
        r = await self._post_json(
            client,
            "/api/v1/evaluation/runs",
            {
                "dataset_id": ds_id,
                "name": "完整工作流 Run",
                "method": "llm_judge",
            },
        )
        run_id = (await r.get_json())["data"]["run"]["id"]

        # 4. 验证结果
        r = await self._get(client, f"/api/v1/evaluation/runs/{run_id}/results")
        data = await r.get_json()
        assert data["data"]["total"] == 5
        assert data["data"]["run"]["status"] == "COMPLETED"
        assert data["data"]["run"]["metrics_summary"] is not None


# ============================================================================
# 测试：auto_hook（自动评测钩子 — 领导要的接口）
# ============================================================================

class TestAutoHook:
    """测试自动评测钩子：auto_evaluate / with_evaluation / set_llm_callable。"""

    # ------------------------------------------------------------------
    # Mock LLM（模拟 RAG pipeline 中使用的 LLMBundle）
    # ------------------------------------------------------------------

    class MockLLMForHook:
        """模拟 LLMBundle，模拟真实 RAG 项目中的 LLM 调用。"""
        def __init__(self):
            self.call_count = 0

        def chat(self, messages):
            """模拟 LLMBundle.chat(messages) 方法。"""
            self.call_count += 1
            prompt = messages[0]["content"]

            if "extract all atomic" in prompt.lower():
                return '["RAG是一种检索增强生成技术", "RAG可以减少大语言模型的幻觉", "RAG结合了检索和生成"]'
            if "verdict" in prompt.lower():
                return '{"verdict": 1}'
            if "relevant" in prompt.lower():
                return '{"relevant": 1}'
            if "split the following reference answer" in prompt.lower():
                return '["RAG是一种检索增强生成技术", "RAG可以减少大语言模型的幻觉"]'
            if "attributed" in prompt.lower():
                return '{"attributed": 1}'
            if "generate exactly" in prompt.lower():
                return '["什么是RAG？", "RAG的全称是什么？", "检索增强生成是什么意思？"]'
            if "similarity" in prompt.lower():
                return '{"similarity": 0.85}'

            return '{"verdict": 1}'

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture(autouse=True)
    def setup_hook(self):
        """每个测试前重置全局评测器状态。"""
        import evaluation.auto_hook as hook
        hook._default_evaluator = None
        hook._EVAL_LOG_FILE = None
        yield
        hook._default_evaluator = None
        hook._EVAL_LOG_FILE = None

    def _init_hook(self):
        """初始化自动评测钩子。"""
        from evaluation.auto_hook import set_llm_callable
        mock = self.MockLLMForHook()
        set_llm_callable(mock.chat)
        return mock

    # ------------------------------------------------------------------
    # auto_evaluate 函数测试
    # ------------------------------------------------------------------

    def test_auto_evaluate_basic(self):
        """基础用法：RAG 检索后自动评测。"""
        mock = self._init_hook()
        from evaluation.auto_hook import auto_evaluate

        scores = auto_evaluate(
            question="什么是RAG？",
            answer="RAG是检索增强生成技术，可以减少大语言模型的幻觉。",
            contexts=[
                "RAG（Retrieval-Augmented Generation）是一种检索增强生成技术。",
                "RAG通过检索外部文档来减少LLM的幻觉问题。",
            ],
            ground_truth="RAG是一种检索增强生成技术。RAG可以减少大语言模型的幻觉。",
        )
        assert "faithfulness" in scores
        assert "context_precision" in scores
        assert "context_recall" in scores
        assert "answer_relevancy" in scores
        for key, val in scores.items():
            if val is not None:
                assert 0.0 <= val <= 1.0, f"{key}={val} 不在 [0,1]"
        assert mock.call_count > 0, "LLM 应该被调用"

    def test_auto_evaluate_no_ground_truth(self):
        """无 ground_truth 时 context_recall 为 None。"""
        self._init_hook()
        from evaluation.auto_hook import auto_evaluate

        scores = auto_evaluate(
            question="什么是RAG？",
            answer="RAG是...",
            contexts=["RAG是一种技术。"],
            ground_truth=None,
        )
        assert scores["context_recall"] is None
        assert scores["faithfulness"] is not None

    def test_auto_evaluate_with_metrics_filter(self):
        """指定只计算部分指标。"""
        self._init_hook()
        from evaluation.auto_hook import auto_evaluate

        scores = auto_evaluate(
            question="什么是RAG？",
            answer="RAG是...",
            contexts=["RAG是一种技术。"],
            metrics=["faithfulness", "context_precision"],
        )
        assert scores["faithfulness"] is not None
        assert scores["context_precision"] is not None
        assert scores["context_recall"] is None  # 没要求计算
        assert scores["answer_relevancy"] is None

    def test_auto_evaluate_without_init_raises(self):
        """未调用 set_llm_callable 时抛出 RuntimeError。"""
        from evaluation.auto_hook import auto_evaluate

        with pytest.raises(RuntimeError, match="未初始化"):
            auto_evaluate(
                question="test",
                answer="test",
                contexts=["test"],
            )

    def test_auto_evaluate_store_result(self, tmp_path):
        """store_result=True 时写入 JSONL 日志文件。"""
        import evaluation.auto_hook as hook
        self._init_hook()

        log_path = str(tmp_path / "eval_test.jsonl")
        hook.set_eval_log_path(log_path)

        scores = hook.auto_evaluate(
            question="测试问题",
            answer="测试答案",
            contexts=["测试上下文"],
            store_result=True,
            extra_meta={"kb_id": "kb_001"},
        )
        assert scores is not None

        # 验证日志文件
        import json, os
        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline())
        assert entry["question"] == "测试问题"
        assert entry["meta"]["kb_id"] == "kb_001"
        assert "scores" in entry

    # ------------------------------------------------------------------
    # with_evaluation 装饰器测试（领导要的用法）
    # ------------------------------------------------------------------

    def test_with_evaluation_decorator_basic(self):
        """最简用法：装饰器自动附加 evaluation 字段。"""
        self._init_hook()
        from evaluation import with_evaluation

        @with_evaluation()
        def ask_rag(question):
            answer = "RAG是检索增强生成技术，可以减少幻觉。"
            contexts = [
                "RAG是一种检索增强生成技术。",
                "RAG减少了LLM的幻觉问题。",
            ]
            return {"answer": answer, "contexts": contexts}

        result = ask_rag("什么是RAG？")

        # 原始字段还在
        assert result["answer"] is not None
        assert result["contexts"] is not None

        # 自动附加的 evaluation 字段
        assert "evaluation" in result
        assert isinstance(result["evaluation"], dict)
        assert "faithfulness" in result["evaluation"]

    def test_with_evaluation_with_ground_truth(self):
        """装饰器 + ground_truth 参数。"""
        self._init_hook()
        from evaluation import with_evaluation

        @with_evaluation(ground_truth_key="ground_truth")
        def ask_rag(question, ground_truth=None):
            return {
                "answer": "RAG是...",
                "contexts": ["RAG是一种技术。"],
                "ground_truth": ground_truth,
            }

        result = ask_rag("什么是RAG？", ground_truth="RAG是一种技术。RAG可以减少幻觉。")

        assert "evaluation" in result
        assert result["evaluation"]["context_recall"] is not None

    def test_with_evaluation_llm_error_graceful(self):
        """LLM 调用失败时装饰器不崩溃，返回 error 信息。"""
        self._init_hook()
        from evaluation import with_evaluation, set_llm_callable

        # 设置一个会崩溃的 LLM
        def broken_llm(messages):
            raise RuntimeError("LLM 不可用")

        set_llm_callable(broken_llm)

        @with_evaluation()
        def ask_rag(question):
            return {"answer": "test", "contexts": ["test"]}

        result = ask_rag("测试")
        assert result["answer"] == "test"  # 原始结果还在，没崩
        assert "evaluation" in result  # 评测失败，evaluation 字段存在但各指标为 None
        for v in result["evaluation"].values():
            assert v is None or v == 0.0

    def test_with_evaluation_non_dict_return(self):
        """被装饰函数返回非 dict 时不崩溃。"""
        self._init_hook()
        from evaluation import with_evaluation

        @with_evaluation()
        def returns_string(question):
            return "just a string"

        result = returns_string("test")
        assert result == "just a string"  # 原样返回

    def test_with_evaluation_preserves_metadata(self):
        """装饰器保留原函数的元数据（@wraps）。"""
        self._init_hook()
        from evaluation import with_evaluation

        @with_evaluation()
        def my_rag_func(question):
            """这是 RAG 查询函数。"""
            return {"answer": "test", "contexts": []}

        assert my_rag_func.__name__ == "my_rag_func"
        assert "RAG 查询" in (my_rag_func.__doc__ or "")

    # ------------------------------------------------------------------
    # 集成测试：模拟真实 RAG pipeline 中的完整用法
    # ------------------------------------------------------------------

    def test_realaistic_rag_pipeline(self):
        """模拟真实场景：RAG 检索 → 自动评测 → 结果写入日志。"""
        import evaluation.auto_hook as hook
        import tempfile, os, json

        # 1. 初始化
        mock = self.MockLLMForHook()
        hook.set_llm_callable(mock.chat)

        # 2. 设置日志路径
        log_dir = tempfile.mkdtemp()
        log_path = os.path.join(log_dir, "rag_eval.jsonl")
        hook.set_eval_log_path(log_path)

        # 3. 模拟 RAG pipeline
        def rag_search(question):
            answers = {
                "什么是RAG？": (
                    "RAG是检索增强生成技术，可以减少幻觉。",
                    ["RAG是一种检索增强生成技术。", "RAG通过检索外部文档来减少幻觉。"],
                ),
            }
            return answers.get(question, ("不知道", []))

        # 4. 每次 RAG 后自动评测
        questions = ["什么是RAG？", "什么是RAG？"]
        all_scores = []

        for q in questions:
            answer, contexts = rag_search(q)
            scores = hook.auto_evaluate(
                question=q,
                answer=answer,
                contexts=contexts,
                store_result=True,
                extra_meta={"session": "test", "dialogue_id": "d_001"},
            )
            all_scores.append(scores)

        # 验证：两次调用，两次评分，两行日志
        assert len(all_scores) == 2
        assert os.path.exists(log_path)

        with open(log_path, "r") as f:
            lines = f.readlines()
        assert len(lines) == 2

        for line in lines:
            entry = json.loads(line)
            assert "scores" in entry
            assert "faithfulness" in entry["scores"]

        # 清理
        import shutil
        shutil.rmtree(log_dir, ignore_errors=True)
