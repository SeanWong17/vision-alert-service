"""日志模块：统一输出到控制台与滚动文件。"""

from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler

from app.common.settings import settings

DEFAULT_LOG_FORMAT = "[%(asctime)s][%(levelname)s][%(name)s:%(lineno)d] %(message)s"


def build_logger(log_dir: str, log_name: str = "ai_alerting.log", level: int = logging.INFO) -> logging.Logger:
    """构建并返回可复用 logger。"""

    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(log_name)
    logger.setLevel(level)
    logger.propagate = False

    # 避免重复初始化时 handler 叠加。
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, log_name),
        when="H",
        interval=1,
        backupCount=72,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


# 导出全局 logger，供各模块直接使用。
logger = build_logger(settings.filepath.log)
