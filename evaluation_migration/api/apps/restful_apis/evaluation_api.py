# -*- coding: utf-8 -*-
"""
RAG 评测系统 - HTTP RESTful API

提供 14 个 API 端点，管理评测数据集、测试用例、评测执行和结果查询。

支持两种使用模式：
  1. 作为 Quart Blueprint 挂载到 ragflow（生产环境）
  2. 独立运行（开发测试，python -m api.apps.restful_apis.evaluation_api）

API 前缀：/api/v1/evaluation

端点列表：
  数据集管理：
    POST   /datasets                           创建数据集
    GET    /datasets                           列出数据集
    GET    /datasets/{dataset_id}              获取数据集详情
    PUT    /datasets/{dataset_id}              更新数据集
    DELETE /datasets/{dataset_id}              删除数据集
  测试用例管理：
    POST   /datasets/{dataset_id}/cases        添加用例
    GET    /datasets/{dataset_id}/cases        列出用例
    POST   /datasets/{dataset_id}/cases/import 批量导入
    DELETE /datasets/{dataset_id}/cases/{cid}  删除用例
  评测执行：
    POST   /runs                               创建并启动 Run
    GET    /runs                               列出 Run
    GET    /runs/{run_id}                      获取 Run 详情
    GET    /runs/{run_id}/results              获取 Run 结果列表
    GET    /runs/{run_id}/results/{result_id}  获取单条结果
"""

import json
import logging
from typing import Any, Dict, List, Optional

# ── Quart 相关导入（尝试两种路径，兼容独立运行和 ragflow 集成） ──
try:
    from quart import Blueprint, jsonify, request
except ImportError:
    from flask import Blueprint, jsonify, request  # type: ignore

logger = logging.getLogger(__name__)

# ============================================================================
# Blueprint 定义
# ============================================================================

evaluation_bp = Blueprint("evaluation", __name__, url_prefix="/api/v1/evaluation")

# ============================================================================
# 内存存储（独立运行时使用，不依赖 ragflow DB）
# ============================================================================
# 生产环境中，这些由 evaluation_service.py + DB 替代
# 此处为独立运行模式提供内存存储，方便测试

_in_memory_store: Dict[str, Dict[str, Any]] = {
    "datasets": {},
    "cases": {},
    "runs": {},
    "results": {},
}


def _now() -> float:
    """获取当前 Unix 时间戳。"""
    import time
    return time.time()


def _uuid() -> str:
    """生成简单唯一 ID。"""
    import uuid
    return uuid.uuid4().hex[:12]


# ============================================================================
# 工具函数
# ============================================================================

def _success(data: Any = None, message: str = "ok") -> tuple:
    """构建成功响应。"""
    return jsonify({"code": 0, "message": message, "data": data}), 200


def _error(message: str, code: int = 400) -> tuple:
    """构建错误响应。"""
    return jsonify({"code": code, "message": message, "data": None}), code


async def _get_json() -> Dict[str, Any]:
    """获取请求 JSON body。"""
    if hasattr(request, "get_json"):
        return await request.get_json() or {}
    return request.get_json(silent=True) or {}


# ============================================================================
# 数据集管理 API
# ============================================================================

@evaluation_bp.route("/datasets", methods=["POST"])
async def create_dataset():
    """创建评测数据集。

    Body:
        name (str): 数据集名称（必填）
        description (str): 描述（可选）
        kb_ids (list[str]): 关联知识库 ID 列表（可选）
    """
    data = await _get_json()
    name = data.get("name", "").strip()
    if not name:
        return _error("数据集名称不能为空")

    ds_id = _uuid()
    dataset = {
        "id": ds_id,
        "name": name,
        "description": data.get("description", ""),
        "kb_ids": data.get("kb_ids", []),
        "created_by": data.get("user_id", "anonymous"),
        "create_time": _now(),
        "update_time": _now(),
        "status": 1,
        "case_count": 0,
    }
    _in_memory_store["datasets"][ds_id] = dataset
    _in_memory_store["cases"][ds_id] = []

    return _success(dataset, "数据集创建成功")


