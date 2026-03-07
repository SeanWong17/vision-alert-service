"""告警运行时容器模块：负责组件装配与单例管理。"""

from __future__ import annotations

from threading import Lock

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
