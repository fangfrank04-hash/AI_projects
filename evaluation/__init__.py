# -*- coding: utf-8 -*-
"""
RAG 评测系统 - evaluation 包

四种使用方式:

  【方式1：自动评测钩子 — RAG 后一行代码自动算指标】
  >>> from evaluation import set_llm_callable, auto_evaluate
  >>> set_llm_callable(my_llm.chat)
  >>> scores = auto_evaluate(question, answer, contexts)

  【方式2：装饰器 — 自动为 RAG 函数附加评测】
  >>> from evaluation import with_evaluation
  >>> @with_evaluation()
  ... def my_rag(q): return {"answer": "...", "contexts": [...]}
  >>> result = my_rag("问题")
  >>> print(result["evaluation"])

  【方式3：手动调用评测器】
  >>> from evaluation import LLMJudgeEvaluator
  >>> evaluator = LLMJudgeEvaluator(llm_callable=my_llm)
  >>> result = evaluator.evaluate(question, answer, contexts)

  【方式4：独立评测脚本（定时/手动跑）】
  >>> python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --output report.json

  【LangFuse 集成】
  >>> from evaluation import LangfuseTracer, run_ragas_from_langfuse
  >>> tracer = LangfuseTracer(public_key="pk-xxx", ...)
  >>> result = run_ragas_from_langfuse(tracer, dataset_name="qa-dataset")
"""

from evaluation.base import BaseEvaluator
from evaluation.ragas_evaluator import RagasEvaluator
from evaluation.llm_judge_evaluator import LLMJudgeEvaluator
from evaluation.auto_hook import (
    auto_evaluate,
    auto_evaluate_ragas,
    set_llm_callable,
    set_eval_log_path,
    with_evaluation,
)
from evaluation.langfuse_integration import (
    LangfuseTracer,
    auto_add_to_dataset,
    run_ragas_from_langfuse,
)

__all__ = [
    # 基类
    "BaseEvaluator",
    # 方案A
    "RagasEvaluator",
    # 方案B
    "LLMJudgeEvaluator",
    # 自动评测钩子
    "auto_evaluate",
    "auto_evaluate_ragas",
    "set_llm_callable",
    "set_eval_log_path",
    "with_evaluation",
    # LangFuse 集成
    "LangfuseTracer",
    "auto_add_to_dataset",
    "run_ragas_from_langfuse",
]
