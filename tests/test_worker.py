"""AlertWorker 单元测试。

验证后台消费线程的启停幂等性、运行状态查询和并发计数等核心行为。
"""

from __future__ import annotations

import contextlib
import multiprocessing
import time
import types
import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import pydantic  # noqa: F401

        return True
    except Exception:
        return False


def _make_fake_service():
    """构造一个满足 AlertWorker 依赖的假 service 对象。

    AlertWorker._loop 在轮询时会访问：
      - service.settings.cleanup_scan_interval_seconds
      - service.store.pop()
      - service.cleanup_expired_images()
      - service.process_async_task(task)

    这里用 SimpleNamespace 搭建最小替身，store.pop() 始终返回 None
    以避免真正提交推理任务。
    """
    service = types.SimpleNamespace()
    service.settings = types.SimpleNamespace(cleanup_scan_interval_seconds=9999)
    service.store = types.SimpleNamespace(pop=lambda: None)
    service.cleanup_expired_images = lambda: None
    service.process_async_task = lambda task: None
    return service


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class TestAlertWorkerLifecycle(unittest.TestCase):
    """测试 AlertWorker 的启停生命周期与幂等性。"""

    def setUp(self):
        """每个测试用例使用独立的 worker 实例。"""

        from app.alerting.worker import AlertWorker

        self.AlertWorker = AlertWorker
        self.service = _make_fake_service()
        self.worker = AlertWorker(self.service, poll_seconds=0.01)

    def tearDown(self):
        """确保测试结束后 worker 被停止，避免线程泄漏。"""
        with contextlib.suppress(Exception):
            self.worker.stop()

    # ------------------------------------------------------------------
    # 启动幂等性
    # ------------------------------------------------------------------

    def test_start_is_idempotent(self):
        """多次调用 start() 不应重复创建线程或抛出异常。"""
        self.worker.start()
        self.worker.start()  # 第二次调用应直接返回
        self.assertTrue(self.worker.is_running())

    # ------------------------------------------------------------------
    # 停止幂等性
    # ------------------------------------------------------------------

    def test_stop_is_idempotent(self):
        """在未启动时调用 stop() 不应抛出异常。"""
        self.worker.stop()
        self.worker.stop()

    def test_stop_after_start_is_idempotent(self):
        """启动后连续两次 stop() 不应抛出异常。"""
        self.worker.start()
        self.worker.stop()
        self.worker.stop()

    # ------------------------------------------------------------------
    # is_running 状态
    # ------------------------------------------------------------------

    def test_is_running_before_start(self):
        """未启动前 is_running 应返回 False。"""
        self.assertFalse(self.worker.is_running())

    def test_is_running_after_start(self):
        """启动后 is_running 应返回 True。"""
        self.worker.start()
        self.assertTrue(self.worker.is_running())

    def test_is_running_after_stop(self):
        """停止后 is_running 应返回 False。"""
        self.worker.start()
        self.assertTrue(self.worker.is_running())
        self.worker.stop()
        self.assertFalse(self.worker.is_running())

    # ------------------------------------------------------------------
    # inflight_tasks
    # ------------------------------------------------------------------

    def test_inflight_tasks_initial_value(self):
        """初始状态下 inflight_tasks 应为 0。"""
        self.assertEqual(self.worker.inflight_tasks(), 0)

    def test_inflight_tasks_zero_after_start(self):
        """启动后若无任务入队，inflight_tasks 仍应为 0。"""
        self.worker.start()
        # 给轮询线程一点运行时间
        time.sleep(0.05)
        self.assertEqual(self.worker.inflight_tasks(), 0)

    # ------------------------------------------------------------------
    # max_workers 默认值
    # ------------------------------------------------------------------

    def test_max_workers_default(self):
        """未指定 max_workers 时应取 CPU 核心数 / 2（至少 1）。"""
        expected = max(1, multiprocessing.cpu_count() // 2)
        self.assertEqual(self.worker.max_workers, expected)

    def test_max_workers_custom(self):
        """显式传入 max_workers 时应使用指定值。"""
        worker = self.AlertWorker(self.service, max_workers=3)
        self.assertEqual(worker.max_workers, 3)
        worker.stop()

    # ------------------------------------------------------------------
    # 重启
    # ------------------------------------------------------------------

    def test_restart_after_stop(self):
        """停止后可以重新启动，且 is_running 恢复为 True。"""
        self.worker.start()
        self.worker.stop()
        self.assertFalse(self.worker.is_running())

        # 重新构建一个 worker（stop 会关闭线程池，原实例不可重用）
        self.worker = self.AlertWorker(self.service, poll_seconds=0.01)
        self.worker.start()
        self.assertTrue(self.worker.is_running())


if __name__ == "__main__":
    unittest.main()
