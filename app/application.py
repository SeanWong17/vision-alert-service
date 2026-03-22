"""Web 应用工厂模块，负责创建并配置 FastAPI 实例。"""

from __future__ import annotations

import time
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.alerting import get_runtime
from app.common.errors import AlertingError
from app.common.metrics import metrics
from app.http import router
from app.common.logging import logger


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """应用生命周期钩子：启动时拉起 worker，退出时安全关闭。"""

    runtime = get_runtime()
    # 在启动阶段预热模型，将模型加载延迟从首次请求移到服务器启动时。
    pipeline = runtime.get("pipeline")
    if pipeline is not None and hasattr(pipeline, "warm_up"):
        try:
            pipeline.warm_up()
        except Exception as exc:
            logger.warning("model warm-up skipped: %s", exc)
    runtime["worker"].start()
    try:
        yield
    finally:
        runtime["worker"].stop()


def create_app() -> FastAPI:
    """创建 FastAPI 对象并注册中间件、异常处理器与路由。"""

    app = FastAPI(docs_url="/docs", lifespan=app_lifespan)
    app.include_router(router, prefix="/api")

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """记录请求耗时并写入响应头。"""

        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        path = request.url.path

        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.time() - start
            metrics.observe_http(request.method, path, status.HTTP_500_INTERNAL_SERVER_ERROR, elapsed)
            logger.info(
                "%s %s %s request_id=%s elapsed=%.4fs",
                request.method,
                request.url,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id,
                elapsed,
            )
            raise

        elapsed = time.time() - start
        response.headers["X-Process-Time"] = str(elapsed)
        response.headers["X-Request-ID"] = request_id
        metrics.observe_http(request.method, path, response.status_code, elapsed)
        logger.info("%s %s %s request_id=%s elapsed=%.4fs", request.method, request.url, response.status_code, request_id, elapsed)
        return response

    @app.get("/healthz")
    async def healthz():
        """进程存活探针。"""

        return {"status": "ok", "timestamp": int(time.time() * 1000)}

    @app.get("/readyz")
    async def readyz():
        """服务就绪探针。"""

        runtime = get_runtime()
        worker = runtime.get("worker")
        store = runtime.get("store")

        worker_running = worker.is_running() if worker is not None and hasattr(worker, "is_running") else True
        inflight = worker.inflight_tasks() if worker is not None and hasattr(worker, "inflight_tasks") else 0
        redis_ok = True
        storage_mode = "memory"
        if store is not None and getattr(store, "redis", None):
            storage_mode = "redis"
            try:
                redis_ok = bool(store.redis.ping())
            except Exception:
                redis_ok = False

        queue_length = 0
        if store is not None and hasattr(store, "queue_length"):
            try:
                queue_length = int(store.queue_length())
            except Exception:
                queue_length = -1

        ready = worker_running and redis_ok
        body = {
            "status": "ready" if ready else "not_ready",
            "workerRunning": worker_running,
            "inflightTasks": inflight,
            "storageMode": storage_mode,
            "redisOk": redis_ok,
            "queueLength": queue_length,
            "timestamp": int(time.time() * 1000),
        }
        return JSONResponse(
            status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body,
        )

    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus 指标导出。"""

        runtime = get_runtime()
        store = runtime.get("store")
        worker = runtime.get("worker")
        queue_length = 0
        inflight_tasks = 0
        dead_letter_size = 0

        if store is not None and hasattr(store, "queue_length"):
            queue_length = int(store.queue_length())
        if store is not None and hasattr(store, "dead_letter_size"):
            dead_letter_size = int(store.dead_letter_size())
        if worker is not None and hasattr(worker, "inflight_tasks"):
            inflight_tasks = int(worker.inflight_tasks())

        body = metrics.render_prometheus(
            queue_length=queue_length,
            inflight_tasks=inflight_tasks,
            dead_letter_size=dead_letter_size,
        )
        return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理 HTTP 异常，统一返回格式。"""

        request_id = getattr(request.state, "request_id", "")
        logger.error("HTTPException %s %s request_id=%s: %s", request.method, request.url, request_id, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail, "status": False, "requestId": request_id},
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理参数校验错误，返回 422。"""

        request_id = getattr(request.state, "request_id", "")
        logger.error("ValidationError %s %s request_id=%s: %s", request.method, request.url, request_id, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({"message": exc.errors(), "status": False, "requestId": request_id}),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(AlertingError)
    async def alerting_exception_handler(request: Request, exc: AlertingError):
        """处理告警领域异常，统一映射为业务错误响应。"""

        request_id = getattr(request.state, "request_id", "")
        logger.error("AlertingError %s %s request_id=%s: %s", request.method, request.url, request_id, exc.message)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder({"code": exc.code, "message": exc.message, "status": False, "requestId": request_id}),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(Exception)
    async def unknown_exception_handler(request: Request, _exc: Exception):
        """兜底异常处理，避免堆栈直接暴露给调用方。"""

        request_id = getattr(request.state, "request_id", "")
        logger.error("Unhandled %s %s request_id=%s\n%s", request.method, request.url, request_id, traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder({"message": "internal server error", "status": False, "requestId": request_id}),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    return app
