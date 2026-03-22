"""输入适配器：将外部请求参数转换为内部统一结构。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app.alerting.config import AlertSettings
from app.alerting.schemas import AlarmTask, ConfirmPayload, RoiRule, UploadEnvelope
from app.common.errors import AlertingError


def _to_object(value: Any) -> Dict[str, Any]:
    """将 dict/json 字符串解析为对象，非法输入抛出领域异常。"""

    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AlertingError(message=f"invalid json payload: {exc}")
        if not isinstance(decoded, dict):
            raise AlertingError(message="payload json must be an object")
        return decoded
    raise AlertingError(message="payload must be a dict or json string")


def _normalize_coordinate(raw_coordinate: Any, roi_default: List[int]) -> List[int]:
    """归一化 ROI 坐标顺序；哨兵值使用 [-1,-1,-1,-1]。"""

    if not isinstance(raw_coordinate, list) or len(raw_coordinate) < 4:
        return list(roi_default)

    try:
        x1, y1, x2, y2 = [int(v) for v in raw_coordinate[:4]]
    except Exception:
        return list(roi_default)

    if [x1, y1, x2, y2] == [-1, -1, -1, -1]:
        return [-1, -1, -1, -1]

    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def _normalize_roi(raw_roi: Any, roi_default: List[int]) -> RoiRule:
    """将单个 ROI 规则归一化为标准结构。"""

    if not isinstance(raw_roi, dict):
        raise AlertingError(message="roi item must be an object")

    coordinate = _normalize_coordinate(raw_roi.get("coordinate", roi_default), roi_default)

    classes = raw_roi.get("classes", [])
    if not isinstance(classes, list):
        classes = []
    classes = [str(x) for x in classes]

    try:
        threshold = float(raw_roi.get("confThreshold", 0.5))
    except Exception:
        threshold = 0.5
    threshold = min(max(threshold, 0.0), 1.0)

    return RoiRule(
        roiId=str(raw_roi.get("roiId", "")),
        coordinate=coordinate,
        classes=classes,
        confThreshold=threshold,
    )


def parse_upload_envelope(file_upload: Any) -> UploadEnvelope:
    """解析上传元数据并校验必填字段。"""

    payload = _to_object(file_upload)
    if "filename" not in payload or "sessionId" not in payload:
        raise AlertingError(message="FileUpload requires filename and sessionId")
    return UploadEnvelope(**payload)


def normalize_tasks(raw_tasks: Any, settings: AlertSettings) -> List[AlarmTask]:
    """将任务参数兼容成统一列表并做默认值补齐。"""

    if isinstance(raw_tasks, str):
        try:
            raw_tasks = json.loads(raw_tasks)
        except json.JSONDecodeError as exc:
            raise AlertingError(message=f"tasks json decode error: {exc}")

    if isinstance(raw_tasks, list):
        candidates = raw_tasks
    elif isinstance(raw_tasks, dict):
        candidates = raw_tasks.get("tasks")
    else:
        candidates = None

    if not isinstance(candidates, list) or not candidates:
        raise AlertingError(message="tasks must include at least one task item")

    normalized: List[AlarmTask] = []
    for candidate in candidates:
        if isinstance(candidate, str):
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise AlertingError(message=f"task item json decode error: {exc}")

        if not isinstance(candidate, dict):
            raise AlertingError(message="task item must be an object")

        params = candidate.setdefault("params", {})
        if not isinstance(params, dict):
            raise AlertingError(message="task params must be an object")

        try:
            params["limit"] = max(0, int(params.get("limit", settings.default_limit)))
        except Exception:
            params["limit"] = settings.default_limit

        rois = params.get("rois")
        normalized_rois: List[RoiRule] = []
        if isinstance(rois, list) and rois:
            normalized_rois = [_normalize_roi(roi, list(settings.roi_default)) for roi in rois]
        else:
            # 无 ROI 时默认全图，类别为全部，阈值 0.5。
            normalized_rois = [RoiRule(coordinate=list(settings.roi_default), classes=[], confThreshold=0.5)]

        params["rois"] = [rule.model_dump() for rule in normalized_rois]
        normalized.append(AlarmTask(**candidate))

    return normalized


def parse_confirm_payload(payload: Any) -> Tuple[str, List[str]]:
    """解析现代确认载荷，返回会话 ID 与图片 ID 列表。"""

    if isinstance(payload, ConfirmPayload):
        return payload.sessionId, list(payload.imageIds)

    if isinstance(payload, dict):
        modern = ConfirmPayload(**payload)
        return modern.sessionId, list(modern.imageIds)

    raise AlertingError(message="invalid confirm payload")
