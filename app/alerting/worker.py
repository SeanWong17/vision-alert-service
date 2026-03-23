"""后台工作线程：持续消费队列并并行执行推理任务。"""

from __future__ import annotations

import contextlib
import multiprocessing
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.alerting.service import AlertService
from app.common.logging import logger


class AlertWorker:
    """异步任务消费器。"""

    def __init__(
        self,
        service: AlertService,
        poll_seconds: float = 0.05,
        max_workers: int | None = None,
        max_inflight: int = 64,
    ):
        """初始化 worker 的轮询参数和线程池。"""

        self.service = service
        self.poll_seconds = poll_seconds
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() // 2)
        self.max_inflight = max(1, int(max_inflight))
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="alert-worker")
        self._thread = threading.Thread(target=self._loop, name="alert-queue-consumer", daemon=True)
        self._stop = threading.Event()
        self._last_cleanup_ts = 0.0
        self._inflight_guard = threading.BoundedSemaphore(value=self.max_inflight)
        self._inflight_lock = threading.Lock()
        self._inflight_count = 0

    def start(self) -> None:
        """启动消费线程（幂等）。"""

        if self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="alert-queue-consumer", daemon=True)
        self._thread.start()
        logger.info("alert worker started threads=%d inflight=%d", self.max_workers, self.max_inflight)

    def stop(self) -> None:
        """停止消费线程并关闭线程池。"""

        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        # 停机时不主动取消 futures，避免已出队任务丢失并长期滞留 pending。
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("alert worker stopped")

    def is_running(self) -> bool:
        """返回消费线程运行状态。"""

        return self._thread.is_alive() and not self._stop.is_set()

    def inflight_tasks(self) -> int:
        """返回当前并发处理中任务数。"""

        with self._inflight_lock:
            return self._inflight_count

    def _loop(self) -> None:
        """轮询队列并提交任务到线程池。"""

        while not self._stop.is_set():
            acquired_slot = False
            inflight_marked = False
            try:
                now = time.time()
                if now - self._last_cleanup_ts >= float(self.service.settings.cleanup_scan_interval_seconds):
                    self.service.cleanup_expired_images()
                    self._last_cleanup_ts = now

                acquired_slot = self._inflight_guard.acquire(blocking=False)
                if not acquired_slot:
                    time.sleep(self.poll_seconds)
                    continue

                task = self.service.store.pop()
                if not task:
                    self._inflight_guard.release()
                    time.sleep(self.poll_seconds)
                    continue
                with self._inflight_lock:
                    self._inflight_count += 1
                    inflight_marked = True
                future = self._executor.submit(self.service.process_async_task, task)
                future.add_done_callback(self._log_task_exception)
            except Exception as exc:
                logger.exception("alert worker loop error: %s", exc)
                if inflight_marked:
                    with self._inflight_lock:
                        self._inflight_count = max(0, self._inflight_count - 1)
                if acquired_slot:
                    self._inflight_guard.release()
                time.sleep(self.poll_seconds)

    def _log_task_exception(self, future) -> None:
        """记录线程池任务异常，避免 silent failure。"""

        try:
            future.result()
        except Exception as exc:
            logger.exception("alert worker task crashed unexpectedly: %s", exc)
        finally:
            with self._inflight_lock:
                self._inflight_count = max(0, self._inflight_count - 1)
            with contextlib.suppress(ValueError):
                self._inflight_guard.release()
