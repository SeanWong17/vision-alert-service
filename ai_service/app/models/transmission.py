#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import time
from enum import Enum
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class RequestStatus(int, Enum):
    SUCCESS = 0
    FAILED = -1


class ImageQueueName(str, Enum):
    DEAL_PENDING = "deal_pending"
    DEAL_PENDING_QUEUE = "deal_pending_queue"
    NOT_ACQUIRED = "not_acquired"


class UploadRequestItem(BaseModel):
    fileuuid: str = ""
    filename: str = ""
    timestamp: int = int(time.time() * 1000)
    sessionId: str = ""


class StatusItem(BaseModel):
    file_uuid: str = ""
    path: str = ""
    filename: str = ""
    timestamp: int = int(time.time() * 1000)
    session_id: str = ""
    image_id: str = ""
    receive_at: datetime = datetime.now()
    tasks: str = ""


class AlarmResultimage(BaseModel):
    filename: str = ""
    fileuuid: str = ""
    results: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: int = int(time.time() * 1000)
    analyzTime: int = int(time.time() * 1000)


class PhotosRecvArguItem(BaseModel):
    photoIds: List[str] = Field(default_factory=list)


class ResultConfirmItem(BaseModel):
    PhotosRecvArgu: PhotosRecvArguItem = Field(default_factory=PhotosRecvArguItem)
    sessionId: str = ""
