# -*- coding: utf-8 -*-
"""
方案B：手工 LLM-as-Judge 评测器

不依赖 RAGAS 库，使用 LLM 直接实现四个 RAG 评测指标：
  - Faithfulness（忠实度）：两阶段 LLM 调用
  - Context Precision（上下文精确度）：逐文档判定 + 位置加权
  - Context Recall（上下文召回率）：ground_truth 拆句 + 归因
  - Answer Relevancy（答案相关性）：反向生成问题 + 语义相似度

用法:
    evaluator = LLMJudgeEvaluator(llm_callable=my_llm_function)
    result = evaluator.evaluate(question, answer, contexts, ground_truth)
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from evaluation.base import BaseEvaluator
from evaluation.prompts import (
    ANSWER_RELEVANCY_REVERSE_QUESTION_PROMPT,
    CONTEXT_PRECISION_JUDGE_PROMPT,
    CONTEXT_RECALL_ATTRIBUTION_PROMPT,
    CONTEXT_RECALL_SENTENCE_SPLIT_PROMPT,
    FAITHFULNESS_STATEMENT_EXTRACTION_PROMPT,
    FAITHFULNESS_VERDICT_PROMPT,
)

logger = logging.getLogger(__name__)


class LLMJudgeEvaluator(BaseEvaluator):
    """手工 LLM-as-Judge 评测器。

    通过精心设计的 prompt 模板，使用 LLM 计算四个 RAG 评测指标。
    完全自主可控，不依赖 ragas 等第三方评测库。

    Attributes:
        _llm_call: LLM 调用函数，签名为 async def fn(messages: list) -> str
        _reverse_question_count: 反向生成问题的数量（默认 3）
    """

    def __init__(
        self,
        llm_callable: Callable[[List[Dict[str, str]]], str],
        reverse_question_count: int = 3,
    ):
        """初始化评测器。

        Args:
            llm_callable: LLM 调用函数。
                          签名为 fn(messages: list[dict]) -> str
                          messages 格式：[{"role": "user", "content": "..."}]
                          返回 LLM 生成的文本。
            reverse_question_count: Answer Relevancy 中反向生成的问题数。
        """
        self._llm_call = llm_callable
        self._reverse_question_count = reverse_question_count

    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Optional[float]]:
        """执行单条评测。

        指标计算互不影响——某个指标失败不会阻塞其他指标。
        """
        metrics = self._normalize_metrics(metrics, ground_truth)
        result: Dict[str, Optional[float]] = {}

        for metric_name in self.METRIC_NAMES:
            if metric_name not in metrics:
                result[metric_name] = None
                continue

            try:
                if metric_name == "faithfulness":
                    result[metric_name] = self._faithfulness(question, answer, contexts)
                elif metric_name == "context_precision":
                    result[metric_name] = self._context_precision(question, contexts)
                elif metric_name == "context_recall":
                    result[metric_name] = self._context_recall(ground_truth, contexts)  # type: ignore
                elif metric_name == "answer_relevancy":
                    result[metric_name] = self._answer_relevancy(question, answer)
            except Exception as e:
                logger.error(f"计算指标 '{metric_name}' 失败: {e}")
                result[metric_name] = None

        return result

    # ========================================================================
    # 1. Faithfulness（忠实度）
    # ========================================================================

    def _faithfulness(self, question: str, answer: str, contexts: List[str]) -> float:
        """两阶段 LLM 调用：
        ① 从 answer 提取原子声明
        ② 逐条验证每个声明是否被 contexts 支撑
        """
        # 阶段 1：提取声明
        claims = self._extract_claims(answer)
        if not claims:
            return 0.0  # 无法提取声明，视为不忠实

        # 阶段 2：逐条验证
        context_text = "\n---\n".join(
            f"[Doc {i + 1}] {ctx}" for i, ctx in enumerate(contexts)
        )
        verified_count = 0

        for claim in claims:
            try:
                prompt = FAITHFULNESS_VERDICT_PROMPT.format(
                    claim=claim, contexts=context_text
                )
                response = self._call_llm(prompt)
                verdict = self._parse_json_field(response, "verdict", default=0)
                verified_count += int(verdict)
            except Exception as e:
                logger.warning(f"验证声明失败: {claim[:50]}... -> {e}")

        return round(verified_count / len(claims), 4)

    def _extract_claims(self, answer: str) -> List[str]:
        """从答案中提取原子声明列表。"""
        prompt = FAITHFULNESS_STATEMENT_EXTRACTION_PROMPT.format(answer=answer)
        response = self._call_llm(prompt)
        claims = self._parse_json_array(response)
        return [c.strip() for c in claims if c.strip()]

    # ========================================================================
    # 2. Context Precision（上下文精确度）
    # ========================================================================

    def _context_precision(self, question: str, contexts: List[str]) -> float:
        """逐文档判定相关性 + 位置加权平均。

        公式：Context Precision = Σ(Precision@k × is_relevant@k) / 相关文档总数
        """
        if not contexts:
            return 0.0

        verdicts = []
        for doc in contexts:
            try:
                prompt = CONTEXT_PRECISION_JUDGE_PROMPT.format(
                    question=question, document=doc
                )
                response = self._call_llm(prompt)
                relevant = int(self._parse_json_field(response, "relevant", default=0))
                verdicts.append(relevant)
            except Exception as e:
                logger.warning(f"判定文档相关性失败: {e}")
                verdicts.append(0)

        total_relevant = sum(verdicts)
        if total_relevant == 0:
            return 0.0

        # 位置加权
        weighted_sum = 0.0
        for k in range(1, len(verdicts) + 1):
            precision_at_k = sum(verdicts[:k]) / k
            weighted_sum += precision_at_k * verdicts[k - 1]

        return round(weighted_sum / total_relevant, 4)

    # ========================================================================
    # 3. Context Recall（上下文召回率）
    # ========================================================================

    def _context_recall(
        self, ground_truth: Optional[str], contexts: List[str]
    ) -> Optional[float]:
        """ground_truth 拆句 + 逐句归因验证。

        需要 ground_truth，否则返回 None。
        """
        if not ground_truth or not ground_truth.strip():
            return None
        if not contexts:
            return 0.0

        # 拆句
        sentences = self._split_ground_truth(ground_truth)
        if not sentences:
            return None

        # 逐句验证
        context_text = "\n---\n".join(
            f"[Doc {i + 1}] {ctx}" for i, ctx in enumerate(contexts)
        )
        attributed_count = 0

        for sentence in sentences:
            try:
                prompt = CONTEXT_RECALL_ATTRIBUTION_PROMPT.format(
                    sentence=sentence, contexts=context_text
                )
                response = self._call_llm(prompt)
                attributed = int(
                    self._parse_json_field(response, "attributed", default=0)
                )
                attributed_count += attributed
            except Exception as e:
                logger.warning(f"归因验证失败: {sentence[:50]}... -> {e}")

        return round(attributed_count / len(sentences), 4)

    def _split_ground_truth(self, ground_truth: str) -> List[str]:
        """将 ground_truth 拆分为独立信息句。"""
        prompt = CONTEXT_RECALL_SENTENCE_SPLIT_PROMPT.format(
            ground_truth=ground_truth
        )
        response = self._call_llm(prompt)
        sentences = self._parse_json_array(response)
        return [s.strip() for s in sentences if s.strip()]

    # ========================================================================
    # 4. Answer Relevancy（答案相关性）
    # ========================================================================

    def _answer_relevancy(self, question: str, answer: str) -> float:
        """反向生成问题 + 与原问题的语义相似度（基于 embedding）。

        由于不依赖外部 embedding 模型，这里使用基于 LLM 的相似度判断
        或简单的文本相似度（当 LLM 不可用时）。

        如果可以获取 embedding 向量，使用余弦相似度；
        否则退化为基于关键词的 Jaccard 相似度。
        """
        # 反向生成问题
        generated_questions = self._reverse_generate_questions(answer)
        if not generated_questions:
            return 0.0

        # 计算语义相似度
        similarities = []
        for gen_q in generated_questions:
            sim = self._compute_semantic_similarity(question, gen_q)
            similarities.append(sim)

        return round(float(np.mean(similarities)), 4)

    def _reverse_generate_questions(self, answer: str) -> List[str]:
        """根据答案反向生成问题列表。"""
        prompt = ANSWER_RELEVANCY_REVERSE_QUESTION_PROMPT.format(
            n=self._reverse_question_count, answer=answer
        )
        response = self._call_llm(prompt)
        questions = self._parse_json_array(response)
        return [q.strip() for q in questions if q.strip()]

    def _compute_semantic_similarity(self, q1: str, q2: str) -> float:
        """计算两个问题的语义相似度。

        使用基于 LLM 的相似度判断（0-1 之间的分数），
        比纯文本方法更准确，且不依赖外部 embedding 模型。
        """
        prompt = f"""\
