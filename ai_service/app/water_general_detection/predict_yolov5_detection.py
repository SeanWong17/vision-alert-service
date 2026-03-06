#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
YOLO detection inference adapter based on ultralytics.
"""

import numpy as np
from ultralytics import YOLO
from app.utilities.logging import logger


class YOLOv5Detector:
    def __init__(self, model_path, config):
        self.imgsz = config.get("imgsz", [1280, 1280])
        self.conf_thres = float(config.get("conf_thres", 0.5))
        self.iou_thres = float(config.get("iou_thres", 0.45))
        self.device_id = config.get("device_id", 0)

        # ultralytics supports YOLOv5/8/11 weights with a unified API.
        self.model = YOLO(model_path)
        self.names = self.model.names

    def _predict(self, im0):
        results = self.model.predict(
            source=im0,
            imgsz=self.imgsz,
            conf=self.conf_thres,
            iou=self.iou_thres,
            device=self.device_id,
            verbose=False,
        )
        return results[0]

    def predict(self, im0):
        """
        Keep compatibility with historical call sites.
        Returns a list containing one ndarray: [N,6] => xyxy, conf, cls
        """
        result = self._predict(im0)
        if result.boxes is None or result.boxes.xyxy is None:
            return []

        xyxy = result.boxes.xyxy.cpu().numpy()
        conf = result.boxes.conf.cpu().numpy().reshape(-1, 1)
        cls = result.boxes.cls.cpu().numpy().reshape(-1, 1)
        det = np.concatenate([xyxy, conf, cls], axis=1)
        return [det]

    def predict_numpy(self, im0):
        """
        Return numpy detection list with numeric class id:
        [[xmin, ymin, xmax, ymax, conf, cls_id], ...]
        """
        result = self._predict(im0)
        detect_res = []
        if result.boxes is None:
            return detect_res

        xyxy = result.boxes.xyxy.cpu().numpy()
        conf = result.boxes.conf.cpu().numpy()
        cls = result.boxes.cls.cpu().numpy()

        for i in range(len(xyxy)):
            xmin, ymin, xmax, ymax = xyxy[i]
            detect_res.append([
                int(xmin), int(ymin), int(xmax), int(ymax),
                round(float(conf[i]), 2),
                int(cls[i]),
            ])

        logger.info(f"det_result_ori: Num:{len(detect_res)}, {detect_res}")
        return detect_res

    def predict_convert_cls(self, im0):
        """
        Return numpy detection list with class name:
        [[xmin, ymin, xmax, ymax, conf, cls_name], ...]
        """
        result = self._predict(im0)
        detect_res = []
        if result.boxes is None:
            return detect_res

        names = result.names if hasattr(result, "names") else self.names
        xyxy = result.boxes.xyxy.cpu().numpy()
        conf = result.boxes.conf.cpu().numpy()
        cls = result.boxes.cls.cpu().numpy()

        for i in range(len(xyxy)):
            xmin, ymin, xmax, ymax = xyxy[i]
            cls_id = int(cls[i])
            label = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
            detect_res.append([
                int(xmin), int(ymin), int(xmax), int(ymax),
                round(float(conf[i]), 2),
                label,
            ])

        logger.info(f"det_result_ori: Num:{len(detect_res)}, {detect_res}")
        return detect_res

    def convert_cls(self, det):
        """
        Convert class id to class name for historical compatibility.
        """
        detect_res = []
        names = self.names
        for xmin, ymin, xmax, ymax, conf, cls in reversed(det):
            cls_id = int(cls)
            label = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
            detect_res.append([xmin, ymin, xmax, ymax, conf, label])
        return detect_res
