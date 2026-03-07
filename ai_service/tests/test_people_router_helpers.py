"""确认载荷适配器测试。"""

import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import fastapi  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class ConfirmAdapterTest(unittest.TestCase):
    """验证现代确认参数解析。"""

    def test_parse_confirm_payload_model(self):
        """Pydantic 模型输入应被正确解析。"""

        from app.alerting.schemas import ConfirmPayload
        from app.alerting.task_adapter import parse_confirm_payload

        payload = ConfirmPayload(sessionId="S2", imageIds=["a"])
        session_id, image_ids = parse_confirm_payload(payload)
        self.assertEqual(session_id, "S2")
        self.assertEqual(image_ids, ["a"])

    def test_parse_confirm_payload_dict(self):
        """dict 输入应按现代载荷规则解析。"""

        from app.alerting.task_adapter import parse_confirm_payload

        session_id, image_ids = parse_confirm_payload({"sessionId": "S3", "imageIds": ["x", "y"]})
        self.assertEqual(session_id, "S3")
        self.assertEqual(image_ids, ["x", "y"])


if __name__ == "__main__":
    unittest.main()
