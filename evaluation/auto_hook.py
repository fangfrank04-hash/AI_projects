# -*- coding: utf-8 -*-
"""
自动评测钩子（Auto Evaluation Hook）

在 RAG 检索完成后自动调用，计算四个评测指标。
一行代码插入，无需预先建数据集、无需手动触发。

用法示例:

    # === 最简用法（方案B，零依赖）===
    from evaluation.auto_hook import auto_evaluate

    # RAG 检索...
    answer, contexts = rag_pipeline.query("什么是RAG？")

    # 一行自动评测
    scores = auto_evaluate(
        question="什么是RAG？",
        answer=answer,
        contexts=contexts,
        ground_truth="RAG是检索增强生成技术...",  # 可选
    )
    print(scores)
    # => {"faithfulness": 0.85, "context_precision": 0.60, "context_recall": 0.75, "answer_relevancy": 0.90}

    # === 集成到 RAG pipeline（装饰器方式）===
    from evaluation.auto_hook import with_evaluation

    @with_evaluation(method="llm_judge")
    def my_rag_query(question):
        # 你的 RAG 逻辑
        return {"answer": "...", "contexts": [...]}
        # 返回结果里会自动附加 evaluation 字段

    result = my_rag_query("什么是RAG？")
    print(result["evaluation"]["faithfulness"])  # 0.85

    # === 方案A（需要 ragas 库 + OpenAI key）===
    from evaluation.auto_hook import auto_evaluate_ragas

    scores = auto_evaluate_ragas(
        question="什么是RAG？",
        answer=answer,
        contexts=contexts,
        ground_truth="RAG是...",
        llm=my_langchain_llm,
        embeddings=my_langchain_embeddings,
    )
"""

import json
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from evaluation.base import BaseEvaluator
from evaluation.llm_judge_evaluator import LLMJudgeEvaluator

logger = logging.getLogger(__name__)

# ============================================================================
# 全局评测器实例（单例，复用 LLMBundle 避免重复初始化）
# ============================================================================

_default_evaluator: Optional[LLMJudgeEvaluator] = None


def set_llm_callable(fn: Callable[[List[Dict[str, str]]], str]):
    """设置全局 LLM 调用函数（方案B 使用）。

    在应用启动时调用一次，后续所有 auto_evaluate() 都会复用这个 LLM。

    Args:
        fn: LLM 调用函数，签名为 fn(messages: list[dict]) -> str。
            如果使用 ragflow，传入 LLMBundle 的 chat 方法即可。

    Example:
        from api.db.services.llm_service import LLMBundle
        bundle = LLMBundle(tenant_id, "chat", model_name)
        set_llm_callable(bundle.chat)
    """
    global _default_evaluator
    _default_evaluator = LLMJudgeEvaluator(llm_callable=fn)
    logger.info("自动评测钩子已初始化（方案B: LLM-as-Judge）")


# ============================================================================
# 核心函数：auto_evaluate（方案B，推荐）
# ============================================================================

def auto_evaluate(
    question: str,
    answer: str,
    contexts: List[str],
    ground_truth: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    store_result: bool = False,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[float]]:
    """RAG 检索后自动评测（方案B: LLM-as-Judge）。

    这是一个纯 Python 函数，插在 RAG pipeline 最后一行即可使用。
    无需预先建数据集，无需 HTTP 请求，无需手动触发。

    Args:
        question: 用户原始问题。
        answer: RAG 系统生成的答案。
        contexts: 检索到的上下文文档列表（每个元素是文档文本）。
        ground_truth: 人工标注正确答案（可选，提供后会自动计算 context_recall）。
        metrics: 需要计算的指标列表，None 表示自动判断（有 ground_truth 则全算，无则算3个）。
        store_result: 是否将结果写入日志文件（默认 False，只返回不落盘）。
        extra_meta: 额外元数据（写入日志时附加，如 knowledge_base_id, dialog_id 等）。

    Returns:
        指标名 → 分数 (0.0~1.0) 的字典。无法计算的指标值为 None。
        例如: {"faithfulness": 0.85, "context_precision": 0.60, "context_recall": 0.75, "answer_relevancy": 0.90}

    Raises:
        RuntimeError: 如果未调用 set_llm_callable() 初始化。

    Example:
        # 应用启动时初始化一次
        set_llm_callable(my_llm_bundle.chat)

        # 每次 RAG 检索后调用
        answer, contexts = rag_search("什么是RAG？")
        scores = auto_evaluate(
            question="什么是RAG？",
            answer=answer,
            contexts=contexts,
            ground_truth="RAG是检索增强生成技术。",
        )
        logger.info(f"评测分数: faithfulness={scores['faithfulness']:.2f}")
    """
    global _default_evaluator

    if _default_evaluator is None:
        raise RuntimeError(
            "自动评测钩子未初始化。请在应用启动时调用 set_llm_callable(fn)。\n"
            "示例：set_llm_callable(LLMBundle(tenant_id, 'chat', model_name).chat)"
        )

    start_time = time.time()
    scores = _default_evaluator.evaluate(
        question=question,
        answer=answer,
        contexts=contexts,
        ground_truth=ground_truth,
        metrics=metrics,
    )
    elapsed = time.time() - start_time

    if store_result:
        _log_evaluation(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
            scores=scores,
            elapsed=elapsed,
            extra_meta=extra_meta,
        )

    return scores


