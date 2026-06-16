#!/bin/bash
# ============================================
# RAG 评测系统 - 依赖一键安装 (Linux/Mac)
# ============================================

echo ""
echo "[RAG 评测系统] 开始安装依赖..."
echo ""

echo "[1/2] 安装方案A依赖（RAGAS）..."
pip install -r requirements-ragas.txt || echo "[警告] 方案A依赖安装失败，方案B仍可正常使用"

echo ""
echo "[2/2] 安装通用依赖..."
pip install pytest scikit-learn numpy || echo "[警告] 通用依赖安装失败"

echo ""
echo "============================================"
echo "安装完成！"
echo ""
echo "用法:"
echo "  from evaluation import RagasEvaluator    # 方案A"
echo "  from evaluation import LLMJudgeEvaluator  # 方案B"
echo "============================================"
