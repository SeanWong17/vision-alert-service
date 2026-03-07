"""输入适配器：将外部请求参数转换为内部统一结构。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app.alerting.config import AlertSettings
from app.alerting.schemas import AlarmTask, ConfirmPayload, UploadEnvelope
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

        # 限制值统一为非负整数。
        try:
            params["limit"] = max(0, int(params.get("limit", settings.default_limit)))
        except Exception:
            params["limit"] = settings.default_limit

        # 坐标统一为 4 元整数，非法时回退默认哨兵值。
        roi = params.get("coordinate", list(settings.roi_default))
        if not isinstance(roi, list) or len(roi) < 4:
            params["coordinate"] = list(settings.roi_default)
        else:
            params["coordinate"] = [int(v) for v in roi[:4]]

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
