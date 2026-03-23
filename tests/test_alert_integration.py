"""最小集成测试：upload -> worker -> alarm_result。"""

import os
import tempfile
import unittest

from tests.conftest import DummyUpload, jpeg_bytes, make_fake_pipeline, runtime_ready


@unittest.skipUnless(runtime_ready("cv2", "numpy", "pydantic"), "runtime deps not installed")
class AlertIntegrationTest(unittest.TestCase):
    """验证异步链路的最小可用性。"""

    def setUp(self):
        """创建服务对象并注入假流水线。"""

        from app.alerting.service import AlertService
        from app.alerting.store import AlertStore
        from app.common.settings import AlertSettings

        self.tmp = tempfile.TemporaryDirectory()
        settings = AlertSettings(
            upload_root=os.path.join(self.tmp.name, "upload"),
            result_root=os.path.join(self.tmp.name, "result"),
            model_root="/tmp/m",
        )
        self.store = AlertStore(settings)
        self.store.redis = None
        self.service = AlertService(settings, self.store, make_fake_pipeline())

    def tearDown(self):
        """释放临时目录。"""

        self.tmp.cleanup()

    def test_upload_worker_alarm_result(self):
        """执行完整异步流程并校验结果输出字段。"""

        upload = DummyUpload("cam_A.jpg", jpeg_bytes(11))
        submit = self.service.submit_async(
            upload,
            {"filename": "cam_A.jpg", "sessionId": "SID-1"},
            [{"id": 1, "params": {"limit": 0}}],
        )
        self.assertEqual(submit["code"], 0)

        task = self.store.pop()
        self.assertIsNotNone(task)
        self.service.process_async_task(task)

        result = self.service.get_alarm_result("SID-1")
        self.assertEqual(result["code"], 0)
        self.assertIn("items", result)
        self.assertGreaterEqual(len(result["items"]), 1)


if __name__ == "__main__":
    unittest.main()
