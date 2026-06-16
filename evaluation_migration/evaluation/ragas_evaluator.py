# -*- coding: utf-8 -*-
"""
方案A：基于 RAGAS 库的评测器

封装 ragas 的 evaluate() 函数，提供与 LLMJudgeEvaluator 统一的接口。

依赖：ragas, datasets, langchain, langchain-openai
外网安装：pip install ragas datasets langchain langchain-openai
内网部署：pip download 打包后传入

用法:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from evaluation import RagasEvaluator

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    evaluator = RagasEvaluator(llm=llm, embeddings=embeddings)
    result = evaluator.evaluate(question, answer, contexts, ground_truth)
"""

import logging
from typing import Any, Dict, List, Optional

from evaluation.base import BaseEvaluator

logger = logging.getLogger(__name__)


class RagasEvaluator(BaseEvaluator):
    """基于 RAGAS 库的评测器。

    使用 ragas.evaluate() 直接计算四个核心指标。
    需要提供 LangChain 兼容的 LLM 和 Embeddings 对象。

    Attributes:
        _llm: LangChain 兼容的 LLM 对象（如 ChatOpenAI）
        _embeddings: LangChain 兼容的 Embeddings 对象（如 OpenAIEmbeddings）
    """

    # RAGAS 指标名 → 本系统指标名的映射
    _METRIC_NAME_MAP = {
        "faithfulness": "faithfulness",
        "context_precision": "context_precision",
        "context_recall": "context_recall",
        "answer_relevancy": "answer_relevancy",
    }

    def __init__(self, llm: Any, embeddings: Any):
        """初始化 RAGAS 评测器。

        Args:
            llm: LangChain 兼容的 LLM 对象。
                 示例：ChatOpenAI(model="gpt-4o-mini", temperature=0)
            embeddings: LangChain 兼容的 Embeddings 对象。
                       示例：OpenAIEmbeddings(model="text-embedding-3-small")
        """
        self._llm = llm
        self._embeddings = embeddings

    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Optional[float]]:
        """使用 RAGAS 执行单条评测。

        单条数据通过 datasets.Dataset.from_dict() 构建后传入 ragas.evaluate()。
        """
        metrics = self._normalize_metrics(metrics, ground_truth)
        result: Dict[str, Optional[float]] = {}

        # 检查 ragas 是否可用
        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import (
                Faithfulness,
                ContextPrecision,
                ContextRecall,
                AnswerRelevancy,
            )
            from datasets import Dataset
        except ImportError as e:
            logger.error(
                f"RAGAS 库未安装，无法使用方案A。"
                f"请执行: pip install ragas datasets langchain langchain-openai"
            )
            raise ImportError(
                "RAGAS 库未安装。请执行: pip install ragas datasets langchain langchain-openai\n"
                f"原始错误: {e}"
            ) from e

        # 构建 RAGAS 数据集（单条）
        data_dict: Dict[str, Any] = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        }

        if ground_truth:
            data_dict["ground_truth"] = [ground_truth]

        dataset = Dataset.from_dict(data_dict)

        # 选择要计算的指标
        ragas_metrics = []
        for m in metrics:
            if m == "faithfulness":
                ragas_metrics.append(Faithfulness())
            elif m == "context_precision":
                ragas_metrics.append(ContextPrecision())
            elif m == "context_recall":
                if ground_truth:
                    ragas_metrics.append(ContextRecall())
                else:
                    result["context_recall"] = None
            elif m == "answer_relevancy":
                ragas_metrics.append(AnswerRelevancy())

        if not ragas_metrics:
            return result

        # 执行 RAGAS 评测
        try:
            score = ragas_evaluate(
                dataset,
                metrics=ragas_metrics,
                llm=self._llm,
                embeddings=self._embeddings,
            )
        except Exception as e:
            logger.error(f"RAGAS 评测执行失败: {e}")
            raise

        # 将 ragas 结果转为标准格式
        score_dict = score.to_dict() if hasattr(score, "to_dict") else dict(score)
        
        for col_name, col_value in score_dict.items():
            metric_name = self._METRIC_NAME_MAP.get(col_name, col_name)
            if metric_name in metrics:
                # ragas 返回可能为 dict 或 list
                if isinstance(col_value, dict):
                    val = col_value.get("score", col_value)
                elif isinstance(col_value, list):
                    val = col_value[0] if col_value else None
                else:
                    val = col_value
                result[metric_name] = round(float(val), 4) if val is not None else None

        # 填充未请求的指标为 None
        for m in self.METRIC_NAMES:
            if m not in result:
                result[m] = None

        return result

    @staticmethod
    def evaluate_batch(
        questions: List[str],
        answers: List[str],
        contexts_list: List[List[str]],
        ground_truths: Optional[List[Optional[str]]] = None,
        metrics: Optional[List[str]] = None,
        llm: Any = None,
        embeddings: Any = None,
    ) -> Dict[str, Any]:
        """批量评测（RAGAS 原生支持批量，效率更高）。

        如果不需要逐条单独评测，批量模式更高效。

        Args:
            questions: 问题列表。
            answers: 答案列表。
            contexts_list: 上下文列表的列表。
            ground_truths: 标准答案列表（可选）。
            metrics: 需要计算的指标列表。
            llm: LangChain LLM 对象。
            embeddings: LangChain Embeddings 对象。

        Returns:
            包含 scores (逐条分数) 和 aggregate (聚合摘要) 的字典。
        """
        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import (
                Faithfulness,
                ContextPrecision,
                ContextRecall,
                AnswerRelevancy,
            )
            from datasets import Dataset
        except ImportError as e:
            raise ImportError(
                "RAGAS 库未安装。请执行: pip install ragas datasets langchain langchain-openai"
            ) from e

        data_dict: Dict[str, Any] = {
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
        }

        if ground_truths:
            # 过滤掉 None 值
            valid_gts = [gt if gt else "" for gt in ground_truths]
            data_dict["ground_truth"] = valid_gts

        dataset = Dataset.from_dict(data_dict)

        if metrics is None:
            metrics = list(BaseEvaluator.METRIC_NAMES)

        ragas_metrics = []
        has_ground_truth = bool(ground_truths and any(ground_truths))
        
        for m in metrics:
            if m == "faithfulness":
                ragas_metrics.append(Faithfulness())
            elif m == "context_precision":
                ragas_metrics.append(ContextPrecision())
            elif m == "context_recall":
                if has_ground_truth:
                    ragas_metrics.append(ContextRecall())
            elif m == "answer_relevancy":
                ragas_metrics.append(AnswerRelevancy())

        score = ragas_evaluate(
            dataset,
            metrics=ragas_metrics,
            llm=llm,
            embeddings=embeddings,
        )

        score_df = score.to_pandas()
        
        # 提取逐条分数
        per_item_scores = []
        for _, row in score_df.iterrows():
            item = {}
            for col in score_df.columns:
                if col in BaseEvaluator.METRIC_NAMES:
                    item[col] = round(float(row[col]), 4)
            per_item_scores.append(item)

        # 聚合
        aggregate = BaseEvaluator.aggregate(per_item_scores)

        return {
            "scores": per_item_scores,
            "aggregate": aggregate,
        }
