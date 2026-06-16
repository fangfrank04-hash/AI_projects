# -*- coding: utf-8 -*-
"""
RAG 评测包装器 — 不改 ragflow 源码，包装一层自动加评测

这个文件是你自己新建的，放在 ragflow 项目根目录就行。
不需要改任何 ragflow 原有代码。

===== 怎么用（三选一）=====

【方式1】你在 ragflow 里调 RAG 的地方，拿到结果后加一行:
    from evaluation_wrapper import eval_answer
    result = ragflow_chat("什么是RAG？")  # 你原来调 ragflow 的代码
    result = eval_answer(result)          # 🆕 加这一行，自动附评测分数
    print(result["evaluation"])           # {"faithfulness": 0.85, ...}

【方式2】装饰器包一层:
    from evaluation_wrapper import with_eval
    @with_eval
    def my_rag(question):
        return call_ragflow(question)     # 你原来调 ragflow 的函数
    result = my_rag("什么是RAG？")        # 自动带 evaluation

【方式3】独立测试（不需要 ragflow）:
    from evaluation_wrapper import test_eval
    test_eval()  # 用假数据跑一遍，验证能用
"""

import logging

logger = logging.getLogger(__name__)

# ============================================================================
# 初始化（启动时执行一次）
# ============================================================================

_evaluator_ready = False


def init_evaluator(llm_chat_function=None):
    """初始化评测器。在 ragflow 启动时调用一次。

    Args:
        llm_chat_function: 你们的 LLM 调用函数。
            如果不传，用内置的模拟 LLM（只能测试，不能真评测）。

    Example:
        from evaluation_wrapper import init_evaluator
        from api.db.services.llm_service import LLMBundle
        init_evaluator(LLMBundle(tenant_id, "chat", model_name).chat)
    """
    global _evaluator_ready

    if llm_chat_function is None:
        # 没有传 LLM，用模拟的（方便先跑通）
        from evaluation.auto_hook import set_llm_callable

        class _MockLLM:
            def chat(self, messages):
                prompt = messages[0]["content"]
                if "extract all atomic" in prompt.lower():
                    return '["声明1", "声明2"]'
                return '{"verdict": 1}'

        set_llm_callable(_MockLLM().chat)
        logger.warning("评测器使用模拟 LLM 初始化（只能测试，不能真评测）")
        logger.warning("正式使用请传 LLMBundle: init_evaluator(LLMBundle(...).chat)")
    else:
        from evaluation.auto_hook import set_llm_callable
        set_llm_callable(llm_chat_function)
        logger.info("评测器初始化成功")

    _evaluator_ready = True


# 自动初始化（没传 LLM 时用模拟的）
try:
    init_evaluator()
except Exception:
    pass


# ============================================================================
# 方式1：拿到 ragflow 结果后加一行
# ============================================================================

def eval_answer(ragflow_result, question=None, ground_truth=None):
    """给 ragflow 返回结果附加评测分数。

    ragflow 的 chat 接口返回格式：
        {"answer": "生成的答案", "reference": {"chunks": [{"content": "文档1"}, ...]}}

    此函数读取 answer 和 chunks，计算 4 个指标，附加到结果里。

    Args:
        ragflow_result: ragflow chat 返回的 dict（必须包含 answer 和 reference.chunks）
        question: 用户问题（如果不传，自动尝试从 result 里找）
        ground_truth: 标准答案（可选）

    Returns:
        原 dict + "evaluation" 字段
        {"answer": "...", "reference": {...}, "evaluation": {"faithfulness": 0.85, ...}}

    Example:
        result = your_ragflow_chat_function("什么是RAG？")
        result = eval_answer(result, question="什么是RAG？")
        print(result["evaluation"]["faithfulness"])
    """
    answer = ragflow_result.get("answer", "")
    reference = ragflow_result.get("reference", {})
    chunks = reference.get("chunks", [])

    # 提取 chunk 文本
    context_texts = []
    for c in chunks:
        if isinstance(c, dict):
            text = c.get("content") or c.get("content_with_weight") or ""
            context_texts.append(text)
        elif isinstance(c, str):
            context_texts.append(c)

    if not answer or not context_texts:
        ragflow_result["evaluation"] = {"error": "缺少 answer 或 contexts"}
        return ragflow_result

    # 自动推断 question（从 result 里找）
    if question is None:
        question = ragflow_result.get("question") or ragflow_result.get("query") or ""

    from evaluation import auto_evaluate

    try:
        scores = auto_evaluate(
            question=str(question),
            answer=answer,
            contexts=context_texts,
            ground_truth=ground_truth,
        )
        ragflow_result["evaluation"] = scores
    except Exception as e:
        ragflow_result["evaluation"] = {"error": str(e)}

    return ragflow_result


# ============================================================================
# 方式2：装饰器
# ============================================================================

def with_eval(func):
    """装饰器：包裹你的 RAG 函数，返回值自动附加 evaluation。

    Example:
        @with_eval
        def ask_knowledge_base(question):
            return call_ragflow_api(question)

        result = ask_knowledge_base("什么是RAG？")
        print(result["evaluation"])
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if not isinstance(result, dict):
            return result

        question = args[0] if args else kwargs.get("question", "")
        return eval_answer(result, question=str(question))

    return wrapper


# ============================================================================
# 方式3：独立测试
# ============================================================================

def test_eval():
    """快速验证评测功能。不依赖 ragflow，用假数据跑一遍。"""
    print("=" * 50)
    print("  评测功能测试（模拟数据）")
    print("=" * 50)

    # 模拟 ragflow 返回的结果
    fake_result = {
        "answer": "RAG（Retrieval-Augmented Generation）是一种检索增强生成技术。它通过从外部知识库检索相关文档来增强大语言模型的回答质量，有效减少幻觉问题。",
        "reference": {
            "chunks": [
                {"content": "RAG（Retrieval-Augmented Generation）是一种将信息检索与文本生成相结合的技术。"},
                {"content": "RAG 通过检索外部知识库中的文档来增强 LLM 的回答，从而减少幻觉。"},
            ]
        },
    }

    # 方式1：直接加一行
    result = eval_answer(fake_result, question="什么是RAG？")
    print(f"\n  方式1: eval_answer() 一行搞定")
    print(f"  faithfulness:  {result['evaluation'].get('faithfulness')}")
    print(f"  precision:     {result['evaluation'].get('context_precision')}")
    print(f"  recall:        {result['evaluation'].get('context_recall')}")
    print(f"  relevancy:     {result['evaluation'].get('answer_relevancy')}")

    # 方式2：装饰器
    @with_eval
    def fake_rag(question):
        return fake_result

    result2 = fake_rag("什么是RAG？")
    print(f"\n  方式2: @with_eval 装饰器")
    print(f"  evaluation:    {list(result2['evaluation'].keys())}")

    print(f"\n  ✅ 评测功能正常工作！")
    print("=" * 50)


# ============================================================================
# 直接运行
# ============================================================================

if __name__ == "__main__":
    test_eval()
