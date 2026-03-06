#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json
import time
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

from app.routers.ai import analysis_water_all
from app.utilities.config import config
from app.utilities.logging import logger
from app.utilities.redis import ZHYRedis
from app.utilities.biz.service_mixins import Singletion
from app.models.transmission import AlarmResultimage, ImageQueueName, StatusItem
from app.models.data_analysis import DataAnalysisKey

workers = max(1, multiprocessing.cpu_count() // 2)
thread_pool = ThreadPoolExecutor(
    max_workers=workers,
    thread_name_prefix='transmission_process'
)


class TransmissionBackstage(Singletion):
    """输电图片处理后台。"""

    def __init__(self):
        self.redis = ZHYRedis()

    def deal_process(self, file_name, file_path, tasks, session_id, image_id):
        try:
            redis = self.redis
            logger.info(f'========子线程开始处理水利通道图片 image_id={image_id}, file_name={file_name}=====')
            key = '_'.join([ImageQueueName.DEAL_PENDING, session_id])
            image_json = redis.hget(key, image_id)
            if not image_json:
                logger.warning(f'========not found image_id={image_id} info=====')
                return

            image = StatusItem(**json.loads(image_json))
            results = analysis_water_all(file_name, tasks, file_path)

            item = AlarmResultimage()
            item.fileuuid = image_id
            item.results = results
            item.filename = file_name

            result_key = '_'.join([ImageQueueName.NOT_ACQUIRED, image.session_id])
            redis.hset(result_key, image_id, json.dumps(item.dict()))

            redis.lpush(DataAnalysisKey.complete_queue, '1')
        except Exception as e:
            logger.exception(e)

    def auto_analyze(self):
        redis = self.redis
        logger.info('======启动自动分析进程====')
        while True:
            try:
                time.sleep(config.ai.thread_sleep)

                if not redis.llen(ImageQueueName.DEAL_PENDING_QUEUE):
                    continue

                queue_json = redis.lpop(ImageQueueName.DEAL_PENDING_QUEUE)
                if not queue_json:
                    continue

                queue_dict = json.loads(queue_json)
                file_name = queue_dict.get('file_name')
                file_path = queue_dict.get('file_path')
                raw_tasks = queue_dict.get('tasks')
                tasks = json.loads(raw_tasks) if isinstance(raw_tasks, str) else raw_tasks
                session_id = queue_dict.get('session_id')
                image_id = queue_dict.get('image_id')

                thread_pool.submit(self.deal_process, file_name, file_path, tasks, session_id, image_id)
            except Exception as e:
                logger.info(f"出错了----------------{str(e)}")
                logger.exception(e)
