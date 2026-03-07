"""HTTP 路由异常语义测试。"""

import unittest
from unittest.mock import patch


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import fastapi  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class UploadRouteErrorTest(unittest.TestCase):
    """验证上传接口错误映射行为。"""

    def _new_client(self, service):
        """构造注入假 runtime 的测试客户端。"""

        from fastapi.testclient import TestClient
        from app.application import create_app

        class _Worker:
            def start(self):
                return None

            def stop(self):
                return None

        runtime = {"service": service, "worker": _Worker()}
        patcher = patch("app.application.get_runtime", return_value=runtime)
        patcher.start()
        self.addCleanup(patcher.stop)
        app = create_app()
        return TestClient(app)

    def test_upload_alerting_error_returns_400(self):
        """业务异常应映射为 400。"""

        from app.common.errors import AlertingError

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                raise AlertingError(message="bad upload payload")

        client = self._new_client(_Service())
        response = client.post(
            "/api/transmission/upload",
            files={"file": ("x.jpg", b"abc", "image/jpeg")},
            data={"FileUpload": "{}", "tasks": "[]"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], -1)
        self.assertEqual(response.json()["message"], "bad upload payload")
        self.assertEqual(response.json()["status"], False)

    def test_upload_unknown_error_returns_500(self):
        """未知异常应透传到全局 500 处理。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                raise RuntimeError("boom")

        client = self._new_client(_Service())
        response = client.post(
            "/api/transmission/upload",
            files={"file": ("x.jpg", b"abc", "image/jpeg")},
            data={"FileUpload": "{}", "tasks": "[]"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "internal server error")


if __name__ == "__main__":
    unittest.main()
