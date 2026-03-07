"""告警存储层测试。"""

import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import pydantic  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class AlertStoreTest(unittest.TestCase):
    """验证队列与结果存取语义。"""

    def setUp(self):
        """初始化测试存储对象并强制使用内存后端。"""

        from app.alerting.schemas import AlarmTask, QueueTask, StoredResult
        from app.alerting.store import AlertStore
        from app.core.settings import AlertSettings

        self.AlarmTask = AlarmTask
        self.QueueTask = QueueTask
        self.StoredResult = StoredResult

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        self.store = AlertStore(settings)
        self.store.redis = None

    def test_enqueue_pop_and_pending(self):
        """写入队列后应可读取 pending 并正常 pop。"""

        task = self.QueueTask(
            image_id="img-1",
            session_id="s1",
            file_name="a.jpg",
            file_path="/tmp/a.jpg",
            tasks=[self.AlarmTask(id=1, params={"limit": 1, "coordinate": [-1, -1, -1, -1]})],
        )
        self.store.enqueue(task)
        self.assertEqual(self.store.queue_length(), 1)

        pending = self.store.get_pending("s1", "img-1")
        self.assertIsNotNone(pending)

        popped = self.store.pop()
        self.assertIsNotNone(popped)
        self.assertEqual(popped.image_id, "img-1")

    def test_result_fetch_and_confirm(self):
        """结果拉取与确认删除行为应符合预期。"""

        self.store.save_result(
            "s1",
            "img-1",
            self.StoredResult(imageId="img-1", filename="a.jpg", results=[{"reserved": "1"}]),
        )
        rows, has_more = self.store.fetch_results("s1", limit=10)
        self.assertFalse(has_more)
        self.assertEqual(len(rows), 1)

        self.store.save_result(
            "s1",
            "img-2",
            self.StoredResult(imageId="img-2", filename="b.jpg", results=[{"reserved": "0"}]),
        )
        self.store.confirm_results("s1", ["img-2"])
        rows2, _ = self.store.fetch_results("s1", limit=10)
        self.assertEqual(rows2, [])


if __name__ == "__main__":
    unittest.main()
