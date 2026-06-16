# -*- coding: utf-8 -*-
"""
RAG 评测系统初始化
在 ragflow 启动时自动执行，初始化评测 LLM。
"""

import logging

logger = logging.getLogger(__name__)

_evaluator_ready = False


def init():
    """初始化评测系统。在 ragflow_server.py 的 if __name__ == '__main__': 里调用。"""
    global _evaluator_ready
    if _evaluator_ready:
        return

    try:
        from evaluation import set_llm_callable
        from api.db.services.llm_service import LLMBundle
        from api.db.services.tenant_llm_service import TenantLLMService

        # 获取默认的 chat 模型
        models = TenantLLMService.get_all_models(LLMType="chat")
        if not models:
            logger.warning("评测系统：未找到 chat 模型，跳过初始化")
            return

        # 使用第一个 chat 模型作为评测 LLM
        model_config = models[0]
        bundle = LLMBundle(model_config["tenant_id"], model_config, max_retries=0)

        set_llm_callable(bundle.chat)
        _evaluator_ready = True
        logger.info("评测系统初始化成功")
    except Exception as e:
        logger.warning(f"评测系统初始化失败（不影响正常功能）: {e}")
