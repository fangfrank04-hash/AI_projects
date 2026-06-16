# -*- coding: utf-8 -*-
"""
评测器抽象基类

方案A(RagasEvaluator)和方案B(LLMJudgeEvaluator)均继承此类，遵循统一接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseEvaluator(ABC):
    """RAG 评测器抽象基类。

    所有评测方案必须实现 evaluate() 方法。
    aggregate() 提供默认实现（均值聚合），子类可按需覆盖。
    """

    # 支持的指标名称列表
    METRIC_NAMES: List[str] = [
        "faithfulness",
        "context_precision",
        "context_recall",
        "answer_relevancy",
    ]

    # 不需要 ground_truth 的指标
    METRICS_WITHOUT_GROUND_TRUTH: List[str] = [
        "faithfulness",
        "context_precision",
        "answer_relevancy",
    ]

    # 需要 ground_truth 的指标
    METRICS_REQUIRING_GROUND_TRUTH: List[str] = [
        "context_recall",
    ]

    @abstractmethod
    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Optional[float]]:
        """执行单条评测。

        Args:
            question: 用户原始问题。
            answer: RAG 系统生成的答案。
            contexts: 检索到的上下文文档列表（每个元素是文档文本）。
            ground_truth: 人工标注正确答案（可选，Context Recall 需要）。
            metrics: 需要计算的指标列表，None 表示计算所有可用指标。

        Returns:
            指标名 → 分数（0.0~1.0）的字典。无法计算的指标值为 None。
            例如: {"faithfulness": 0.85, "context_precision": 0.60, "context_recall": None, "answer_relevancy": 0.92}

        Raises:
            ValueError: 如果 metrics 中包含不支持的指标名。
        """
        ...

    @staticmethod
    def aggregate(results: List[Dict[str, Optional[float]]]) -> Dict[str, Any]:
        """聚合多条评测结果，计算各指标的均值。

        None 值会被跳过（不计入均值）。

        Args:
            results: evaluate() 返回值的列表。

        Returns:
            聚合结果字典，包含 avg_<metric>、total、valid_count。
            例如: {
                "total": 10,
                "valid_count": {"faithfulness": 10, "context_recall": 8},
                "avg_faithfulness": 0.81,
                "avg_context_precision": 0.72,
                ...
            }
        """
        if not results:
            return {"total": 0, "valid_count": {}, "error": "empty results"}

        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}

        for r in results:
            for key, val in r.items():
                if val is not None and isinstance(val, (int, float)):
                    sums[key] = sums.get(key, 0.0) + float(val)
                    counts[key] = counts.get(key, 0) + 1

        summary: Dict[str, Any] = {
            "total": len(results),
            "valid_count": dict(counts),
        }

        for key in sums:
            if counts[key] > 0:
                summary[f"avg_{key}"] = round(sums[key] / counts[key], 4)

        return summary

    @staticmethod
    def _normalize_metrics(
        requested: Optional[List[str]],
        ground_truth: Optional[str],
    ) -> List[str]:
        """根据 ground_truth 是否提供，规范化指标列表。

        Args:
            requested: 用户请求的指标列表，None 表示全部。
            ground_truth: 标准答案，为 None 时自动排除需要它的指标。

        Returns:
            规范化的指标列表。
        """
        if requested is None:
            requested = list(BaseEvaluator.METRIC_NAMES)

        # 验证指标名
        for m in requested:
            if m not in BaseEvaluator.METRIC_NAMES:
                raise ValueError(
                    f"不支持的指标: '{m}'。支持的指标: {BaseEvaluator.METRIC_NAMES}"
                )

        # 自动排除需要 ground_truth 但未提供的指标
        if ground_truth is None:
            requested = [
                m for m in requested
                if m not in BaseEvaluator.METRICS_REQUIRING_GROUND_TRUTH
            ]

        return requested
