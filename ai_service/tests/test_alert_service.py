"""告警服务单元测试（使用假流水线，不依赖真实模型）。"""

import io
import os
import tempfile
import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class AlertServiceTest(unittest.TestCase):
    """验证服务层同步/异步核心行为。"""

    def setUp(self):
        """构造隔离目录、假上传对象和假流水线。"""

        import numpy as np

        from app.alerting.pipeline import InferenceOutcome
        from app.alerting.schemas import DetectionBox, TaskResult

        class _DummyUpload:
            """模拟 UploadFile 的最小对象。"""

            def __init__(self, name: str, content: bytes, content_type: str = "image/jpeg"):
                """初始化上传对象。"""

                self.filename = name
                self.file = io.BytesIO(content)
                self.content_type = content_type

        class _FakePipeline:
            """模拟推理流水线，返回固定结果。"""

            def run(self, image_path, tasks):
                """返回固定推理产物。"""

                _ = (image_path, tasks)
                return InferenceOutcome(
                    detections=[
                        DetectionBox(
                            coordinate=[1, 2, 3, 4],
                            score=0.9,
                            tagName="enter_water",
                            overlapWater=0.2,
                            distanceToWater=0.0,
                        )
                    ],
                    water_color={"water_ratio": 0.5},
                    shoreline_points=[[1, 1], [2, 2]],
                    rendered_image=np.zeros((16, 16, 3), dtype=np.uint8),
                )

            def build_task_results(self, tasks, outcome):
                """返回固定任务结果。"""

                _ = outcome
                detail = [{"water_color_dict": {"water_ratio": 0.5}}]
                return [TaskResult(id=task.id, reserved="1", detail=detail) for task in tasks]

        from app.alerting.schemas import StoredResult
        from app.alerting.service import AlertService
        from app.alerting.store import AlertStore
        from app.core.settings import AlertSettings

        self.StoredResult = StoredResult
        self.DummyUpload = _DummyUpload

        self.tmp = tempfile.TemporaryDirectory()
        upload_root = os.path.join(self.tmp.name, "upload")
        result_root = os.path.join(self.tmp.name, "result")
        settings = AlertSettings(upload_root=upload_root, result_root=result_root, model_root="/tmp/m")

        self.store = AlertStore(settings)
        self.store.redis = None
        self.service = AlertService(settings, self.store, _FakePipeline())

    def tearDown(self):
        """清理临时目录。"""

        self.tmp.cleanup()

    def test_submit_async(self):
        """异步提交后队列长度应增加。"""

        image = self.DummyUpload("cam_1.jpg", b"123")
        file_upload = {"filename": "cam_1.jpg", "sessionId": "S1"}
        tasks = [{"id": 1, "params": {"limit": 1}}]

        result = self.service.submit_async(image, file_upload, tasks)
        self.assertEqual(result["code"], 0)
        self.assertEqual(self.store.queue_length(), 1)

    def test_analyze_sync(self):
        """同步分析应返回任务结果列表。"""

        image = self.DummyUpload("cam_2.jpg", b"456", content_type="image/jpeg")
        tasks = [{"id": 7, "params": {"limit": 0}}]

        result = self.service.analyze_sync(image, "cam_2.jpg", tasks)
        self.assertEqual(result[0]["reserved"], "1")

    def test_confirm_result_modern_payload(self):
        """现代确认载荷应正确删除结果记录。"""

        self.store.save_result(
            "S2",
            "img-1",
            self.StoredResult(imageId="img-1", filename="x.jpg", results=[{"reserved": "1"}]),
        )
        self.service.confirm_result({"sessionId": "S2", "imageIds": ["img-1"]})
        rows, _ = self.store.fetch_results("S2")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
