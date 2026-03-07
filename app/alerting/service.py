"""告警应用服务：负责同步/异步流程编排。"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

import cv2
from fastapi import UploadFile
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.alerting.config import AlertSettings
from app.alerting.pipeline import AlertPipeline
from app.alerting.schemas import ConfirmPayload, QueueTask, StoredResult
from app.alerting.store import AlertStore
from app.alerting.task_adapter import normalize_tasks, parse_confirm_payload, parse_upload_envelope
from app.common.errors import AlertingError, ApiError
from app.common.logging import logger


class AlertService:
    """封装上传落盘、推理调用、结果存储与查询确认等业务操作。"""

    def __init__(self, settings: AlertSettings, store: AlertStore, pipeline: AlertPipeline):
        """初始化服务依赖。"""

        self.settings = settings
        self.store = store
        self.pipeline = pipeline

    @staticmethod
    def _position_from_filename(file_name: str) -> str:
        """从文件名提取点位前缀，用于目录分桶。"""

        return file_name.split("_")[0] if "_" in file_name else "other"

    def _save_upload_file(self, file_name: str, file_obj: UploadFile) -> str:
        """保存上传原图并返回本地路径。"""

        position = self._position_from_filename(file_name)
        directory = os.path.join(self.settings.upload_root, position)
        os.makedirs(directory, exist_ok=True)

        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as fh:
            fh.write(file_obj.file.read())
        return file_path

    def _save_result_image(self, file_name: str, image, has_alarm: bool) -> str:
        """保存标注结果图，告警图自动添加 _ALARM 后缀。"""

        position = self._position_from_filename(file_name)
        folder = os.path.join(self.settings.result_root, "alerts", position)
        os.makedirs(folder, exist_ok=True)

        stem, ext = os.path.splitext(file_name)
        save_name = f"{stem}_ALARM{ext}" if has_alarm else file_name
        save_path = os.path.join(folder, save_name)
        cv2.imwrite(save_path, image)
        return save_path

    def submit_async(self, upload: UploadFile, file_upload_raw: Any, tasks_raw: Any) -> Dict[str, Any]:
        """提交异步任务：接收入参、保存原图、写入队列。"""

        envelope = parse_upload_envelope(file_upload_raw)
        tasks = normalize_tasks(tasks_raw, self.settings)

        image_id = envelope.fileuuid or uuid.uuid4().hex
        file_path = self._save_upload_file(envelope.filename, upload)
        self.store.enqueue(
            QueueTask(
                image_id=image_id,
                session_id=envelope.sessionId,
                file_name=envelope.filename,
                file_path=file_path,
                tasks=tasks,
            )
        )

        logger.info("async upload accepted session_id=%s image_id=%s", envelope.sessionId, image_id)
        return {"code": 0, "message": "Success", "sessionId": envelope.sessionId, "imageId": image_id}

    def analyze_sync(self, image: UploadFile, file_name: str, tasks_raw: Any) -> List[Dict[str, Any]]:
        """同步推理：上传即分析并返回任务结果。"""

        if image.content_type not in {"image/jpg", "image/jpeg", "image/png"}:
            raise ApiError(status_code=HTTP_422_UNPROCESSABLE_ENTITY, message="The file is not an image")

        tasks = normalize_tasks(tasks_raw, self.settings)
        file_path = self._save_upload_file(file_name, image)
        outcome = self.pipeline.run(file_path, tasks)
        task_results = self.pipeline.build_task_results(tasks, outcome)
        has_alarm = any(item.reserved == "1" for item in task_results)

        self._save_result_image(file_name, outcome.rendered_image, has_alarm=has_alarm)
        return [item.dict() for item in task_results]

    def process_async_task(self, task: QueueTask) -> None:
        """消费单个异步任务并写回结果存储。"""

        pending = self.store.get_pending(task.session_id, task.image_id)
        if not pending:
            logger.warning("pending task missing session=%s image=%s", task.session_id, task.image_id)
            return

        outcome = self.pipeline.run(task.file_path, task.tasks)
        task_results = self.pipeline.build_task_results(task.tasks, outcome)
        results = [item.dict() for item in task_results]
        has_alarm = any(item.reserved == "1" for item in task_results)

        self._save_result_image(task.file_name, outcome.rendered_image, has_alarm=has_alarm)
        self.store.save_result(
            task.session_id,
            task.image_id,
            StoredResult(
                imageId=task.image_id,
                filename=task.file_name,
                results=results,
                timestamp=int(datetime.now().timestamp() * 1000),
            ),
        )

    def get_alarm_result(self, session_id: str) -> Dict[str, Any]:
        """按会话拉取一批异步结果（现代字段：items）。"""

        if not session_id:
            raise AlertingError(message="sessionId is required")

        rows, has_more = self.store.fetch_results(session_id)
        items = [dict(row) for row in rows]
        return {"code": 0, "message": "Success", "hasMore": has_more, "items": items}

    def confirm_result(self, payload: ConfirmPayload | Any) -> Dict[str, Any]:
        """确认已消费的结果项。"""

        session_id, image_ids = parse_confirm_payload(payload)
        if not session_id:
            raise AlertingError(message="sessionId is required")

        self.store.confirm_results(session_id, image_ids)
        return {"code": 0, "message": "Success", "confirmed": len(image_ids)}
