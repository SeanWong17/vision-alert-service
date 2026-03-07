"""最小集成测试：upload -> worker -> alarm_result。"""

import io
import os
import tempfile
import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import pydantic  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class AlertIntegrationTest(unittest.TestCase):
    """验证异步链路的最小可用性。"""

    def setUp(self):
        """创建服务对象并注入假流水线。"""

        import numpy as np

        from app.alerting.pipeline import InferenceOutcome
        from app.alerting.schemas import DetectionBox, TaskResult

        class _DummyUpload:
            """模拟上传文件对象。"""

            def __init__(self, name: str, content: bytes, content_type: str = "image/jpeg"):
                """初始化上传对象。"""

                self.filename = name
                self.file = io.BytesIO(content)
                self.content_type = content_type

        class _FakePipeline:
            """模拟推理流水线。"""

            def run(self, image_path, tasks):
                """返回固定推理结果。"""

                _ = (image_path, tasks)
                return InferenceOutcome(
                    detections=[
                        DetectionBox(
                            coordinate=[10, 10, 20, 20],
                            score=0.95,
                            tagName="enter_water",
                            overlapWater=0.3,
                            distanceToWater=0.0,
                        )
                    ],
                    water_color={"water_ratio": 0.4},
                    shoreline_points=[[1, 1], [2, 2]],
                    rendered_image=np.zeros((16, 16, 3), dtype=np.uint8),
                )

            def build_task_results(self, tasks, outcome):
                """将固定结果包装为任务返回。"""

                _ = outcome
                return [TaskResult(id=task.id, reserved="1", detail=[{"foo": "bar"}]) for task in tasks]

        from app.alerting.service import AlertService
        from app.alerting.store import AlertStore
        from app.core.settings import AlertSettings

        self.DummyUpload = _DummyUpload

        self.tmp = tempfile.TemporaryDirectory()
        settings = AlertSettings(
            upload_root=os.path.join(self.tmp.name, "upload"),
            result_root=os.path.join(self.tmp.name, "result"),
            model_root="/tmp/m",
        )
        self.store = AlertStore(settings)
        self.store.redis = None
        self.service = AlertService(settings, self.store, _FakePipeline())

    def tearDown(self):
        """释放临时目录。"""

        self.tmp.cleanup()

    def test_upload_worker_alarm_result(self):
        """执行完整异步流程并校验结果输出字段。"""

        upload = self.DummyUpload("cam_A.jpg", b"image-bytes")
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