@evaluation_bp.route("/datasets", methods=["GET"])
async def list_datasets():
    """获取数据集列表。

    Query:
        page (int): 页码（默认 1）
        page_size (int): 每页条数（默认 20）
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    datasets = list(_in_memory_store["datasets"].values())
    datasets.sort(key=lambda d: d["create_time"], reverse=True)

    total = len(datasets)
    start = (page - 1) * page_size
    end = start + page_size

    return _success({
        "total": total,
        "page": page,
        "page_size": page_size,
        "datasets": datasets[start:end],
    })


@evaluation_bp.route("/datasets/<dataset_id>", methods=["GET"])
async def get_dataset(dataset_id: str):
    """获取单个数据集详情。"""
    ds = _in_memory_store["datasets"].get(dataset_id)
    if not ds:
        return _error("数据集不存在", 404)

    cases = _in_memory_store["cases"].get(dataset_id, [])
    ds["case_count"] = len(cases)
    return _success(ds)


@evaluation_bp.route("/datasets/<dataset_id>", methods=["PUT"])
async def update_dataset(dataset_id: str):
    """更新数据集信息。"""
    ds = _in_memory_store["datasets"].get(dataset_id)
    if not ds:
        return _error("数据集不存在", 404)

    data = await _get_json()
    if "name" in data:
        ds["name"] = data["name"].strip()
    if "description" in data:
        ds["description"] = data["description"]
    if "kb_ids" in data:
        ds["kb_ids"] = data["kb_ids"]
    ds["update_time"] = _now()

    return _success(ds, "更新成功")


@evaluation_bp.route("/datasets/<dataset_id>", methods=["DELETE"])
async def delete_dataset(dataset_id: str):
    """删除数据集（软删除）。"""
    ds = _in_memory_store["datasets"].get(dataset_id)
    if not ds:
        return _error("数据集不存在", 404)

    ds["status"] = 0
    return _success(None, "删除成功")


# ============================================================================
# 测试用例管理 API
# ============================================================================

@evaluation_bp.route("/datasets/<dataset_id>/cases", methods=["POST"])
async def add_test_case(dataset_id: str):
    """添加单条测试用例。

    Body:
        question (str): 测试问题（必填）
        reference_answer (str): 标准答案（可选）
        relevant_chunk_ids (list[str]): 相关 chunk ID（可选）
        metadata (dict): 附加元数据（可选）
    """
    if dataset_id not in _in_memory_store["datasets"]:
        return _error("数据集不存在", 404)

    data = await _get_json()
    question = data.get("question", "").strip()
    if not question:
        return _error("问题不能为空")

    case_id = _uuid()
    case = {
        "id": case_id,
        "dataset_id": dataset_id,
        "question": question,
        "reference_answer": data.get("reference_answer"),
        "relevant_chunk_ids": data.get("relevant_chunk_ids"),
        "metadata": data.get("metadata"),
        "create_time": _now(),
    }

    if dataset_id not in _in_memory_store["cases"]:
        _in_memory_store["cases"][dataset_id] = []
    _in_memory_store["cases"][dataset_id].append(case)

    return _success(case, "用例添加成功")


@evaluation_bp.route("/datasets/<dataset_id>/cases", methods=["GET"])
async def list_test_cases(dataset_id: str):
    """获取数据集下所有测试用例。"""
    if dataset_id not in _in_memory_store["datasets"]:
        return _error("数据集不存在", 404)

    cases = _in_memory_store["cases"].get(dataset_id, [])
    return _success({"total": len(cases), "cases": cases})


@evaluation_bp.route("/datasets/<dataset_id>/cases/import", methods=["POST"])
async def import_test_cases(dataset_id: str):
    """批量导入测试用例（JSON body）。

    Body:
        cases (list[dict]): 测试用例列表，每个包含 question（必填）等字段
    """
    if dataset_id not in _in_memory_store["datasets"]:
        return _error("数据集不存在", 404)

    data = await _get_json()
    cases_data = data.get("cases", [])
    if not cases_data:
        return _error("cases 列表不能为空")

    success_count = 0
    for case_data in cases_data:
        question = case_data.get("question", "").strip()
        if not question:
            continue

        case_id = _uuid()
        case = {
            "id": case_id,
            "dataset_id": dataset_id,
            "question": question,
            "reference_answer": case_data.get("reference_answer"),
            "relevant_chunk_ids": case_data.get("relevant_chunk_ids"),
            "metadata": case_data.get("metadata"),
            "create_time": _now(),
        }

        if dataset_id not in _in_memory_store["cases"]:
            _in_memory_store["cases"][dataset_id] = []
        _in_memory_store["cases"][dataset_id].append(case)
        success_count += 1

    return _success(
        {"imported": success_count, "total": len(cases_data)},
        f"成功导入 {success_count}/{len(cases_data)} 条用例",
    )


@evaluation_bp.route("/datasets/<dataset_id>/cases/<case_id>", methods=["DELETE"])
async def delete_test_case(dataset_id: str, case_id: str):
    """删除单条测试用例。"""
    cases = _in_memory_store["cases"].get(dataset_id, [])
    original_len = len(cases)
    _in_memory_store["cases"][dataset_id] = [
        c for c in cases if c["id"] != case_id
    ]

    if len(_in_memory_store["cases"][dataset_id]) == original_len:
        return _error("用例不存在", 404)

    return _success(None, "删除成功")


# ============================================================================
# 评测执行 API
# ============================================================================

@evaluation_bp.route("/runs", methods=["POST"])
async def create_run():
    """创建并执行评测 Run。

    Body:
        dataset_id (str): 数据集 ID（必填）
        name (str): Run 名称（可选）
        method (str): 评测方法，"ragas" 或 "llm_judge"（默认 "llm_judge"）
        metrics (list[str]): 需要计算的指标列表（可选，默认全部）
        config (dict): 评测配置快照（可选）

    注意：
        方案A (ragas) 需要正确配置的 LLM + Embeddings 对象。
        方案B (llm_judge) 需要 LLM callable 函数。
        独立运行模式下使用模拟 LLM 进行演示。
    """
    data = await _get_json()
    dataset_id = data.get("dataset_id", "")
    if not dataset_id or dataset_id not in _in_memory_store["datasets"]:
        return _error("数据集不存在或未指定", 404)

    run_id = _uuid()
    name = data.get("name", f"Run-{run_id[:8]}")
    method = data.get("method", "llm_judge")
    metrics = data.get("metrics", [
        "faithfulness", "context_precision", "context_recall", "answer_relevancy"
    ])

    run = {
        "id": run_id,
        "dataset_id": dataset_id,
        "name": name,
        "method": method,
        "config_snapshot": data.get("config", {}),
        "metrics_summary": None,
        "status": "RUNNING",
        "created_by": data.get("user_id", "anonymous"),
        "create_time": _now(),
        "complete_time": None,
    }
    _in_memory_store["runs"][run_id] = run

    # 获取测试用例
    cases = _in_memory_store["cases"].get(dataset_id, [])

    # 模拟评测执行（生产环境应调用真实 RAG pipeline + Evaluator）
    results = []
    from evaluation.base import BaseEvaluator

    for case in cases:
        result_id = _uuid()
        # 模拟生成答案和检索结果（生产环境应调用 dialog_service.async_chat()）
        generated_answer = f"[模拟回答] 关于「{case['question'][:30]}...」的回答"
        retrieved_chunks = [
            {"chunk_id": f"chunk_{_uuid()[:6]}", "content": "[模拟检索内容]"}
        ]

        # 模拟指标计算（生产环境应调用 Evaluator.evaluate()）
        mock_metrics = {
            "faithfulness": 0.85,
            "context_precision": 0.72,
            "context_recall": 0.66 if case.get("reference_answer") else None,
            "answer_relevancy": 0.90,
            "answer_length": len(generated_answer),
            "has_answer": 1.0,
            "precision": 0.75,
            "recall": 0.68,
            "f1_score": 0.71,
            "hit_rate": 1.0,
            "mrr": 0.50,
        }

        result = {
            "id": result_id,
            "run_id": run_id,
            "case_id": case["id"],
            "question": case["question"],
            "generated_answer": generated_answer,
            "retrieved_chunks": retrieved_chunks,
            "metrics": mock_metrics,
            "execution_time": 1.5,
            "token_usage": {"prompt_tokens": 500, "completion_tokens": 200},
            "create_time": _now(),
        }
        _in_memory_store["results"][result_id] = result
        results.append(result)

    # 聚合
    aggregate = BaseEvaluator.aggregate(
        [r["metrics"] for r in results]
    )

    run["metrics_summary"] = aggregate
    run["status"] = "COMPLETED"
    run["complete_time"] = _now()

    return _success({
        "run": run,
        "results_count": len(results),
    }, "评测完成")


@evaluation_bp.route("/runs", methods=["GET"])
async def list_runs():
    """获取评测 Run 列表。"""
    runs = list(_in_memory_store["runs"].values())
    runs.sort(key=lambda r: r["create_time"], reverse=True)
    return _success({"total": len(runs), "runs": runs})


@evaluation_bp.route("/runs/<run_id>", methods=["GET"])
async def get_run(run_id: str):
    """获取 Run 详情。"""
    run = _in_memory_store["runs"].get(run_id)
    if not run:
        return _error("Run 不存在", 404)
    return _success(run)


@evaluation_bp.route("/runs/<run_id>/results", methods=["GET"])
async def get_run_results(run_id: str):
    """获取 Run 的所有评测结果。"""
    if run_id not in _in_memory_store["runs"]:
        return _error("Run 不存在", 404)

    results = [
        r for r in _in_memory_store["results"].values()
        if r["run_id"] == run_id
    ]
    results.sort(key=lambda r: r["create_time"])

    return _success({
        "run": _in_memory_store["runs"][run_id],
        "total": len(results),
        "results": results,
    })


@evaluation_bp.route("/runs/<run_id>/results/<result_id>", methods=["GET"])
async def get_single_result(run_id: str, result_id: str):
    """获取单条评测结果详情。"""
    result = _in_memory_store["results"].get(result_id)
    if not result or result["run_id"] != run_id:
        return _error("结果不存在", 404)
    return _success(result)


# ============================================================================
# 独立运行
# ============================================================================

def create_app():
    """创建独立运行的 Quart/Flask 应用（用于开发测试）。"""
    try:
        from quart import Quart
        app = Quart(__name__)
    except ImportError:
        from flask import Flask
        app = Flask(__name__)

    app.register_blueprint(evaluation_bp)
    logger.info("评测 API 已注册，前缀: /api/v1/evaluation")
    return app


if __name__ == "__main__":
    app = create_app()
    print("=" * 60)
    print("RAG 评测系统 API 服务启动")
    print("=" * 60)
    print("API 端点:")
    print("  POST   /api/v1/evaluation/datasets")
    print("  GET    /api/v1/evaluation/datasets")
    print("  GET    /api/v1/evaluation/datasets/<id>")
    print("  PUT    /api/v1/evaluation/datasets/<id>")
    print("  DELETE /api/v1/evaluation/datasets/<id>")
    print("  POST   /api/v1/evaluation/datasets/<id>/cases")
    print("  GET    /api/v1/evaluation/datasets/<id>/cases")
    print("  POST   /api/v1/evaluation/datasets/<id>/cases/import")
    print("  DELETE /api/v1/evaluation/datasets/<id>/cases/<cid>")
    print("  POST   /api/v1/evaluation/runs")
    print("  GET    /api/v1/evaluation/runs")
    print("  GET    /api/v1/evaluation/runs/<id>")
    print("  GET    /api/v1/evaluation/runs/<id>/results")
    print("  GET    /api/v1/evaluation/runs/<id>/results/<rid>")
    print("=" * 60)
    app.run(host="0.0.0.0", port=9380, debug=True)
