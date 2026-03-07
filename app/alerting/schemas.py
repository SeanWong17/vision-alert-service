"""告警领域的数据模型定义。"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DetectionBox(BaseModel):
    """单个检测框及其水面关系特征。"""

    coordinate: List[int] = Field(default_factory=list)
    score: float = 0.0
    tagName: str = ""
    overlapWater: float = 0.0
    distanceToWater: float = 0.0


class RoiRule(BaseModel):
    """单个 ROI 的告警规则。"""

    roiId: str = ""
    coordinate: List[int] = Field(default_factory=lambda: [-1, -1, -1, -1])
    classes: List[str] = Field(default_factory=list)
    confThreshold: float = 0.5


class AlarmTask(BaseModel):
    """标准化后的任务定义。"""

    id: Any = None
    params: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """与任务 ID 对齐的单项结果。"""

    id: Any = None
    reserved: str = "0"
    detail: Dict[str, Any] = Field(default_factory=dict)


class UploadEnvelope(BaseModel):
    """上传请求中的元数据（来自表单 FileUpload 字段）。"""

    filename: str
    sessionId: str
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    fileuuid: Optional[str] = None


class QueueTask(BaseModel):
    """异步队列中的任务载荷。"""

    image_id: str
    session_id: str
    file_name: str
    file_path: str
    tasks: List[AlarmTask] = Field(default_factory=list)


class StoredResult(BaseModel):
    """异步处理后持久化的结果。"""

    imageId: str
    filename: str
    results: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


class ConfirmPayload(BaseModel):
    """结果确认接口的现代请求体。"""

    sessionId: str = ""
    imageIds: List[str] = Field(default_factory=list)
