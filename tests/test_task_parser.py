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
        self.assertEqual(tasks[0].params["coordinate"], list(settings.roi_default))

    def test_invalid_shape_raises(self):
        """非法任务结构应抛出领域异常。"""

        from app.alerting.config import AlertSettings
        from app.alerting.task_adapter import normalize_tasks
        from app.common.errors import AlertingError

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        with self.assertRaises(AlertingError):
            normalize_tasks({"foo": []}, settings)


if __name__ == "__main__":
    unittest.main()
