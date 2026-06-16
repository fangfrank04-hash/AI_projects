# -*- coding: utf-8 -*-
"""
LangFuse 集成模块

对应文章 §3 的全部内容，提供三个核心能力：
  1. LangFuseTracer — 自动记录每次 RAG 调用（Tracing）
  2. auto_add_to_dataset — 差评/问题自动加入评测用例集
  3. run_ragas_from_langfuse — 从 LangFuse 拉数据 → 评测 → 回写评分

用法:

    # ===== 1. 自动 Tracing =====
    from evaluation.langfuse_integration import LangfuseTracer

    tracer = LangfuseTracer(public_key="pk-xxx", secret_key="sk-xxx", host="https://xxx")

    # 装饰器方式
    @tracer.trace(name="rag-query")
    def my_rag(question):
        return {"answer": "...", "contexts": [...]}

    # 上下文管理器方式
    with tracer.span(name="retrieval", input_data={"query": q}) as span:
        contexts = retriever.search(q)
        span.end(output_data={"contexts": contexts})

    # ===== 2. 差评自动入 Dataset =====
    from evaluation.langfuse_integration import auto_add_to_dataset

    auto_add_to_dataset(
        tracer=tracer,
        question="什么是RAG？",
        answer="不知道",
        contexts=["RAG是..."],
        user_rating=2,
        dataset_name="rag-eval/pending-review",
    )

    # ===== 3. LangFuse → RAGAS 完整流程 =====
    from evaluation.langfuse_integration import run_ragas_from_langfuse

    result = run_ragas_from_langfuse(
        tracer=tracer,
        dataset_name="rag-eval/qa-dataset",
        run_name="eval-v1.2",
        rag_function=my_rag,
    )
"""

import json
import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# LangfuseTracer — 自动 Tracing
# ============================================================================


class LangfuseTracer:
    """LangFuse 追踪器，自动记录每次 RAG 调用的完整链路。

    对应文章 §3.2：三种接入方式中的"手动 Trace（完全控制）"。

    Attributes:
        _client: Langfuse 客户端实例
        _trace_enabled: 是否启用追踪（未配置时为 False）
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: bool = True,
    ):
        """初始化 LangFuse 追踪器。

        Args:
            public_key: LangFuse 公钥
            secret_key: LangFuse 私钥
            host: LangFuse 服务地址
            enabled: 是否启用追踪（关闭时不调用 LangFuse，方便开发调试）

        如果密钥未提供，追踪器在"静默模式"下运行，不报错也不记录。
        """
        self._enabled = enabled
        self._client = None

        if public_key and secret_key and host:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                if self._client.auth_check():
                    logger.info("LangFuse 追踪器初始化成功")
                else:
                    logger.warning("LangFuse 认证失败，追踪器将以静默模式运行")
                    self._client = None
            except ImportError:
                logger.warning("langfuse 库未安装，追踪器将以静默模式运行。安装: pip install langfuse")
                self._client = None
            except Exception as e:
                logger.warning(f"LangFuse 初始化失败: {e}，追踪器将以静默模式运行")
                self._client = None

    @property
    def is_ready(self) -> bool:
        return self._enabled and self._client is not None

    @property
    def client(self):
        return self._client

    # ------------------------------------------------------------------
    # 装饰器模式：自动包裹 RAG 函数
    # ------------------------------------------------------------------

    def trace(
        self,
        name: str = "rag-query",
        tags: Optional[List[str]] = None,
    ):
        """装饰器：自动为 RAG 函数记录 Trace。

        被装饰函数的返回值应包含 answer 和 contexts 字段。

        Example:
            tracer = LangfuseTracer(...)

            @tracer.trace(name="rag-search")
            def search(question):
                return {"answer": "...", "contexts": [...]}

            result = search("什么是RAG？")
            # Trace 已自动记录到 LangFuse
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.is_ready:
                    return func(*args, **kwargs)

                question = str(args[0]) if args else kwargs.get("question", "")
                trace = self._client.trace(
                    name=name,
                    input={"question": question},
                    tags=tags,
                )

                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.time() - start_time

                    if isinstance(result, dict):
                        trace.update(
                            output={
                                "answer": str(result.get("answer", ""))[:500],
                                "contexts_count": len(result.get("contexts", [])),
                            },
                            metadata={"elapsed_seconds": round(elapsed, 3)},
                        )

                    # 记录检索阶段 span
                    if isinstance(result, dict) and result.get("contexts"):
                        retrieval_span = trace.span(
                            name="retrieval",
                            input={"query": question},
                        )
                        retrieval_span.end(
                            output={
                                "chunks_count": len(result["contexts"]),
                                "chunks_preview": [
                                    c[:100] for c in result["contexts"][:3]
                                ],
                            }
                        )

                    # 记录生成阶段 generation
                    if isinstance(result, dict) and result.get("answer"):
                        trace.generation(
                            name="llm-generation",
                            input={
                                "question": question,
                                "contexts_count": len(result.get("contexts", [])),
                            },
                            output={"answer": str(result["answer"])[:500]},
                        )

                    # 将 trace_id 注入返回值
                    if isinstance(result, dict):
                        result["_langfuse_trace_id"] = trace.id

                    return result
                except Exception as e:
                    logger.error(f"RAG 调用失败: {e}")
                    trace.update(metadata={"error": str(e)})
                    raise

            return wrapper

        return decorator

    # ------------------------------------------------------------------
    # 上下文管理器模式：手动 Span
    # ------------------------------------------------------------------

    @contextmanager
    def span(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ):
        """上下文管理器：手动创建一个 Span。

        Example:
            with tracer.span(name="retrieval", input_data={"query": q}) as span:
                result = do_search(q)
                span.end(output_data={"results": result})
        """
        if not self.is_ready or not self._client:
            yield _NoOpSpan()
            return

        trace = None
        if trace_id:
            trace = self._client.get_trace(trace_id)

        if trace:
            span_obj = trace.span(name=name, input=input_data)
        else:
            # 独立 Span（无父 Trace）
            t = self._client.trace(name=f"{name}-standalone")
            span_obj = t.span(name=name, input=input_data)

        yield SpanWrapper(span_obj)


