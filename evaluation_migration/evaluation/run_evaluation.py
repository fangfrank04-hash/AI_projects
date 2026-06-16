#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
独立评测脚本 — 从评测数据集读用例 → 调 RAG → 算指标 → 出报告

这是领导要的核心交付物：一个能定时/自动跑的评测脚本。

用法:
    # 基础用法（读 JSON 数据集，模拟 RAG 回答）
    python run_evaluation.py --dataset tests/mock_data/eval_dataset.json

    # 指定输出报告路径
    python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --output report.json

    # 输出 Markdown 格式报告
    python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --output report.md --format markdown

    # 只计算部分指标
    python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --metrics faithfulness,context_precision

    # 使用方案A (RAGAS 库，需要 OpenAI Key)
    python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --method ragas --openai-key sk-xxx

定时运行（Linux cron）:
    0 8 * * * cd /path/to/ragflow && python run_evaluation.py --dataset qa_dataset.json --output /var/log/rag_eval/report.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# 确保项目根目录可导入
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ============================================================================
# 命令行参数
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="RAG 评测脚本 — 从数据集读用例，调 RAG，算指标，出报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_evaluation.py --dataset eval_dataset.json
  python run_evaluation.py --dataset eval_dataset.json --output report.md --format markdown
  python run_evaluation.py --dataset eval_dataset.json --metrics faithfulness,context_precision
        """,
    )

    parser.add_argument(
        "--dataset", "-d",
        required=True,
        help="评测数据集 JSON 文件路径",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出报告路径（默认打印到控制台）",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown", "text"],
        default="text",
        help="输出格式（默认 text）",
    )
    parser.add_argument(
        "--method", "-m",
        choices=["llm_judge", "ragas"],
        default="llm_judge",
        help="评测方法（默认 llm_judge）",
    )
    parser.add_argument(
        "--metrics",
        default=None,
        help="需要计算的指标，逗号分隔（如 faithfulness,context_precision）",
    )
    parser.add_argument(
        "--rag-script",
        default=None,
        help="外部 RAG 查询脚本路径 fn(question) -> {answer, contexts}",
    )
    parser.add_argument(
        "--openai-key",
        default=None,
        help="OpenAI API Key（方案A ragas 需要）",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-4o-mini",
        help="OpenAI 模型名（默认 gpt-4o-mini）",
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        help="限制评测用例数量（调试用）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细过程",
    )

    return parser.parse_args()


# ============================================================================
# 数据集加载
# ============================================================================

def load_dataset(path: str) -> List[Dict[str, Any]]:
    """加载评测数据集，支持两种格式。

    格式A（标准）:
        {"cases": [{"question": "...", "reference_answer": "...", ...}, ...]}

    格式B（简化）:
        [{"question": "...", "reference_answer": "..."}, ...]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    if isinstance(data, dict) and "samples" in data:
        return data["samples"]

    raise ValueError(f"无法识别的数据集格式: {path}")


# ============================================================================
# RAG 模拟（默认，生产环境替换为真实 RAG 函数）
# ============================================================================

def default_rag_function(question: str) -> Dict[str, Any]:
    """默认模拟 RAG 函数。生产环境中替换为真实的 RAG pipeline 调用。

    会被 --rag-script 参数覆盖。
    """
    return {
        "answer": f'[模拟回答] 关于「{question[:50]}」的回答：这是一个 RAG 检索增强生成系统产生的答案。',
        "contexts": [
            f"[模拟上下文 1] 这是关于 {question[:30]} 的第一段相关文档。",
            f"[模拟上下文 2] 这是关于 {question[:30]} 的第二段相关文档。",
        ],
    }


def load_rag_function(script_path: Optional[str]) -> Callable:
    """从外部脚本加载 RAG 查询函数。

    脚本应定义一个 query(question) -> {"answer", "contexts"} 函数。
    """
    if not script_path:
        return default_rag_function

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "rag_script", os.path.abspath(script_path)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    for attr in ["query", "rag", "ask", "chat"]:
        if hasattr(mod, attr):
            return getattr(mod, attr)

    raise ValueError(
        f"外部脚本 {script_path} 中未找到 query/rag/ask/chat 函数。"
        f"请确保脚本定义了 fn(question) -> {{'answer': ..., 'contexts': [...]}}"
    )


# ============================================================================
# Mock LLM（方案B 使用，真实环境替换为 LLMBundle）
# ============================================================================

