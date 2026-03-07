"""告警流水线后处理测试。"""

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
                    alarmTag="near_water",
                    overlapWater=0.02,
                    distanceToWater=5.0,
                )
            ],
            water_color={"water_ratio": 0.3},
            shoreline_points=[[1, 1]],
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
                        "classes": ["near_water"],
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
        self.assertEqual(roi["alertClasses"], ["near_water"])
        self.assertEqual(roi["targets"][0]["tagName"], "person")
        self.assertEqual(roi["targets"][0]["alarmTag"], "near_water")

    def test_derive_alarm_tag_rules(self):
        """人员类别应按重叠率和距离映射业务标签。"""

        self.assertEqual(self.pipeline._derive_alarm_tag("person", overlap_ratio=0.2, distance=100), "enter_water")
        self.assertEqual(self.pipeline._derive_alarm_tag("person", overlap_ratio=0.01, distance=5), "near_water")
        self.assertEqual(self.pipeline._derive_alarm_tag("car", overlap_ratio=0.2, distance=1), "car")


if __name__ == "__main__":
    unittest.main()
