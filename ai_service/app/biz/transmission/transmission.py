#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import json
from datetime import datetime
from fastapi.encoders import jsonable_encoder

from app.utilities.biz.service_mixins import Singletion
from app.utilities.logging import logger
from app.utilities.config import ZHYConfigParser
from app.utilities.redis import ZHYRedis
from app.utilities import exceptions
from app.utilities.datetime_utils import utc_today_int
from app.models.transmission import ImageQueueName, StatusItem


class TransmissionBiz(Singletion):
    def __init__(self):
        self.config = ZHYConfigParser().config
        self.redis = ZHYRedis()
        self.time_limit_enable: bool = False
        self.deadline_time: int = 20991231

    def upload(self, file_name, file, file_uuid):
        if self.service_time_out_closed:
            raise exceptions.TransmissionError(message="Time Out Config Server Time")

        position = file_name.split('_')[0] if '_' in file_name else 'other'
        image_dir_path = os.path.join(self.config.filepath.upload, position)
        if not os.path.exists(image_dir_path):
            os.makedirs(image_dir_path)

        file_path = os.path.join(image_dir_path, file_name)
        contents = file.file.read()
        with open(file_path, 'wb') as fp:
            fp.write(contents)
        return file_path

    def save(self, file_uuid, timestamp, file_name, session_id, file_path, receive_at, tasks):
        item = StatusItem()
        item.file_uuid = file_uuid
        item.timestamp = timestamp
        item.filename = file_name
        item.image_id = file_uuid
        item.session_id = session_id
        item.path = file_path
        item.receive_at = receive_at
        item.tasks = tasks

        item_json = json.dumps(jsonable_encoder(item.dict()))
        queue_json = json.dumps({
            "session_id": session_id,
            "image_id": file_uuid,
            "file_path": file_path,
            "file_name": file_name,
            "tasks": tasks,
        })

        session_key = '_'.join([ImageQueueName.DEAL_PENDING, session_id])
        res = self.redis.hset(session_key, file_uuid, item_json)
        if res:
            dt = datetime.now().strftime('%y-%m-%d %H:%M:%S')
            logger.info(f'=====save image img_name: {file_name},\tupload_time: {dt}=====')

        self.redis.rpush(ImageQueueName.DEAL_PENDING_QUEUE, queue_json)
        logger.info(f'=========deal_pending_queue len：{self.redis.llen(ImageQueueName.DEAL_PENDING_QUEUE)}==========')

    def alarm_result(self, session_id):
        key = '_'.join([ImageQueueName.NOT_ACQUIRED, session_id])
        num = self.redis.hlen(key)

        photos = []
        more = num > 50

        images = self.redis.hgetall(key)
        count = 0
        for image_id in images:
            image_json = images.get(image_id)
            self.redis.hdel(key, image_id)
            image_json = image_json if isinstance(image_json, dict) else json.loads(image_json)
            image_json.pop("fileuuid", None)
            photos.append(image_json)
            count += 1
            if count >= 50:
                break
        return photos, more

    def result_confirm(self, image, session_id):
        key = '_'.join([ImageQueueName.NOT_ACQUIRED, session_id])
        image_ids = image.photoIds
        for image_id in image_ids:
            res = self.redis.hdel(key, image_id)
            if res:
                dt = datetime.now().strftime('%y-%m-%d %H:%M:%S')
                logger.info(f'=====result_confirm image_id: {image_id},\tverify_time: {dt}=====')

    @property
    def service_time_out_closed(self):
        now_time_int = utc_today_int()
        return self.time_limit_enable and now_time_int > self.deadline_time
