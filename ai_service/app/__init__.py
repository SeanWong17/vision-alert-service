#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : __init__.py
@desc          : 
@dateTime      : 2020/04/07 11:23:19
@author        : 5km
@contact       : 5km@smslit.cn
'''

import time
import traceback
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models.config import Config
from app.utilities.exceptions import ApiError
from app.utilities.logging import logger
from fastapi.responses import JSONResponse
from app import routers


def create_app(config: Config, sub_threads=None) -> FastAPI:

    app = FastAPI(
        # docs_url=None,
        # openapi_url=None,
        docs_url='/docs',
        # openapi_url='/openapi.json',
        # title=config.appinfo.title,
        # description=config.appinfo.description
    )

    app.include_router(
        routers.router,
        prefix='/api'
    )

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        logger.info(f"======= {request.method} {request.url} {response.status_code} ======")
        return response

    @app.exception_handler(StarletteHTTPException)
    async def api_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.error(f"======={request.method} {request.url} StarletteHTTPException error: {exc.status_code} {exc.detail} {exc.args} ======")

        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail, "status": False}
        )

    @app.exception_handler(RequestValidationError)
    async def api_exception_handler(request: Request, exc: RequestValidationError):
        logger.error(f"======={request.method} {request.url} RequestValidationError error: {exc.errors()} {exc.args} {exc.body}======")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({"message": exc.errors(), "status": False})
        )

    @app.exception_handler(Exception)
    async def all_exception_handler(request: Request, exc: Exception):
        """
        全局所有异常
        :param request:
        :param exc:
        :return:
        """
        logger.error(f"======= {request.method} {request.url} {status.HTTP_500_INTERNAL_SERVER_ERROR} \n{traceback.format_exc()}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder({"message": "服务器内部错误", "status": False})
        )

    @app.on_event("shutdown")
    def shutdown_event():
        if sub_threads is None:
            return
        for sub_thread in sub_threads:
            sub_thread.exit()

    return app
