"""告警运行时容器模块：负责组件装配与单例管理。"""

from __future__ import annotations

from threading import Lock
from typing import Any, Dict

from app.alerting.config import load_alert_settings
from app.alerting.pipeline import AlertPipeline
from app.alerting.service import AlertService
from app.alerting.store import AlertStore
from app.alerting.worker import AlertWorker

_runtime_lock = Lock()
_runtime = None


def get_runtime() -> dict:
    """按需构建并返回运行时依赖图。"""

    global _runtime
    if _runtime is not None:
        return _runtime

    with _runtime_lock:
        if _runtime is not None:
            return _runtime

        settings = load_alert_settings()
        store = AlertStore(settings)
        pipeline = AlertPipeline(settings)
        service = AlertService(settings, store, pipeline)
        worker = AlertWorker(
            service,
            poll_seconds=settings.worker_poll_seconds,
            max_workers=settings.worker_threads,
            max_inflight=settings.worker_max_inflight,
        )
        _runtime = {
            "settings": settings,
            "store": store,
            "pipeline": pipeline,
            "service": service,
            "worker": worker,
        }

    return _runtime


def reset_runtime() -> None:
    """重置运行时单例（仅用于测试）。"""

    global _runtime
    with _runtime_lock:
        _runtime = None


# ---- FastAPI 依赖注入 ----

def _get_service() -> AlertService:
    """FastAPI Depends() 可用的服务依赖。"""

    return get_runtime()["service"]


def _get_store() -> AlertStore:
    """FastAPI Depends() 可用的存储依赖。"""

    return get_runtime()["store"]


def _get_worker() -> AlertWorker:
    """FastAPI Depends() 可用的 worker 依赖。"""

    return get_runtime()["worker"]