class MockJudgeLLM:
    """模拟评测 LLM，真实环境替换为 ragflow 的 LLMBundle.chat()。

    在启动脚本中替换：
        set_llm_callable(LLMBundle(tenant_id, "chat", model_name).chat)
    """
    def __init__(self):
        self.call_count = 0

    def chat(self, messages):
        self.call_count += 1
        prompt = messages[0]["content"]

        if "extract all atomic" in prompt.lower():
            return '["声明1", "声明2"]'
        if "verdict" in prompt.lower():
            return '{"verdict": 1}'
        if "relevant" in prompt.lower():
            return '{"relevant": 1}'
        if "split the following reference answer" in prompt.lower():
            return '["句子1", "句子2"]'
        if "attributed" in prompt.lower():
            return '{"attributed": 1}'
        if "generate exactly" in prompt.lower():
            return '["问题1", "问题2", "问题3"]'
        if "similarity" in prompt.lower():
            return '{"similarity": 0.80}'

        return '{"verdict": 1}'


# ============================================================================
# 评测执行
# ============================================================================

def run_evaluation(
    cases: List[Dict[str, Any]],
    rag_function: Callable,
    method: str = "llm_judge",
    metrics: Optional[List[str]] = None,
    openai_key: Optional[str] = None,
    openai_model: str = "gpt-4o-mini",
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """执行评测，返回每条用例的结果。

    Args:
        cases: 评测用例列表
        rag_function: RAG 查询函数 fn(question) -> {"answer", "contexts"}
        method: 评测方法
        metrics: 指标列表
        openai_key: OpenAI API Key（方案A）
        openai_model: OpenAI 模型名（方案A）
        verbose: 显示详细过程

    Returns:
        [{"question": ..., "answer": ..., "faithfulness": 0.85, ...}, ...]
    """
    from evaluation.base import BaseEvaluator

    if method == "ragas":
        return _run_with_ragas(cases, rag_function, metrics, openai_key, openai_model, verbose)
    else:
        return _run_with_llm_judge(cases, rag_function, metrics, verbose)


def _run_with_llm_judge(
    cases, rag_function, metrics, verbose
) -> List[Dict[str, Any]]:
    """方案B：手工 LLM-as-Judge。"""
    from evaluation.auto_hook import set_llm_callable, auto_evaluate

    # 初始化评测 LLM
    judge_llm = MockJudgeLLM()
    set_llm_callable(judge_llm.chat)

    results = []
    total = len(cases)

    for i, case in enumerate(cases):
        question = case["question"]
        ground_truth = case.get("reference_answer") or case.get("ground_truth")

        # 调用 RAG 系统
        if verbose:
            print(f"[{i+1}/{total}] 评测: {question[:60]}...")

        try:
            rag_result = rag_function(question)
            answer = rag_result.get("answer", "")
            contexts = rag_result.get("contexts", [])
        except Exception as e:
            print(f"[{i+1}/{total}] RAG 调用失败: {e}")
            answer = f"[错误] {e}"
            contexts = []

        # 自动评测
        try:
            scores = auto_evaluate(
                question=question,
                answer=answer,
                contexts=contexts,
                ground_truth=ground_truth,
                metrics=metrics,
            )
        except Exception as e:
            print(f"[{i+1}/{total}] 评测失败: {e}")
            scores = {"faithfulness": None, "context_precision": None, "context_recall": None, "answer_relevancy": None}

        result = {
            "question": question,
            "answer": answer[:300],
            "contexts_count": len(contexts),
            "has_ground_truth": ground_truth is not None,
            **scores,
        }
        results.append(result)

        if verbose and i < 3:  # 只打印前3条的详细结果
            print(f"  → faithfulness={scores.get('faithfulness')}, "
                  f"precision={scores.get('context_precision')}, "
                  f"relevancy={scores.get('answer_relevancy')}")

    print(f"\n评测完成！LLM 调用了 {judge_llm.call_count} 次")
    return results


def _run_with_ragas(
    cases, rag_function, metrics, openai_key, openai_model, verbose
) -> List[Dict[str, Any]]:
    """方案A：RAGAS 库。"""
    if not openai_key:
        print("[错误] 方案A需要 --openai-key 参数")
        sys.exit(1)

    os.environ["OPENAI_API_KEY"] = openai_key

    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from evaluation.ragas_evaluator import RagasEvaluator
    except ImportError as e:
        print(f"[错误] 方案A依赖缺失: {e}")
        print("请安装: pip install ragas datasets langchain langchain-openai")
        sys.exit(1)

    llm = ChatOpenAI(model=openai_model, temperature=0)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    evaluator = RagasEvaluator(llm=llm, embeddings=embeddings)

    questions, answers, contexts_list, ground_truths = [], [], [], []

    for case in cases:
        q = case["question"]
        questions.append(q)
        ground_truths.append(case.get("reference_answer") or case.get("ground_truth"))

        try:
            rag_result = rag_function(q)
            answers.append(rag_result.get("answer", ""))
            contexts_list.append(rag_result.get("contexts", []))
        except Exception:
            answers.append("")
            contexts_list.append([])

    batch_result = evaluator.evaluate_batch(
        questions=questions,
        answers=answers,
        contexts_list=contexts_list,
        ground_truths=ground_truths,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
    )

    results = []
    for i, score in enumerate(batch_result["scores"]):
        results.append({
            "question": questions[i],
            "answer": answers[i][:300],
            "contexts_count": len(contexts_list[i]),
            **score,
        })

    return results


# ============================================================================
# 聚合 + 输出
# ============================================================================

def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """聚合评测结果。"""
    from evaluation.base import BaseEvaluator

    score_only = [
        {k: v for k, v in r.items() if k in ("faithfulness", "context_precision", "context_recall", "answer_relevancy")}
        for r in results
    ]
    return BaseEvaluator.aggregate(score_only)


def print_text_report(results: List[Dict[str, Any]], aggregate: Dict[str, Any]):
    """控制台文本格式报告。"""
    print("\n" + "=" * 60)
    print("  RAG 评测报告")
    print("=" * 60)
    print(f"  评测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  总用例数: {len(results)}")
    print("-" * 60)

    for metric in ["faithfulness", "context_precision", "context_recall", "answer_relevancy"]:
        key = f"avg_{metric}"
        if key in aggregate:
            count = aggregate["valid_count"].get(metric, 0)
            val = aggregate[key]
            bar = "█" * int(val * 20)
            print(f"  {metric:25s}: {val:.3f} ({count}/{len(results)} 条)  {bar}")
        else:
            print(f"  {metric:25s}: (未计算)")

    print("-" * 60)
    # 问题用例
    bad_cases = [r for r in results if r.get("faithfulness", 1.0) is not None and r.get("faithfulness", 1.0) < 0.5]
    if bad_cases:
        print(f"\n  ⚠️  忠实度 < 0.5 的用例 ({len(bad_cases)} 条):")
        for r in bad_cases[:5]:
            print(f"    - {r['question'][:60]}... (faithfulness={r.get('faithfulness')})")
    print("=" * 60)


def write_json_report(results: List[Dict[str, Any]], aggregate: Dict[str, Any], path: str):
    """输出 JSON 格式报告。"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "aggregate": aggregate,
        "results": results,
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"报告已保存: {path}")


def write_markdown_report(results: List[Dict[str, Any]], aggregate: Dict[str, Any], path: str):
    """输出 Markdown 格式报告。"""
    lines = [
        f"# RAG 评测报告",
        f"",
        f"**评测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**总用例数**: {len(results)}",
        f"",
        f"## 指标汇总",
        f"",
        f"| 指标 | 均值 | 有效条数 |",
        f"|------|------|---------|",
    ]

    for metric in ["faithfulness", "context_precision", "context_recall", "answer_relevancy"]:
        key = f"avg_{metric}"
        if key in aggregate:
            count = aggregate["valid_count"].get(metric, 0)
            val = aggregate[key]
            lines.append(f"| {metric} | {val:.3f} | {count}/{len(results)} |")
        else:
            lines.append(f"| {metric} | N/A | 0/{len(results)} |")

    lines += [
        f"",
        f"## 用例详情",
        f"",
    ]

    for i, r in enumerate(results):
        lines.append(f"### {i+1}. {r['question'][:80]}")
        lines.append(f"")
        lines.append(f"- Faithfulness: {r.get('faithfulness', 'N/A')}")
        lines.append(f"- Context Precision: {r.get('context_precision', 'N/A')}")
        lines.append(f"- Context Recall: {r.get('context_recall', 'N/A')}")
        lines.append(f"- Answer Relevancy: {r.get('answer_relevancy', 'N/A')}")
        lines.append(f"")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"报告已保存: {path}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    args = parse_args()

    # 1. 加载数据集
    print(f"加载数据集: {args.dataset}")
    cases = load_dataset(args.dataset)
    if args.limit:
        cases = cases[:args.limit]
    print(f"共 {len(cases)} 条用例")

    # 2. 加载 RAG 函数
    rag_fn = load_rag_function(args.rag_script)

    # 3. 解析指标
    metrics = None
    if args.metrics:
        metrics = [m.strip() for m in args.metrics.split(",")]

    # 4. 执行评测
    print(f"评测方法: {args.method}")
    print(f"开始评测...")
    start_time = time.time()

    results = run_evaluation(
        cases=cases,
        rag_function=rag_fn,
        method=args.method,
        metrics=metrics,
        openai_key=args.openai_key,
        openai_model=args.openai_model,
        verbose=args.verbose,
    )

    elapsed = time.time() - start_time
    print(f"耗时: {elapsed:.1f}s")

    # 5. 聚合
    aggregate = aggregate_results(results)

    # 6. 输出
    if args.output:
        if args.format == "markdown" or (args.format == "json" and False):
            pass

        if args.output.endswith(".md") or args.format == "markdown":
            write_markdown_report(results, aggregate, args.output)
        else:
            write_json_report(results, aggregate, args.output)

    print_text_report(results, aggregate)

    return results, aggregate


if __name__ == "__main__":
    main()
