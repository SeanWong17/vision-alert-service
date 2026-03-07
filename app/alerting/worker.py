"""后台工作线程：持续消费队列并并行执行推理任务。"""

from __future__ import annotations

import multiprocessing
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.alerting.service import AlertService
from app.common.logging import logger


class AlertWorker:
    """异步任务消费器。"""

    def __init__(self, service: AlertService, poll_seconds: float = 0.05, max_workers: int | None = None):
        """初始化 worker 的轮询参数和线程池。"""

        self.service = service
        self.poll_seconds = poll_seconds
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() // 2)
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="alert-worker")
        self._thread = threading.Thread(target=self._loop, name="alert-queue-consumer", daemon=True)
        self._stop = threading.Event()

    def start(self) -> None:
        """启动消费线程（幂等）。"""

        if self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="alert-queue-consumer", daemon=True)
        self._thread.start()
        logger.info("alert worker started threads=%d", self.max_workers)

    def stop(self) -> None:
        """停止消费线程并关闭线程池。"""

        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("alert worker stopped")

    def _loop(self) -> None:
        """轮询队列并提交任务到线程池。"""

        while not self._stop.is_set():
            try:
                task = self.service.store.pop()
                if not task:
                    time.sleep(self.poll_seconds)
                    continue
                self._executor.submit(self.service.process_async_task, task)
            except Exception as exc:
                logger.exception("alert worker loop error: %s", exc)
                time.sleep(self.poll_seconds)
