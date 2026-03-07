"""告警应用服务：负责同步/异步流程编排。"""

from __future__ import annotations

import os
import re
import time
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
from app.common.metrics import metrics


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

    @staticmethod
    def _sanitize_filename(file_name: str) -> str:
        """净化文件名，阻断路径穿越和非法字符。"""

        base = os.path.basename(str(file_name or "").strip())
        if not base or base in {".", ".."}:
            raise AlertingError(message="invalid filename")

        # 文件名仅允许白名单字符，其他字符统一替换。
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)
        if not safe or safe in {".", ".."}:
            raise AlertingError(message="invalid filename")
        return safe

    def _validate_upload_type(self, upload: UploadFile) -> None:
        """校验上传文件 MIME 类型。"""

        if upload.content_type not in self.settings.allowed_image_types:
            raise ApiError(status_code=HTTP_422_UNPROCESSABLE_ENTITY, message="The file is not an image")

    @staticmethod
    def _detect_image_kind(content_head: bytes) -> str:
        """基于文件头魔数识别图片类型。"""

        head = bytes(content_head or b"")
        if len(head) >= 3 and head[0:3] == b"\xff\xd8\xff":
            return "jpeg"
        if len(head) >= 8 and head[0:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        return ""

    def _validate_upload_magic(self, upload: UploadFile, content_head: bytes) -> None:
        """校验上传文件真实内容与声明类型是否匹配。"""

        kind = self._detect_image_kind(content_head)
        if not kind:
            raise ApiError(status_code=HTTP_422_UNPROCESSABLE_ENTITY, message="The file is not an image")

        # 仅允许落在配置白名单中的真实图片类型。
        kind_to_mimes = {
            "jpeg": {"image/jpeg", "image/jpg"},
            "png": {"image/png"},
        }
        allowed_mimes = {item.lower() for item in self.settings.allowed_image_types}
        allowed_kinds = {
            image_kind
            for image_kind, mimes in kind_to_mimes.items()
            if any(mime in allowed_mimes for mime in mimes)
        }
        if kind not in allowed_kinds:
            raise ApiError(status_code=HTTP_422_UNPROCESSABLE_ENTITY, message="The file is not an image")

    @staticmethod
    def _cleanup_older_than(root_dir: str, expire_ts: float) -> int:
        """删除目录下早于指定时间戳的文件，并清理空目录。"""

        removed = 0
        if not os.path.isdir(root_dir):
            return removed

        # bottom-up 遍历便于在删除文件后继续删除空目录。
        for current_root, dirs, files in os.walk(root_dir, topdown=False):
            for name in files:
                path = os.path.join(current_root, name)
                try:
                    if os.path.getmtime(path) < expire_ts:
                        os.remove(path)
                        removed += 1
                except Exception:
                    continue

            for name in dirs:
                directory = os.path.join(current_root, name)
                try:
                    if not os.listdir(directory):
                        os.rmdir(directory)
                except Exception:
                    continue
        return removed

    def cleanup_expired_images(self) -> int:
        """清理过期上传图和结果图，默认保留一个月。"""

        expire_ts = time.time() - float(self.settings.image_retention_days * 24 * 3600)
        removed_upload = self._cleanup_older_than(self.settings.upload_root, expire_ts)
        removed_result = self._cleanup_older_than(self.settings.result_root, expire_ts)
        removed_total = removed_upload + removed_result
        if removed_total:
            logger.info(
                "cleanup expired images removed=%d upload=%d result=%d retention_days=%d",
                removed_total,
                removed_upload,
                removed_result,
                self.settings.image_retention_days,
            )
        return removed_total

    def _save_upload_file(self, file_name: str, file_obj: UploadFile) -> str:
        """保存上传原图并返回本地路径。"""

        position = self._position_from_filename(file_name)
        directory = os.path.join(self.settings.upload_root, position)
        os.makedirs(directory, exist_ok=True)

        file_path = os.path.join(directory, file_name)
        total = 0
        try:
            first_chunk = file_obj.file.read(1024 * 1024)
            if not first_chunk:
                raise AlertingError(message="empty file")
            self._validate_upload_magic(file_obj, first_chunk)

            with open(file_path, "wb") as fh:
                total += len(first_chunk)
                if total > self.settings.upload_max_bytes:
                    raise AlertingError(message="file too large")
                fh.write(first_chunk)
                while True:
                    chunk = file_obj.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.settings.upload_max_bytes:
                        # 超限立即终止；异常处理会删除半写入文件。
                        raise AlertingError(message="file too large")
                    fh.write(chunk)
        except Exception:
            # 写入失败时清理半成品，避免磁盘遗留脏文件。
            if os.path.exists(file_path):
                os.remove(file_path)
            raise
        return file_path

    def _save_result_image(self, file_name: str, image, has_alarm: bool) -> str:
        """保存标注结果图，告警图自动添加 _ALARM 后缀。"""

        position = self._position_from_filename(file_name)
        folder = os.path.join(self.settings.result_root, "alerts", position)
        os.makedirs(folder, exist_ok=True)

        stem, ext = os.path.splitext(file_name)
        save_name = f"{stem}_ALARM{ext}" if has_alarm else file_name
        save_path = os.path.join(folder, save_name)
        if not cv2.imwrite(save_path, image):
            raise RuntimeError(f"failed to write result image: {save_path}")
        return save_path

    @staticmethod
    def _build_failure_results(task: QueueTask, error_message: str) -> List[Dict[str, Any]]:
        """构造异步失败时的结果载荷，避免调用方一直等待。"""

        rows: List[Dict[str, Any]] = []
        for item in task.tasks:
            rows.append(
                {
                    "id": item.id,
                    "reserved": "0",
                    "detail": {"error": str(error_message)},
                }
            )
        return rows

    def submit_async(self, upload: UploadFile, file_upload_raw: Any, tasks_raw: Any) -> Dict[str, Any]:
        """提交异步任务：接收入参、保存原图、写入队列。"""

        self._validate_upload_type(upload)
        envelope = parse_upload_envelope(file_upload_raw)
        safe_filename = self._sanitize_filename(envelope.filename)
        tasks = normalize_tasks(tasks_raw, self.settings)

        image_id = envelope.fileuuid or uuid.uuid4().hex
        file_path = self._save_upload_file(safe_filename, upload)
        self.store.enqueue(
            QueueTask(
                image_id=image_id,
                session_id=envelope.sessionId,
                file_name=safe_filename,
                file_path=file_path,
                tasks=tasks,
            )
        )

        logger.info("async upload accepted session_id=%s image_id=%s", envelope.sessionId, image_id)
        return {"code": 0, "message": "Success", "sessionId": envelope.sessionId, "imageId": image_id}

    def analyze_sync(self, image: UploadFile, file_name: str, tasks_raw: Any) -> List[Dict[str, Any]]:
        """同步推理：上传即分析并返回任务结果。"""

        self._validate_upload_type(image)
        safe_filename = self._sanitize_filename(file_name)

        tasks = normalize_tasks(tasks_raw, self.settings)
        file_path = self._save_upload_file(safe_filename, image)
        outcome = self.pipeline.run(file_path, tasks)
        task_results = self.pipeline.build_task_results(tasks, outcome)
        has_alarm = any(item.reserved == "1" for item in task_results)

        self._save_result_image(safe_filename, outcome.rendered_image, has_alarm=has_alarm)
        return [item.dict() for item in task_results]

    def process_async_task(self, task: QueueTask) -> None:
        """消费单个异步任务并写回结果存储。"""

        pending = self.store.get_pending(task.session_id, task.image_id)
        if not pending:
            logger.warning("pending task missing session=%s image=%s", task.session_id, task.image_id)
            return

        try:
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
            metrics.inc_async_task("success")
        except Exception as exc:
            logger.exception("async task failed session=%s image=%s: %s", task.session_id, task.image_id, exc)
            metrics.inc_async_task("failure")
            try:
                self.store.push_dead_letter(task, str(exc))
            except Exception:
                logger.exception("failed to write dead letter session=%s image=%s", task.session_id, task.image_id)
            try:
                self.store.save_result(
                    task.session_id,
                    task.image_id,
                    StoredResult(
                        imageId=task.image_id,
                        filename=task.file_name,
                        results=self._build_failure_results(task, str(exc)),
                        timestamp=int(datetime.now().timestamp() * 1000),
                    ),
                )
            except Exception:
                logger.exception(
                    "failed to persist async failure result session=%s image=%s",
                    task.session_id,
                    task.image_id,
                )
                self.store.discard_pending(task.session_id, task.image_id)

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
