#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

from fastapi.encoders import jsonable_encoder

from app.models.data_analysis import DataAnalysisKey
from app.models.transmission import AlarmResultimage, ImageQueueName, StatusItem
from app.utilities.logging import logger
from app.utilities.redis import ZHYRedis


class TransmissionRepository:
    def __init__(self):
        self.redis = ZHYRedis()

    def save_pending(self, file_uuid: str, timestamp: int, file_name: str, session_id: str, file_path: str, receive_at: datetime, tasks_json: str):
        item = StatusItem(
            file_uuid=file_uuid,
            timestamp=timestamp,
            filename=file_name,
            image_id=file_uuid,
            session_id=session_id,
            path=file_path,
            receive_at=receive_at,
            tasks=tasks_json,
        )

        item_json = json.dumps(jsonable_encoder(item.dict()))
        queue_json = json.dumps(
            {
                "session_id": session_id,
                "image_id": file_uuid,
                "file_path": file_path,
                "file_name": file_name,
                "tasks": tasks_json,
            },
            ensure_ascii=False,
        )

        pending_key = f"{ImageQueueName.DEAL_PENDING}_{session_id}"
        self.redis.hset(pending_key, file_uuid, item_json)
        self.redis.rpush(ImageQueueName.DEAL_PENDING_QUEUE, queue_json)
        logger.info(f"enqueue pending image_id={file_uuid} queue_len={self.redis.llen(ImageQueueName.DEAL_PENDING_QUEUE)}")

    def pop_pending_queue(self) -> Dict[str, Any] | None:
        queue_json = self.redis.lpop(ImageQueueName.DEAL_PENDING_QUEUE)
        if not queue_json:
            return None
        queue_dict = json.loads(queue_json)
        raw_tasks = queue_dict.get("tasks")
        queue_dict["tasks"] = json.loads(raw_tasks) if isinstance(raw_tasks, str) else raw_tasks
        return queue_dict

    def pending_queue_length(self) -> int:
        return self.redis.llen(ImageQueueName.DEAL_PENDING_QUEUE)

    def get_pending_status(self, session_id: str, image_id: str) -> StatusItem | None:
        pending_key = f"{ImageQueueName.DEAL_PENDING}_{session_id}"
        image_json = self.redis.hget(pending_key, image_id)
        if not image_json:
            return None
        return StatusItem(**json.loads(image_json))

    def save_result(self, status_item: StatusItem, image_id: str, file_name: str, results: List[Dict[str, Any]]):
        result_item = AlarmResultimage(fileuuid=image_id, filename=file_name, results=results)
        result_key = f"{ImageQueueName.NOT_ACQUIRED}_{status_item.session_id}"
        self.redis.hset(result_key, image_id, json.dumps(result_item.dict(), ensure_ascii=False))

    def get_alarm_result_batch(self, session_id: str, limit: int = 50) -> Tuple[List[Dict[str, Any]], bool]:
        result_key = f"{ImageQueueName.NOT_ACQUIRED}_{session_id}"
        total = self.redis.hlen(result_key)
        has_more = total > limit

        photos: List[Dict[str, Any]] = []
        image_map = self.redis.hgetall(result_key)
        count = 0
        for image_id, image_json in image_map.items():
            payload = image_json if isinstance(image_json, dict) else json.loads(image_json)
            payload.pop("fileuuid", None)
            photos.append(payload)
            self.redis.hdel(result_key, image_id)
            count += 1
            if count >= limit:
                break

        return photos, has_more

    def confirm_results(self, session_id: str, image_ids: List[str]):
        result_key = f"{ImageQueueName.NOT_ACQUIRED}_{session_id}"
        for image_id in image_ids:
            if self.redis.hdel(result_key, image_id):
                logger.info(f"result confirmed image_id={image_id}")

    def mark_upload_count(self):
        self.redis.lpush(DataAnalysisKey.upload_queue, "1")

    def mark_complete_count(self):
        self.redis.lpush(DataAnalysisKey.complete_queue, "1")
