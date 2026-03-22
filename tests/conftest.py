"""测试共享工具和固定装置：统一假对象避免各测试文件重复定义。"""

from __future__ import annotations

import io
import os
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def runtime_ready(*modules: str) -> bool:
    """检测运行时依赖是否齐全，支持按需指定模块列表。"""

    for mod in modules:
        try:
            __import__(mod)
        except Exception:
            return False
    return True


class DummyUpload:
    """模拟 FastAPI UploadFile 的最小对象。"""

    def __init__(self, name: str, content: bytes, content_type: str = "image/jpeg"):
        """初始化上传对象。"""

        self.filename = name
        self.file = io.BytesIO(content)
        self.content_type = content_type


def jpeg_bytes(payload_size: int = 32) -> bytes:
    """构造满足 JPEG 魔数的测试字节流。"""

    return b"\xff\xd8\xff" + (b"x" * max(0, payload_size - 3))


def make_fake_pipeline():
    """创建假推理流水线（不依赖真实模型）。"""

    import numpy as np

    from app.alerting.pipeline import InferenceOutcome
    from app.alerting.schemas import DetectionBox, TaskResult

    class FakePipeline:
        """模拟推理流水线，返回固定结果。"""

        def run(self, image_path, tasks):
            """返回固定推理产物。"""

            _ = (image_path, tasks)
            return InferenceOutcome(
                detections=[
                    DetectionBox(
                        coordinate=[1, 2, 3, 4],
                        score=0.9,
                        tagName="enter_segment",
                        overlapSegment=0.2,
                        distanceToSegment=0.0,
                    )
                ],
                rendered_image=np.zeros((16, 16, 3), dtype=np.uint8),
                image_width=16,
                image_height=16,
            )

        def build_task_results(self, tasks, outcome):
            """返回固定任务结果。"""

            _ = outcome
            detail = {"roiResults": [{"targetCount": 1}]}
            return [TaskResult(id=task.id, reserved="1", detail=detail) for task in tasks]

    return FakePipeline()


def make_test_service(tmp_dir: str | None = None):
    """创建用于测试的服务实例、存储和临时目录。"""

    from app.alerting.service import AlertService
    from app.alerting.store import AlertStore
    from app.common.settings import AlertSettings

    if tmp_dir is None:
        tmp = tempfile.TemporaryDirectory()
        tmp_dir = tmp.name
    else:
        tmp = None

    upload_root = os.path.join(tmp_dir, "upload")
    result_root = os.path.join(tmp_dir, "result")
    settings = AlertSettings(upload_root=upload_root, result_root=result_root, model_root="/tmp/m")

    store = AlertStore(settings)
    store.redis = None
    pipeline = make_fake_pipeline()
    service = AlertService(settings, store, pipeline)

    return service, store, settings, tmp


class FakeWorker:
    """模拟 AlertWorker 的最小实现。"""

    def start(self):
        return None

    def stop(self):
        return None

    def is_running(self):
        return True

    def inflight_tasks(self):
        return 0


class FakeStore:
    """模拟 AlertStore 的最小实现。"""

    redis = None

    def queue_length(self):
        return 0

    def dead_letter_size(self):
        return 0
