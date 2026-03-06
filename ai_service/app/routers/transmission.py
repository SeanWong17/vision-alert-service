#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from fastapi import File, UploadFile, Form, Query
from fastapi.encoders import jsonable_encoder

from app.models.transmission import ResultConfirmItem
from app.modules.transmission.service import TransmissionService
from app.utilities import exceptions
from app.utilities.logging import logger
from app.routers import router

service = TransmissionService.instance()


@router.post('/transmission/upload')
def upload(
    file: UploadFile = File(...),
    FileUpload=Form(...),
    tasks=Form(...),
):
    try:
        return service.handle_async_upload(file, FileUpload, tasks)
    except Exception as e:
        return {'code': "-1", 'message': str(e)}


@router.post('/analysis/danger')
def image_analysis_form(
    image: UploadFile = File(...),
    file_name: str = Form(...),
    tasks=Form(...),
):
    return service.handle_sync_analysis(image, file_name, tasks)


@router.get('/transmission/alarm_result')
def alarm_result(sessionId: str = Query(None)):
    try:
        result = service.get_alarm_result(sessionId)
    except exceptions.TransmissionError as e:
        result = {'code': e.code, 'message': e.message}

    logger.info(f"alarm_result response: {result}")
    return jsonable_encoder(result)


@router.post('/transmission/result_confirm')
def result_confirm(spec: ResultConfirmItem):
    try:
        result = service.confirm_result(spec)
    except exceptions.TransmissionError as e:
        result = {'code': e.code, 'message': e.message}

    return jsonable_encoder(result)
