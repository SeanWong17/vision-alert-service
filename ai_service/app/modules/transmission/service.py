#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

import cv2
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.models.transmission import RequestStatus, ResultConfirmItem, UploadRequestItem
from app.modules.transmission.repository import TransmissionRepository
from app.modules.transmission.naming import position_from_filename, result_image_name
from app.modules.transmission.task_parser import normalize_people_tasks
from app.modules.people.service import run_people_sync_inference
from app.utilities import exceptions
from app.utilities.biz.service_mixins import Singletion
from app.utilities.config import ZHYConfigParser
from app.utilities.datetime_utils import utc_today_int
from app.utilities.logging import logger


class TransmissionService(Singletion):
    def __init__(self):
        self.config = ZHYConfigParser().config
        self.repo = TransmissionRepository()
        self.time_limit_enable: bool = False
        self.deadline_time: int = 20991231

    @property
    def service_time_out_closed(self) -> bool:
        return self.time_limit_enable and utc_today_int() > self.deadline_time

    def _save_upload_file(self, file_name: str, upload_file) -> str:
        if self.service_time_out_closed:
            raise exceptions.TransmissionError(message="Time Out Config Server Time")

        position = file_name.split('_')[0] if '_' in file_name else 'other'
        image_dir_path = os.path.join(self.config.filepath.upload, position)
        os.makedirs(image_dir_path, exist_ok=True)

        file_path = os.path.join(image_dir_path, file_name)
        contents = upload_file.file.read()
        with open(file_path, 'wb') as fp:
            fp.write(contents)
        return file_path

    def handle_async_upload(self, upload_file, file_upload_raw: Any, tasks_raw: Any) -> Dict[str, Any]:
        receive_at = datetime.now()
        file_upload_json = file_upload_raw if isinstance(file_upload_raw, dict) else json.loads(file_upload_raw)
        file_upload_json["fileuuid"] = str(uuid.uuid4()).replace("-", "")

        if not file_upload_json or not file_upload_json.get("filename") or not file_upload_json.get("sessionId"):
            return {'code': "-1", 'message': 'There is no enough parameter.'}

        try:
            file_upload = UploadRequestItem(**file_upload_json)
        except Exception:
            return {'code': "-1", 'message': 'FileUpload validation error!'}

        normalized_tasks = normalize_people_tasks(tasks_raw)
        file_path = self._save_upload_file(file_upload.filename, upload_file)

        self.repo.save_pending(
            file_uuid=file_upload.fileuuid,
            timestamp=file_upload.timestamp,
            file_name=file_upload.filename,
            session_id=file_upload.sessionId,
            file_path=file_path,
            receive_at=receive_at,
            tasks_json=json.dumps(normalized_tasks, ensure_ascii=False),
        )
        self.repo.mark_upload_count()

        logger.info(f"upload accepted file_name={file_upload.filename} session_id={file_upload.sessionId}")
        return {'code': RequestStatus.SUCCESS, 'message': 'Success', 'sessionId': file_upload.sessionId}

    def handle_sync_analysis(self, image, file_name: str, tasks_raw: Any) -> List[Dict[str, Any]]:
        if image.content_type not in ['image/jpg', 'image/jpeg', 'image/png']:
            raise exceptions.ApiError(
                status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                message='The file is not a image!'
            )

        file_path = self._save_upload_file(file_name, image)
        normalized_tasks = normalize_people_tasks(tasks_raw)
        people_tasks = normalized_tasks["ultrahigh_people_task"]
        coordinates = people_tasks[0].get("params", {}).get("coordinate")

        result, result_image, raw_det_res = run_people_sync_inference(people_tasks, file_path, coordinates)

        result_path = os.path.join(self.config.filepath.result, 'ultrahigh_people_task')
        save_path = os.path.join(result_path, position_from_filename(file_name))
        os.makedirs(save_path, exist_ok=True)

        save_name = result_image_name(file_name, has_alarm=bool(raw_det_res))

        cv2.imwrite(os.path.join(save_path, save_name), result_image)
        return result

    def get_alarm_result(self, session_id: str) -> Dict[str, Any]:
        if not session_id:
            raise exceptions.TransmissionError(message='sessionId is None')

        photos, has_more = self.repo.get_alarm_result_batch(session_id)
        return {
            'code': RequestStatus.SUCCESS,
            'message': 'Success',
            'hasMore': has_more,
            'photos': photos,
        }

    def confirm_result(self, spec: ResultConfirmItem) -> Dict[str, Any]:
        photos = spec.PhotosRecvArgu
        session_id = spec.sessionId
        if not photos or not session_id:
            raise exceptions.TransmissionError(message='There is no parameter')

        self.repo.confirm_results(session_id, photos.photoIds)
        return {'code': RequestStatus.SUCCESS, 'message': 'success'}