# ============================================================================
# 装饰器：with_evaluation
# ============================================================================

def with_evaluation(
    method: str = "llm_judge",
    metrics: Optional[List[str]] = None,
    question_key: str = "question",
    ground_truth_key: Optional[str] = "ground_truth",
    store_result: bool = False,
):
    """装饰器：自动为 RAG 查询函数附加评测结果。

    被装饰的函数需要返回一个 dict，包含 'answer' 和 'contexts' 字段。
    装饰后，返回的 dict 会自动增加 'evaluation' 字段。

    Args:
        method: 评测方法，"llm_judge"（方案B）或 "ragas"（方案A）。
        metrics: 需要计算的指标列表。
        question_key: 函数参数中问题对应的 key 名称。
        ground_truth_key: 函数参数中标准答案对应的 key 名称（可选）。
        store_result: 是否落盘存储结果。

    Example:
        @with_evaluation(method="llm_judge")
        def ask(question, ground_truth=None):
            answer, contexts = my_rag(question)
            return {"answer": answer, "contexts": contexts}

        result = ask("什么是RAG？", ground_truth="RAG是...")
        print(result["evaluation"])  # 自动附加的评测结果
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 调用原始 RAG 函数
            result = func(*args, **kwargs)

            if not isinstance(result, dict):
                logger.warning("with_evaluation 要求被装饰函数返回 dict，跳过评测")
                return result

            question = result.get(question_key, kwargs.get(question_key, ""))
            ground_truth = None
            if ground_truth_key:
                ground_truth = result.get(
                    ground_truth_key, kwargs.get(ground_truth_key)
                )

            try:
                if method == "llm_judge":
                    scores = auto_evaluate(
                        question=str(question),
                        answer=str(result.get("answer", "")),
                        contexts=list(result.get("contexts", [])),
                        ground_truth=ground_truth,
                        metrics=metrics,
                        store_result=store_result,
                    )
                else:
                    logger.warning(f"未知评测方法: {method}，跳过")
                    scores = None

                result["evaluation"] = scores
            except Exception as e:
                logger.error(f"自动评测失败: {e}")
                result["evaluation"] = None
                result["evaluation_error"] = str(e)

            return result

        return wrapper

    return decorator


# ============================================================================
# 方案A：auto_evaluate_ragas
# ============================================================================

def auto_evaluate_ragas(
    question: str,
    answer: str,
    contexts: List[str],
    ground_truth: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    llm: Any = None,
    embeddings: Any = None,
) -> Dict[str, Optional[float]]:
    """RAG 检索后自动评测（方案A: RAGAS 库）。

    需要预装 ragas 库和 LangChain 兼容的 LLM/Embeddings 对象。

    Args:
        question: 用户原始问题。
        answer: RAG 系统生成的答案。
        contexts: 检索到的上下文文档列表。
        ground_truth: 标准答案（可选）。
        metrics: 需要计算的指标列表。
        llm: LangChain 兼容的 LLM 对象（如 ChatOpenAI）。
        embeddings: LangChain 兼容的 Embeddings 对象。

    Returns:
        评测分数字典。

    Example:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from evaluation.auto_hook import auto_evaluate_ragas

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

        scores = auto_evaluate_ragas(
            question="什么是RAG？",
            answer=answer,
            contexts=contexts,
            ground_truth="RAG是...",
            llm=llm,
            embeddings=embeddings,
        )
    """
    try:
        from evaluation.ragas_evaluator import RagasEvaluator
    except ImportError as e:
        raise ImportError(
            "方案A 需要 ragas 库。请安装: pip install ragas datasets langchain langchain-openai"
        ) from e

    evaluator = RagasEvaluator(llm=llm, embeddings=embeddings)

    return evaluator.evaluate(
        question=question,
        answer=answer,
        contexts=contexts,
        ground_truth=ground_truth,
        metrics=metrics,
    )


# ============================================================================
# 结果落盘（可选）
# ============================================================================

_EVAL_LOG_FILE: Optional[str] = None


def set_eval_log_path(path: str):
    """设置评测结果日志文件路径。

    Args:
        path: JSONL 日志文件路径。如 "/var/log/rag_eval.jsonl"
    """
    global _EVAL_LOG_FILE
    _EVAL_LOG_FILE = path


def _log_evaluation(
    question: str,
    answer: str,
    contexts: List[str],
    ground_truth: Optional[str],
    scores: Dict[str, Optional[float]],
    elapsed: float,
    extra_meta: Optional[Dict[str, Any]] = None,
):
    """将评测结果写入 JSONL 日志文件。"""
    global _EVAL_LOG_FILE

    if not _EVAL_LOG_FILE:
        return

    log_entry = {
        "timestamp": time.time(),
        "question": question,
        "answer": answer[:500],  # 截断长答案
        "contexts_count": len(contexts),
        "has_ground_truth": ground_truth is not None,
        "scores": scores,
        "elapsed_seconds": round(elapsed, 2),
    }

    if extra_meta:
        log_entry["meta"] = extra_meta

    try:
        import os
        os.makedirs(os.path.dirname(_EVAL_LOG_FILE), exist_ok=True)
        with open(_EVAL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"写入评测日志失败: {e}")
