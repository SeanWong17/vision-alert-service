"""HTTP 路由异常语义测试。"""

import unittest
from unittest.mock import patch


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import fastapi  # noqa: F401
        import httpx  # noqa: F401
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

            def is_running(self):
                return True

            def inflight_tasks(self):
                return 0

        class _Store:
            redis = None

            def queue_length(self):
                return 0

            def dead_letter_size(self):
                return 0

        runtime = {"service": service, "worker": _Worker(), "store": _Store()}
        patcher_app = patch("app.application.get_runtime", return_value=runtime)
        patcher_routes = patch("app.http.routes.get_runtime", return_value=runtime)
        patcher_app.start()
        patcher_routes.start()
        self.addCleanup(patcher_app.stop)
        self.addCleanup(patcher_routes.stop)
        app = create_app()
        return TestClient(app, raise_server_exceptions=False)

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
        self.assertTrue(response.json()["requestId"])
        self.assertEqual(response.headers.get("X-Request-ID"), response.json()["requestId"])

    def test_upload_unknown_error_is_recorded_in_metrics(self):
        """抛异常请求也应计入 HTTP 指标。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                raise RuntimeError("boom")

        client = self._new_client(_Service())
        _ = client.post(
            "/api/transmission/upload",
            files={"file": ("x.jpg", b"abc", "image/jpeg")},
            data={"FileUpload": "{}", "tasks": "[]"},
        )
        metrics = client.get("/metrics")
        self.assertEqual(metrics.status_code, 200)
        self.assertIn('path="/api/transmission/upload",status="500"', metrics.text)

    def test_request_id_is_echoed_for_success(self):
        """成功请求应透传 X-Request-ID。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0, "message": "Success", "sessionId": "S1", "imageId": "I1"}

        client = self._new_client(_Service())
        response = client.post(
            "/api/transmission/upload",
            files={"file": ("x.jpg", b"abc", "image/jpeg")},
            data={"FileUpload": "{\"filename\":\"x.jpg\",\"sessionId\":\"S1\"}", "tasks": "[{\"id\":1,\"params\":{\"limit\":1}}]"},
            headers={"X-Request-ID": "rid-123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), "rid-123")

    def test_healthz_and_readyz(self):
        """健康检查接口应返回可解析状态。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0}

        client = self._new_client(_Service())
        health = client.get("/healthz")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        ready = client.get("/readyz")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["status"], "ready")
        self.assertEqual(ready.json()["workerRunning"], True)
        self.assertEqual(ready.json()["storageMode"], "memory")

    def test_metrics_endpoint_exposes_core_metrics(self):
        """指标端点应导出 Prometheus 文本。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0}

        client = self._new_client(_Service())
        _ = client.get("/healthz")
        response = client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("http_requests_total", response.text)
        self.assertIn("http_request_duration_seconds_bucket", response.text)
        self.assertIn("alert_queue_length", response.text)


if __name__ == "__main__":
    unittest.main()
