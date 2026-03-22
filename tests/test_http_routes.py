"""HTTP 路由异常语义测试。"""

from contextlib import asynccontextmanager
import json
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
class UploadRouteErrorTest(unittest.IsolatedAsyncioTestCase):
    """验证上传接口错误映射行为。"""

    def _build_request(self, app, path: str, method: str = "POST", request_id: str = "rid-123"):
        """构造最小 Request 对象，用于直接调用异常处理器。"""

        from starlette.requests import Request

        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "root_path": "",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
                "app": app,
            }
        )
        request.state.request_id = request_id
        return request

    @asynccontextmanager
    async def _new_client(self, service):
        """构造注入假 runtime 的异步测试客户端，避免 TestClient 死锁。"""

        import httpx

        from app.application import create_app
        from app.alerting import _get_service

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

        runtime = {"service": service, "worker": _Worker(), "store": _Store(), "pipeline": None}
        patcher_app = patch("app.application.get_runtime", return_value=runtime)
        patcher_app.start()
        self.addCleanup(patcher_app.stop)
        app = create_app()
        app.state.log_unhandled_tracebacks = False
        # 使用 FastAPI dependency_overrides 替代对路由模块的 patch
        app.dependency_overrides[_get_service] = lambda: service
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield app, client

    async def test_alerting_exception_handler_returns_400(self):
        """业务异常处理器应映射为 400。"""

        from app.common.errors import AlertingError

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0}

        async with self._new_client(_Service()) as (app, _client):
            request = self._build_request(app, "/api/transmission/upload")
            handler = app.exception_handlers[AlertingError]
            response = await handler(request, AlertingError(message="bad upload payload"))

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.body)
        self.assertEqual(payload["code"], -1)
        self.assertEqual(payload["message"], "bad upload payload")
        self.assertEqual(payload["status"], False)
        self.assertEqual(response.headers.get("X-Request-ID"), "rid-123")

    async def test_unknown_exception_handler_returns_500(self):
        """未知异常处理器应返回 500。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0}

        async with self._new_client(_Service()) as (app, _client):
            request = self._build_request(app, "/api/transmission/upload")
            handler = app.exception_handlers[Exception]
            response = await handler(request, RuntimeError("boom"))

        self.assertEqual(response.status_code, 500)
        payload = json.loads(response.body)
        self.assertEqual(payload["message"], "internal server error")
        self.assertEqual(payload["requestId"], "rid-123")
        self.assertEqual(response.headers.get("X-Request-ID"), "rid-123")

    async def test_request_id_is_echoed_for_success(self):
        """成功请求应透传 X-Request-ID。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0, "message": "Success", "sessionId": "S1", "imageId": "I1"}

        async with self._new_client(_Service()) as (_app, client):
            response = await client.get("/healthz", headers={"X-Request-ID": "rid-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), "rid-123")

    async def test_healthz_and_readyz(self):
        """健康检查接口应返回可解析状态。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0}

        async with self._new_client(_Service()) as (_app, client):
            health = await client.get("/healthz")
            ready = await client.get("/readyz")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["status"], "ready")
        self.assertEqual(ready.json()["workerRunning"], True)
        self.assertEqual(ready.json()["storageMode"], "memory")

    async def test_metrics_endpoint_exposes_core_metrics(self):
        """指标端点应导出 Prometheus 文本。"""

        class _Service:
            def submit_async(self, *_args, **_kwargs):
                return {"code": 0}

        async with self._new_client(_Service()) as (_app, client):
            _ = await client.get("/healthz")
            response = await client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("http_requests_total", response.text)
        self.assertIn("http_request_duration_seconds_bucket", response.text)
        self.assertIn("alert_queue_length", response.text)


if __name__ == "__main__":
    unittest.main()
