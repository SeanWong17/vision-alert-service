#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import time

from app.modules.transmission.repository import TransmissionRepository
from app.modules.transmission.worker import TransmissionWorker
from app.utilities.biz.service_mixins import Singletion
from app.utilities.config import config
from app.utilities.logging import logger


class TransmissionBackstage(Singletion):
    """Pending queue consumer."""

    def __init__(self):
        self.repo = TransmissionRepository()
        self.worker = TransmissionWorker()

    def auto_analyze(self):
        logger.info('start transmission worker loop')
        while True:
            try:
                time.sleep(config.ai.thread_sleep)
                if self.repo.pending_queue_length() <= 0:
                    continue

                queue_item = self.repo.pop_pending_queue()
                if not queue_item:
                    continue

                self.worker.submit(queue_item)
            except Exception as e:
                logger.exception(e)