Your task is to rate the semantic similarity between two questions on a scale of 0.0 to 1.0.

Question 1: {q1}
Question 2: {q2}

Instructions:
1. 1.0 means the questions are semantically identical.
2. 0.0 means they are completely unrelated.
3. Consider meaning, not exact wording.
4. Output ONLY a JSON object with a single key "similarity" set to a float between 0.0 and 1.0.

Output format:
{{"similarity": 0.85}}
"""
        response = self._call_llm(prompt)
        try:
            similarity = float(self._parse_json_field(response, "similarity", default=0.5))
            return max(0.0, min(1.0, similarity))
        except Exception:
            # 回退到简单文本相似度
            return self._fallback_text_similarity(q1, q2)

    @staticmethod
    def _fallback_text_similarity(q1: str, q2: str) -> float:
        """基于 Jaccard 的简单文本相似度（回退方案）。"""
        words1 = set(q1.lower().split())
        words2 = set(q2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    # ========================================================================
    # LLM 调用与 JSON 解析工具
    # ========================================================================

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM 并返回文本响应。

        支持同步和异步 callable。
        """
        messages = [{"role": "user", "content": prompt}]

        # 同步调用
        if callable(self._llm_call):
            import inspect
            result = self._llm_call(messages)
            # 如果是协程，在同步上下文中运行
            if inspect.iscoroutine(result):
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, result)
                            return future.result(timeout=120)
                    else:
                        return loop.run_until_complete(result)
                except RuntimeError:
                    return asyncio.run(result)
            return str(result)

        raise TypeError("_llm_call must be callable")

    @staticmethod
    def _parse_json_field(
        response: str, key: str, default: Any = None
    ) -> Any:
        """从 LLM 响应中解析 JSON 对象的指定字段。

        支持多种格式容错：
        - 纯 JSON: {"key": value}
        - 含 Markdown 代码块: ```json\n{...}\n```
        - 含额外文本的前后 JSON
        """
        # 尝试提取 Markdown 代码块中的 JSON
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```",
            response,
            re.DOTALL,
        )
        if code_block_match:
            response = code_block_match.group(1)

        # 尝试提取 JSON 对象
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                obj = json.loads(json_match.group(0))
                return obj.get(key, default)
            except json.JSONDecodeError:
                pass

        # 尝试直接从完整响应解析
        try:
            obj = json.loads(response.strip())
            return obj.get(key, default)
        except json.JSONDecodeError:
            pass

        # 最终回退
        logger.warning(
            f"无法从 LLM 响应中解析字段 '{key}'，响应前 200 字符：{response[:200]}"
        )
        return default

    @staticmethod
    def _parse_json_array(response: str) -> List[str]:
        """从 LLM 响应中解析 JSON 数组。

        支持多种格式容错，返回字符串列表。
        """
        # 尝试提取 Markdown 代码块中的 JSON
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(\[.*?\])\s*\n?```",
            response,
            re.DOTALL,
        )
        if code_block_match:
            response = code_block_match.group(1)

        # 尝试提取 JSON 数组
        arr_match = re.search(r"\[.*\]", response, re.DOTALL)
        if arr_match:
            try:
                arr = json.loads(arr_match.group(0))
                return [str(item) for item in arr]
            except json.JSONDecodeError:
                pass

        # 尝试直接从完整响应解析
        try:
            arr = json.loads(response.strip())
            return [str(item) for item in arr]
        except json.JSONDecodeError:
            pass

        # 最终回退：按行分割
        logger.warning(
            f"无法从 LLM 响应中解析 JSON 数组，回退到按行分割。"
            f"响应前 200 字符：{response[:200]}"
        )
        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
        # 去除序号前缀 (如 "1. ", "- ")
        lines = [re.sub(r"^\d+\.\s*", "", l) for l in lines]
        lines = [re.sub(r"^[-*]\s*", "", l) for l in lines]
        return lines
