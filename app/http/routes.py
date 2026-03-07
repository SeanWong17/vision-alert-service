"""HTTP 路由控制器：仅做参数接收、调用服务并返回响应。"""

from __future__ import annotations

from typing import Any

from fastapi import File, Form, Query, UploadFile
from fastapi.encoders import jsonable_encoder

from app.alerting import get_runtime
from app.alerting.schemas import ConfirmPayload
from app.http import router
from app.common.errors import AlertingError
from app.common.logging import logger


@router.post("/transmission/upload")
async def upload(file: UploadFile = File(...), FileUpload: Any = Form(...), tasks: Any = Form(...)):
    """异步上传接口：返回 sessionId 与 imageId。"""

    service = get_runtime()["service"]
    try:
        return service.submit_async(file, FileUpload, tasks)
    except Exception as exc:
        logger.exception("upload failed: %s", exc)
        return {"code": -1, "message": str(exc)}


@router.post("/analysis/danger")
async def analysis_danger(image: UploadFile = File(...), file_name: str = Form(...), tasks: Any = Form(...)):
    """同步分析接口：返回任务结果列表。"""

    service = get_runtime()["service"]
    return service.analyze_sync(image, file_name, tasks)


@router.get("/transmission/alarm_result")
async def alarm_result(sessionId: str = Query(None)):
    """异步结果拉取接口：返回现代字段 items。"""

    service = get_runtime()["service"]
    try:
        result = service.get_alarm_result(sessionId)
    except AlertingError as exc:
        result = {"code": exc.code, "message": exc.message}

    logger.info("alarm_result response: %s", result)
    return jsonable_encoder(result)


@router.post("/transmission/result_confirm")
async def result_confirm(spec: ConfirmPayload):
    """异步结果确认接口：仅接受现代确认载荷。"""

    service = get_runtime()["service"]
    try:
        result = service.confirm_result(spec)
    except AlertingError as exc:
        result = {"code": exc.code, "message": exc.message}
    return jsonable_encoder(result)
