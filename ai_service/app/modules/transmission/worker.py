#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import multiprocessing
from concurrent.futures import ThreadPoolExecutor

from app.modules.transmission.repository import TransmissionRepository
from app.modules.people.service import run_people_async_pipeline
from app.utilities.logging import logger


_workers = max(1, multiprocessing.cpu_count() // 2)
_thread_pool = ThreadPoolExecutor(max_workers=_workers, thread_name_prefix='transmission_process')


class TransmissionWorker:
    def __init__(self):
        self.repo = TransmissionRepository()

    def process_one(self, file_name, file_path, tasks, session_id, image_id):
        status_item = self.repo.get_pending_status(session_id, image_id)
        if not status_item:
            logger.warning(f"not found pending image_id={image_id} session_id={session_id}")
            return

        results = run_people_async_pipeline(file_name, tasks, file_path)
        self.repo.save_result(status_item, image_id, file_name, results)
        self.repo.mark_complete_count()

    def submit(self, queue_item):
        _thread_pool.submit(
            self.process_one,
            queue_item.get('file_name'),
            queue_item.get('file_path'),
            queue_item.get('tasks'),
            queue_item.get('session_id'),
            queue_item.get('image_id'),
        )
