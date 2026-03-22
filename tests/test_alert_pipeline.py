"""告警流水线后处理测试。"""

import numpy as np
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
class AlertPipelinePostprocessTest(unittest.TestCase):
    """验证 ROI 归一化、业务标签与阈值边界。"""

    def setUp(self):
        """创建流水线与通用推理结果。"""

        from app.alerting.config import AlertSettings
        from app.alerting.pipeline import AlertPipeline, InferenceOutcome
        from app.alerting.schemas import DetectionBox

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        self.pipeline = AlertPipeline(settings)
        self.InferenceOutcome = InferenceOutcome
        self.DetectionBox = DetectionBox

    def test_build_results_with_alarm_tag_and_limit_boundary(self):
        """类别筛选应同时支持 alarmTag；target==limit 时应告警。"""

        from app.alerting.schemas import AlarmTask

        outcome = self.InferenceOutcome(
            detections=[
                self.DetectionBox(
                    coordinate=[1, 1, 5, 5],
                    score=0.5,
                    tagName="person",
                    alarmTag="near_segment",
                    overlapSegment=0.02,
                    distanceToSegment=5.0,
                )
            ],
            rendered_image=None,
            image_width=16,
            image_height=16,
        )
        task = AlarmTask(
            id=101,
            params={
                "limit": 1,
                "rois": [
                    {
                        "roiId": "r1",
                        "coordinate": [20, 20, -5, -10],
                        "classes": ["near_segment"],
                        "confThreshold": 0.5,
                    }
                ],
            },
        )

        result = self.pipeline.build_task_results([task], outcome)[0]
        self.assertEqual(result.reserved, "1")
        roi = result.detail["roiResults"][0]
        self.assertEqual(roi["coordinate"], [0, 0, 16, 16])
        self.assertEqual(roi["targetCount"], 1)
        self.assertEqual(roi["alertClasses"], ["near_segment"])
        self.assertEqual(roi["targets"][0]["tagName"], "person")
        self.assertEqual(roi["targets"][0]["alarmTag"], "near_segment")

    def test_derive_alarm_tag_rules(self):
        """配置类目应按重叠率和距离映射业务标签。"""

        self.assertEqual(self.pipeline._derive_alarm_tag("person", overlap_ratio=0.25, distance=100), "enter_segment")
        self.assertEqual(self.pipeline._derive_alarm_tag("person", overlap_ratio=0.2, distance=100), "near_segment")
        self.assertEqual(self.pipeline._derive_alarm_tag("person", overlap_ratio=0.01, distance=5), "near_segment")
        self.assertEqual(self.pipeline._derive_alarm_tag("person", overlap_ratio=0.0, distance=5), "near_segment")
        self.assertEqual(self.pipeline._derive_alarm_tag("car", overlap_ratio=0.2, distance=1), "car")

    def test_derive_alarm_tag_only_uses_configured_classes(self):
        """仅配置中的类别会应用分割后处理。"""

        self.pipeline.settings.segment_postprocess_class_names = ("person",)

        self.assertEqual(self.pipeline._derive_alarm_tag("person", overlap_ratio=0.9, distance=5), "enter_segment")
        self.assertEqual(self.pipeline._derive_alarm_tag("adult", overlap_ratio=0.9, distance=5), "adult")

    def test_draw_render_applies_segment_overlay_to_masked_pixels(self):
        """结果图应对目标分割类掩膜区域绘制半透明叠色。"""

        image = np.full((32, 32, 3), 100, dtype=np.uint8)
        seg_mask = np.zeros((32, 32), dtype=np.uint8)
        seg_mask[8:24, 8:24] = 1

        rendered = self.pipeline._draw_render(image, seg_mask, [])

        self.assertTrue(np.array_equal(rendered[0, 0], image[0, 0]))
        self.assertFalse(np.array_equal(rendered[12, 12], image[12, 12]))
        self.assertGreater(int(rendered[12, 12][2]), int(image[12, 12][2]))


if __name__ == "__main__":
    unittest.main()
