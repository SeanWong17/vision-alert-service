"""日志模块：统一输出到控制台与滚动文件，支持 JSON 结构化格式。"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler

from app.common.settings import settings

DEFAULT_LOG_FORMAT = "[%(asctime)s][%(levelname)s][%(name)s:%(lineno)d] %(message)s"
_CURRENT_REQUEST_ID: ContextVar[str | None] = ContextVar("current_request_id", default=None)


class JsonFormatter(logging.Formatter):
    """将日志记录序列化为单行 JSON，适用于 ELK / Loki / CloudWatch 等日志聚合系统。"""

    def format(self, record: logging.LogRecord) -> str:
        """将 LogRecord 格式化为 JSON 字符串。"""

        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        # 附加结构化上下文字段（由调用方通过 extra 传入）
        for key in ("request_id", "session_id", "image_id", "duration_ms", "error_code"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def build_logger(log_dir: str, log_name: str = "ai_alerting.log", level: int = logging.INFO) -> logging.Logger:
    """构建并返回可复用 logger，通过 ALERT_LOG_FORMAT 环境变量控制输出格式。

    ALERT_LOG_FORMAT=json 时启用 JSON 结构化格式，否则使用传统文本格式。
    """

    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        # 日志目录不可写时（如非 root 用户运行默认路径），回退到临时目录。
        import tempfile
        log_dir = os.path.join(tempfile.gettempdir(), "ai_alerting_log")
        os.makedirs(log_dir, exist_ok=True)

    log = logging.getLogger(log_name)
    log.setLevel(level)
    log.propagate = False

    # 避免重复初始化时 handler 叠加。
    for handler in list(log.handlers):
        handler.close()
        log.removeHandler(handler)

    use_json = os.getenv("ALERT_LOG_FORMAT", "").strip().lower() == "json"
    formatter: logging.Formatter = JsonFormatter() if use_json else logging.Formatter(DEFAULT_LOG_FORMAT)

    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, log_name),
        when="D",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)
    return log


def bind_request_id(request_id: str):
    """将 request_id 绑定到当前上下文。"""

    return _CURRENT_REQUEST_ID.set(request_id)


def reset_request_id(token) -> None:
    """重置当前上下文中的 request_id。"""

    _CURRENT_REQUEST_ID.reset(token)


def request_log_extra(**extra) -> dict:
    """为日志补齐当前 request_id，便于跨线程串联请求链路。"""

    request_id = _CURRENT_REQUEST_ID.get()
    if request_id:
        extra.setdefault("request_id", request_id)
    return extra


# 导出全局 logger，供各模块直接使用。
logger = build_logger(settings.filepath.log)
