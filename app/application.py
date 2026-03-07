"""Web 应用工厂模块，负责创建并配置 FastAPI 实例。"""

from __future__ import annotations

import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.alerting import get_runtime
from app.http import router
from app.common.logging import logger


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """应用生命周期钩子：启动时拉起 worker，退出时安全关闭。"""

    runtime = get_runtime()
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

        start = time.time()
        response = await call_next(request)
        response.headers["X-Process-Time"] = str(time.time() - start)
        logger.info("%s %s %s", request.method, request.url, response.status_code)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理 HTTP 异常，统一返回格式。"""

        logger.error("HTTPException %s %s: %s", request.method, request.url, exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail, "status": False})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理参数校验错误，返回 422。"""

        logger.error("ValidationError %s %s: %s", request.method, request.url, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({"message": exc.errors(), "status": False}),
        )

    @app.exception_handler(Exception)
    async def unknown_exception_handler(request: Request, _exc: Exception):
        """兜底异常处理，避免堆栈直接暴露给调用方。"""

        logger.error("Unhandled %s %s\n%s", request.method, request.url, traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder({"message": "internal server error", "status": False}),
        )

    return app
