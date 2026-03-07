"""服务命名策略测试。"""

import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import fastapi  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class ServiceNamingTest(unittest.TestCase):
    """验证文件名分桶规则。"""

    def test_position_from_filename(self):
        """带下划线取前缀，不带下划线回退 other。"""

        from app.alerting.config import AlertSettings
        from app.alerting.pipeline import AlertPipeline
        from app.alerting.service import AlertService
        from app.alerting.store import AlertStore

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        svc = AlertService(settings, AlertStore(settings), AlertPipeline(settings))
        self.assertEqual(svc._position_from_filename("A100_20250101.jpg"), "A100")
        self.assertEqual(svc._position_from_filename("plain.jpg"), "other")


if __name__ == "__main__":
    unittest.main()
