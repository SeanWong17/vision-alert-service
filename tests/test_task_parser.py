"""任务适配器测试。"""

import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import fastapi  # noqa: F401

        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class TaskAdapterTest(unittest.TestCase):
    """验证任务标准化规则。"""

    def test_legacy_task_list_is_normalized(self):
        """直接传 list 时应被识别为任务列表。"""

        from app.alerting.config import AlertSettings
        from app.alerting.task_adapter import normalize_tasks

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        tasks = normalize_tasks([{"id": 1, "params": {"limit": "2"}}], settings)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].params["limit"], 2)

    def test_invalid_coordinate_falls_back(self):
        """缺失坐标时应回退默认哨兵坐标。"""

        from app.alerting.config import AlertSettings
        from app.alerting.task_adapter import normalize_tasks

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        tasks = normalize_tasks({"tasks": [{"id": 2, "params": {}}]}, settings)
        rois = tasks[0].params["rois"]
        self.assertEqual(rois[0]["coordinate"], list(settings.roi_default))
        self.assertEqual(rois[0]["confThreshold"], 0.5)

    def test_invalid_shape_raises(self):
        """非法任务结构应抛出领域异常。"""

        from app.alerting.config import AlertSettings
        from app.alerting.task_adapter import normalize_tasks
        from app.common.errors import AlertingError

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        with self.assertRaises(AlertingError):
            normalize_tasks({"foo": []}, settings)

    def test_multi_roi_is_normalized(self):
        """多 ROI 规则应保留类别与阈值。"""

        from app.alerting.config import AlertSettings
        from app.alerting.task_adapter import normalize_tasks

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        tasks = normalize_tasks(
            {
                "tasks": [
                    {
                        "id": 3,
                        "params": {
                            "rois": [
                                {
                                    "roiId": "r1",
                                    "coordinate": [1, 2, 100, 120],
                                    "classes": ["person", "car"],
                                    "confThreshold": 0.7,
                                },
                                {"roiId": "r2", "coordinate": [-1, -1, -1, -1], "classes": [], "confThreshold": 0.5},
                            ]
                        },
                    }
                ]
            },
            settings,
        )
        rois = tasks[0].params["rois"]
        self.assertEqual(len(rois), 2)
        self.assertEqual(rois[0]["roiId"], "r1")
        self.assertEqual(rois[0]["classes"], ["person", "car"])
        self.assertEqual(rois[0]["confThreshold"], 0.7)

    def test_roi_coordinate_is_order_normalized(self):
        """反向坐标应在适配层归一化为左上到右下。"""

        from app.alerting.config import AlertSettings
        from app.alerting.task_adapter import normalize_tasks

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        tasks = normalize_tasks(
            {"tasks": [{"id": 9, "params": {"rois": [{"coordinate": [200, 120, 100, 20]}]}}]},
            settings,
        )
        roi = tasks[0].params["rois"][0]
        self.assertEqual(roi["coordinate"], [100, 20, 200, 120])

    def test_roi_threshold_is_clamped_to_0_1(self):
        """阈值应被限制在 [0,1]。"""

        from app.alerting.config import AlertSettings
        from app.alerting.task_adapter import normalize_tasks

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        tasks = normalize_tasks(
            {
                "tasks": [
                    {
                        "id": 10,
                        "params": {
                            "rois": [
                                {"roiId": "low", "coordinate": [1, 1, 2, 2], "confThreshold": -0.1},
                                {"roiId": "high", "coordinate": [1, 1, 2, 2], "confThreshold": 1.5},
                            ]
                        },
                    }
                ]
            },
            settings,
        )
        rois = tasks[0].params["rois"]
        self.assertEqual(rois[0]["confThreshold"], 0.0)
        self.assertEqual(rois[1]["confThreshold"], 1.0)


if __name__ == "__main__":
    unittest.main()
