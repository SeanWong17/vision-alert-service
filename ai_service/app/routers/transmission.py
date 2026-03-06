#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import cv2
import uuid
import json
import os.path as op
from datetime import datetime
from typing import Any, Dict

from fastapi import File, UploadFile, Form, Query
from fastapi.encoders import jsonable_encoder
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.routers import router
from app.utilities import exceptions
from app.utilities.logging import logger
from app.utilities.redis import ZHYRedis
from app.utilities.config import ZHYConfigParser
from app.biz.transmission.transmission import TransmissionBiz
from app.models.transmission import UploadRequestItem, RequestStatus, ResultConfirmItem
from app.models.data_analysis import DataAnalysisKey
from app.routers.people import run_people_sync_inference

redis = ZHYRedis()
config = ZHYConfigParser().config


def _normalize_tasks(tasks: Any) -> Dict[str, Any]:
    if isinstance(tasks, str):
        tasks = json.loads(tasks)

    if isinstance(tasks, list):
        tasks = {"ultrahigh_people_task": tasks}

    if not isinstance(tasks, dict):
        raise exceptions.TransmissionError(message='tasks format is invalid')

    people_tasks = tasks.get("ultrahigh_people_task")
    if not isinstance(people_tasks, list) or len(people_tasks) == 0:
        raise exceptions.TransmissionError(message='ultrahigh_people_task is required')

    for task in people_tasks:
        if not isinstance(task, dict):
            raise exceptions.TransmissionError(message='task item format is invalid')
        params = task.setdefault("params", {})
        coordinate = params.get("coordinate")
        if not isinstance(coordinate, list) or len(coordinate) < 4:
            params["coordinate"] = [-1, -1, -1, -1]

    return {"ultrahigh_people_task": people_tasks}


@router.post('/transmission/upload')
def upload(
    file: UploadFile = File(...),
    FileUpload=Form(...),
    tasks=Form(...)
):
    """
    people 异步分析上传接口
    """
    try:
        receive_at = datetime.now()
        file_upload_json = FileUpload if isinstance(FileUpload, dict) else json.loads(FileUpload)
        file_upload_json["fileuuid"] = str(uuid.uuid4()).replace("-", "")

        if not file_upload_json or not file_upload_json.get("filename") or not file_upload_json.get("sessionId"):
            return {'code': "-1", 'message': 'There is no enough parameter.'}

        try:
            file_upload = UploadRequestItem(**file_upload_json)
        except Exception:
            return {'code': "-1", 'message': 'FileUpload validation error!'}

        normalized_tasks = _normalize_tasks(tasks)

        file_uuid = file_upload.fileuuid
        file_name = file_upload.filename
        timestamp = file_upload.timestamp
        session_id = file_upload.sessionId

        biz = TransmissionBiz.instance()

        file_path = biz.upload(file_name, file, file_uuid)
        biz.save(
            file_uuid,
            timestamp,
            file_name,
            session_id,
            file_path,
            receive_at,
            json.dumps(normalized_tasks, ensure_ascii=False)
        )

        result = {'code': RequestStatus.SUCCESS, 'message': 'Success', 'sessionId': session_id}

        redis.lpush(DataAnalysisKey.upload_queue, '1')

        logger.info(
            f'======upload_record file_name: {file_name}, upload_time: {receive_at}, end_at: {datetime.now()} ============'
        )
    except Exception as e:
        result = {'code': "-1", 'message': str(e)}

    return result


@router.post('/analysis/danger')
def image_analysis_form(
    image: UploadFile = File(...),
    file_name: str = Form(...),
    tasks=Form(...),
):
    """
    people 同步分析接口
    """
    if image.content_type not in ['image/jpg', 'image/jpeg', 'image/png']:
        raise exceptions.ApiError(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            message='The file is not a image!'
        )

    try:
        biz = TransmissionBiz.instance()
        file_uuid = str(uuid.uuid4()).replace("-", "")

        file_path = biz.upload(file_name, image, file_uuid)

        normalized_tasks = _normalize_tasks(tasks)
        people_tasks = normalized_tasks["ultrahigh_people_task"]
        coordinates = people_tasks[0].get("params", {}).get("coordinate")

        result, img_res, raw_det_res = run_people_sync_inference(people_tasks, file_path, coordinates)

        result_path = op.join(config.filepath.result, 'ultrahigh_people_task')
        position = file_name.split('_')[0] if '_' in file_name else 'other'
        save_path = os.path.join(result_path, position)
        if not os.path.exists(save_path):
            os.makedirs(save_path)

        if len(raw_det_res) > 0:
            file_base, file_ext = os.path.splitext(file_name)
            file_name = f"{file_base}_ALARM{file_ext}"

        save_img_path = os.path.join(save_path, file_name)
        cv2.imwrite(save_img_path, img_res)

    except exceptions.RpcRuntimeError as e:
        raise exceptions.ApiError(message=e.message)

    return result


@router.get('/transmission/alarm_result')
def alarm_result(
    sessionId: str = Query(None)
):
    try:
        session_id = sessionId
        if not session_id:
            raise exceptions.TransmissionError(message='sessionId is None')

        biz = TransmissionBiz.instance()
        photos, more = biz.alarm_result(session_id)

        result = {
            'code': RequestStatus.SUCCESS,
            'message': 'Success',
            'hasMore': more,
            'photos': photos
        }
    except exceptions.TransmissionError as e:
        result = {'code': e.code, 'message': e.message}

    logger.info(f"-------get-----------------{result}")
    return jsonable_encoder(result)


@router.post('/transmission/result_confirm')
def result_confirm(
    spec: ResultConfirmItem
):
    try:
        photos = spec.PhotosRecvArgu
        session_id = spec.sessionId

        if not photos or not session_id:
            raise exceptions.TransmissionError(message='There is no parameter')

        biz = TransmissionBiz.instance()
        biz.result_confirm(photos, session_id)

        result = {'code': RequestStatus.SUCCESS, 'message': 'success'}
    except exceptions.TransmissionError as e:
        result = {'code': e.code, 'message': e.message}

    return jsonable_encoder(result)