class SpanWrapper:
    """Span 包装器，简化 end() 调用。"""
    def __init__(self, span_obj):
        self._span = span_obj
        self.output_data = {}
        self.metadata = {}

    def end(self, output_data: Optional[Dict] = None, metadata: Optional[Dict] = None):
        kwargs = {}
        if output_data:
            kwargs["output"] = output_data
        if metadata:
            kwargs["metadata"] = metadata
        if kwargs:
            self._span.end(**kwargs)
        else:
            self._span.end()


class _NoOpSpan:
    """静默模式的空 Span。"""
    def end(self, **kwargs):
        pass


# ============================================================================
# auto_add_to_dataset — 差评自动入 Dataset
# ============================================================================


def auto_add_to_dataset(
    tracer: LangfuseTracer,
    question: str,
    answer: str,
    contexts: List[str],
    dataset_name: str = "rag-eval/pending-review",
    user_rating: Optional[int] = None,
    user_feedback: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """差评/问题自动加入 LangFuse 评测用例集。

    对应文章 §3.3 的代码示例。

    当用户给出差评（rating ≤ 2）或人工发现问题时，调用此函数
    将当前问答自动加入 LangFuse Dataset，供后续评测使用。

    Args:
        tracer: LangFuseTracer 实例
        question: 用户问题
        answer: 系统生成的答案
        contexts: 检索到的上下文
        dataset_name: 目标 Dataset 名称（支持 / 创建文件夹层级）
        user_rating: 用户评分（1-5）
        user_feedback: 用户反馈文本
        trace_id: 关联的 Trace ID
        metadata: 附加元数据

    Returns:
        True 如果成功，False 如果失败

    Example:
        # 在用户反馈回调中使用
        def on_feedback(question, answer, rating, feedback):
            if rating <= 2:  # 差评
                auto_add_to_dataset(
                    tracer=tracer,
                    question=question,
                    answer=answer,
                    contexts=get_contexts(question),
                    user_rating=rating,
                    user_feedback=feedback,
                    dataset_name="rag-eval/pending-review",
                )
    """
    if not tracer.is_ready:
        logger.debug("LangFuse 未配置，跳过自动入 Dataset")
        return False

    client = tracer.client
    if not client:
        return False

    try:
        meta = {
            "source": "user-feedback-auto",
            "status": "pending_review",
        }
        if user_rating is not None:
            meta["user_rating"] = user_rating
        if user_feedback:
            meta["user_feedback"] = user_feedback
        if trace_id:
            meta["source_trace_id"] = trace_id
        if metadata:
            meta.update(metadata)

        client.create_dataset_item(
            dataset_name=dataset_name,
            input={
                "question": question,
                "contexts": contexts,
            },
            expected_output={
                "answer": answer,
            },
            metadata=meta,
        )

        logger.info(f"用例已自动加入 Dataset: {dataset_name}")
        return True
    except Exception as e:
        logger.error(f"自动加入 Dataset 失败: {e}")
        return False


# ============================================================================
# run_ragas_from_langfuse — LangFuse → RAGAS 完整流程
# ============================================================================


def run_ragas_from_langfuse(
    tracer: LangfuseTracer,
    dataset_name: str,
    run_name: Optional[str] = None,
    rag_function: Optional[Callable[[str], Dict[str, Any]]] = None,
    metrics: Optional[List[str]] = None,
    method: str = "llm_judge",
    ground_truths: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """从 LangFuse Dataset 读取用例 → 执行评测 → 回写评分。

    对应文章 §3.5 的 run_ragas_from_langfuse() 函数。

    完整流程：
      1. client.get_dataset(dataset_name) 拉取用例
      2. 提取 question / answer / contexts / ground_truth
      3. 若无 answer/contexts，调用 rag_function 实时生成
      4. 调用 Evaluator 计算指标
      5. 评分回写 LangFuse (create_score)

    Args:
        tracer: LangfuseTracer 实例
        dataset_name: LangFuse Dataset 名称（如 "rag-eval/qa-dataset"）
        run_name: 本次 Run 的名称（如 "eval-v1.2"）
        rag_function: RAG 查询函数 fn(question) -> {"answer", "contexts"}
        metrics: 需要计算的指标列表，None 表示全部
        method: 评测方法 "llm_judge" 或 "ragas"
        ground_truths: {question: ground_truth} 映射（可选）

    Returns:
        {
            "run_name": "eval-v1.2",
            "total": 10,
            "scores": [{"question": ..., "faithfulness": 0.85, ...}, ...],
            "aggregate": {"avg_faithfulness": 0.81, ...},
        }
    """
    if not tracer.is_ready:
        return {
            "error": "LangFuse 未配置，无法执行评测",
            "total": 0,
            "scores": [],
            "aggregate": {},
        }

    client = tracer.client
    if not client:
        return {"error": "LangFuse 客户端不可用", "total": 0, "scores": [], "aggregate": {}}

    if run_name is None:
        run_name = f"ragas-eval-{time.strftime('%Y%m%d-%H%M%S')}"

    # 1. 获取数据集
    try:
        dataset = client.get_dataset(dataset_name)
    except Exception as e:
        logger.error(f"获取 LangFuse Dataset 失败: {e}")
        return {"error": str(e), "total": 0, "scores": [], "aggregate": {}}

    # 2. 提取用例数据
    questions, answers, contexts_list, ground_truth_list = [], [], [], []
    items = list(dataset.items)

    for item in items:
        inp = item.input or {}
        exp = item.expected_output or {}

        q = inp.get("question", "")
        questions.append(q)

        ctx = inp.get("contexts", [])
        contexts_list.append(ctx if isinstance(ctx, list) else [str(ctx)])

        ans = exp.get("answer", "")
        answers.append(ans)

        gt = None
        if ground_truths and q in ground_truths:
            gt = ground_truths[q]
        elif exp.get("ground_truth"):
            gt = exp["ground_truth"]
        ground_truth_list.append(gt)

    # 3. 若无 answer/contexts，实时调用 RAG 系统
    if rag_function and (not any(answers) or not any(contexts_list)):
        logger.info("数据不完整，实时调用 RAG 系统生成 answer/contexts...")
        for i, q in enumerate(questions):
            try:
                result = rag_function(q)
                if not answers[i]:
                    answers[i] = result.get("answer", "")
                if not contexts_list[i]:
                    contexts_list[i] = result.get("contexts", [])
            except Exception as e:
                logger.error(f"调用 RAG 系统失败 (q={q[:50]}...): {e}")

    # 4. 执行评测
    from evaluation.base import BaseEvaluator
    from evaluation.auto_hook import auto_evaluate

    all_scores = []
    for i in range(len(questions)):
        try:
            score = auto_evaluate(
                question=questions[i],
                answer=answers[i] or "",
                contexts=contexts_list[i] or [],
                ground_truth=ground_truth_list[i],
                metrics=metrics,
            )
            all_scores.append({
                "question": questions[i],
                "answer": (answers[i] or "")[:200],
                **score,
            })
        except Exception as e:
            logger.error(f"评测失败 (q={questions[i][:50]}...): {e}")
            all_scores.append({
                "question": questions[i],
                "error": str(e),
            })

    # 5. 评分回写 LangFuse
    aggregate = BaseEvaluator.aggregate(
        [{k: v for k, v in s.items() if k not in ("question", "answer", "error")} for s in all_scores]
    )

    try:
        for idx, item in enumerate(items):
            run_item = item.link(
                trace_or_observation=None,
                run_name=run_name,
            )
            scores_dict = all_scores[idx]
            for metric_name in ["faithfulness", "context_precision", "context_recall", "answer_relevancy"]:
                val = scores_dict.get(metric_name)
                if val is not None:
                    client.create_score(
                        name=f"ragas_{metric_name}",
                        value=float(val),
                        dataset_run_item_id=run_item.id,
                    )
        logger.info(f"评分已回写 LangFuse: {run_name} ({len(items)} 条)")
    except Exception as e:
        logger.error(f"评分回写 LangFuse 失败: {e}")

    return {
        "run_name": run_name,
        "total": len(all_scores),
        "scores": all_scores,
        "aggregate": aggregate,
    }
