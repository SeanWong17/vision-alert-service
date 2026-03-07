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
                    image_width=16,
                    image_height=16,
                )

            def build_task_results(self, tasks, outcome):
                """返回固定任务结果。"""

                _ = outcome
                detail = {"roiResults": [{"targetCount": 1}]}
                return [TaskResult(id=task.id, reserved="1", detail=detail) for task in tasks]

        from app.alerting.schemas import StoredResult
        from app.alerting.service import AlertService
        from app.alerting.store import AlertStore
        from app.common.settings import AlertSettings

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

    def test_submit_async_writes_file_in_chunks(self):
        """上传文件应按固定分块读取，避免一次性读入内存。"""

        class _ChunkReadable:
            def __init__(self, data: bytes):
                self._data = data
                self._offset = 0
                self.read_sizes = []

            def read(self, size: int = -1):
                self.read_sizes.append(size)
                if size is None or size < 0:
                    raise AssertionError("unexpected unbounded read")
                start = self._offset
                end = min(len(self._data), self._offset + size)
                self._offset = end
                return self._data[start:end]

        payload = b"x" * (2 * 1024 * 1024 + 123)
        stream = _ChunkReadable(payload)
        upload = self.DummyUpload("cam_3.jpg", b"")
        upload.file = stream

        result = self.service.submit_async(
            upload,
            {"filename": "cam_3.jpg", "sessionId": "S3"},
            [{"id": 1, "params": {"limit": 1}}],
        )
        self.assertEqual(result["code"], 0)

        saved_path = os.path.join(self.service.settings.upload_root, "cam", "cam_3.jpg")
        self.assertTrue(os.path.exists(saved_path))
        self.assertEqual(os.path.getsize(saved_path), len(payload))
        self.assertTrue(all(size == 1024 * 1024 for size in stream.read_sizes))

    def test_submit_async_sanitizes_filename(self):
        """异步上传应净化文件名，避免路径穿越。"""

        image = self.DummyUpload("origin.jpg", b"123")
        result = self.service.submit_async(
            image,
            {"filename": "../unsafe name?.jpg", "sessionId": "S4"},
            [{"id": 1, "params": {"limit": 1}}],
        )
        self.assertEqual(result["code"], 0)
        task = self.store.pop()
        self.assertIsNotNone(task)
        self.assertEqual(task.file_name, "unsafe_name_.jpg")
        self.assertTrue(task.file_path.endswith("/unsafe_name_.jpg"))

    def test_submit_async_rejects_non_image(self):
        """异步上传应拒绝非图片 MIME 类型。"""

        from app.common.errors import ApiError

        image = self.DummyUpload("x.txt", b"not-image", content_type="text/plain")
        with self.assertRaises(ApiError):
            self.service.submit_async(
                image,
                {"filename": "x.txt", "sessionId": "S5"},
                [{"id": 1, "params": {"limit": 1}}],
            )

    def test_submit_async_rejects_oversized_file(self):
        """异步上传超限时应抛错并删除落盘文件。"""

        from app.common.errors import AlertingError

        self.service.settings.upload_max_bytes = 16
        image = self.DummyUpload("cam_oversize.jpg", b"x" * 64, content_type="image/jpeg")

        with self.assertRaises(AlertingError):
            self.service.submit_async(
                image,
                {"filename": "cam_oversize.jpg", "sessionId": "S6"},
                [{"id": 1, "params": {"limit": 1}}],
            )

        saved_path = os.path.join(self.service.settings.upload_root, "cam", "cam_oversize.jpg")
        self.assertFalse(os.path.exists(saved_path))


if __name__ == "__main__":
    unittest.main()
