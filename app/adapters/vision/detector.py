"""检测器适配模块：封装 ultralytics YOLO 调用。"""

from __future__ import annotations

from typing import Any

import numpy as np
from ultralytics import YOLO

from app.common.logging import logger


class YoloDetector:
    """YOLO 检测器封装，输出统一检测框格式。"""

    def __init__(self, model_path: str, config: dict[str, Any]):
        """加载权重并读取推理参数。"""

        self.imgsz = config.get("imgsz", [1280, 1280])
        self.conf_thres = float(config.get("conf_thres", 0.5))
        self.iou_thres = float(config.get("iou_thres", 0.45))
        self.device = config.get("device", "0")
        self.model = YOLO(model_path)
        self.names = self.model.names

    def _predict(self, image: np.ndarray):
        """执行一次底层模型推理。"""

        return self.model.predict(
            source=image,
            imgsz=self.imgsz,
            conf=self.conf_thres,
            iou=self.iou_thres,
            device=self.device,
            verbose=False,
        )[0]

    def predict_boxes(self, image: np.ndarray) -> list[list[Any]]:
        """返回 `[x1, y1, x2, y2, conf, label]` 结构的检测列表。"""

        result = self._predict(image)
        if result.boxes is None:
            return []

        names = result.names if hasattr(result, "names") else self.names
        xyxy = result.boxes.xyxy.cpu().numpy()
        conf = result.boxes.conf.cpu().numpy()
        cls = result.boxes.cls.cpu().numpy()

        outputs: list[list[Any]] = []
        for i in range(len(xyxy)):
            x1, y1, x2, y2 = xyxy[i]
            cls_id = int(cls[i])
            label = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
            outputs.append([int(x1), int(y1), int(x2), int(y2), round(float(conf[i]), 4), label])

        logger.info("detector outputs=%d", len(outputs))
        return outputs
