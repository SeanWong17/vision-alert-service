"""HTTP 路由控制器：仅做参数接收、调用服务并返回响应。"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from fastapi import File, Form, Query, UploadFile

from app.alerting import get_runtime
from app.alerting.schemas import ConfirmPayload
from app.http import router


async def _run_sync(func, *args):
    """将同步业务函数委派到默认线程池，避免阻塞事件循环。"""

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


@router.post("/transmission/upload")
async def upload(file: UploadFile = File(...), FileUpload: Any = Form(...), tasks: Any = Form(...)):
    """异步上传接口：返回 sessionId 与 imageId。"""

    service = get_runtime()["service"]
    return await _run_sync(service.submit_async, file, FileUpload, tasks)


@router.post("/analysis/danger")
async def analysis_danger(image: UploadFile = File(...), file_name: str = Form(...), tasks: Any = Form(...)):
    """同步分析接口：返回任务结果列表。"""

    service = get_runtime()["service"]
    return await _run_sync(service.analyze_sync, image, file_name, tasks)


@router.get("/transmission/alarm_result")
async def alarm_result(sessionId: str = Query(None)):
    """异步结果拉取接口：返回现代字段 items。"""

    service = get_runtime()["service"]
    return await _run_sync(service.get_alarm_result, sessionId)


@router.post("/transmission/result_confirm")
async def result_confirm(spec: ConfirmPayload):
    """异步结果确认接口：仅接受现代确认载荷。"""

    service = get_runtime()["service"]
    return await _run_sync(service.confirm_result, spec)
