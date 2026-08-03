"""日志配置

统一初始化 logging，替代散落的 print。级别由 .env 的 LOG_LEVEL 控制。

用法（在 main.py 里调用一次）：
    from app.core.logging import setup_logging
    setup_logging()
"""
import logging

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging() -> None:
    """初始化根日志器。重复调用不会叠加 handler。"""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    logging.getLogger(__name__).debug("logging initialized at level %s", settings.log_level)
