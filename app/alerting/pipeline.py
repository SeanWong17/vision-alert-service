"""告警推理流水线：检测 + 分割 + 后处理 + 可视化。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from app.alerting.config import AlertSettings
from app.alerting.schemas import AlarmTask, DetectionBox, RoiRule, TaskResult
from app.common.logging import logger
from app.adapters.vision.detector import YoloDetector
from app.adapters.vision.segmentor import MmsegSegmentor


@dataclass
class InferenceOutcome:
    """单张图片推理的统一输出结构。"""

    detections: List[DetectionBox]
    water_color: Dict[str, float]
    shoreline_points: List[List[int]]
    rendered_image: np.ndarray
    image_width: int
    image_height: int


class AlertPipeline:
    """告警领域主流水线。"""

    def __init__(self, settings: AlertSettings):
        """初始化流水线配置和模型句柄。"""

        self.settings = settings
        self._detector: YoloDetector | None = None
        self._segmentor: MmsegSegmentor | None = None
        self._load_lock = Lock()

    def _model_paths(self) -> Tuple[str, str, str]:
        """拼接检测/分割权重与配置文件路径。"""

        root = self.settings.model_root
        return (
            os.path.join(root, self.settings.det_model_name),
            os.path.join(root, self.settings.seg_config_name),
            os.path.join(root, self.settings.seg_model_name),
        )

    def _ensure_models(self) -> None:
        """懒加载模型，避免进程启动时阻塞。"""

        if self._detector and self._segmentor:
            return

        with self._load_lock:
            if self._detector and self._segmentor:
                return

            det_model_path, seg_config_path, seg_model_path = self._model_paths()
            for path in [det_model_path, seg_config_path, seg_model_path]:
                if not os.path.exists(path):
                    raise RuntimeError(f"missing model artifact: {path}")

            self._detector = YoloDetector(
                det_model_path,
                {
                    "imgsz": list(self.settings.detector_imgsz),
                    "conf_thres": self.settings.detector_conf,
                    "iou_thres": self.settings.detector_iou,
                    "device": self.settings.detector_device,
                },
            )
            self._segmentor = MmsegSegmentor(
                seg_config_path,
                seg_model_path,
                device=self.settings.segmentor_device,
            )
            logger.info("models loaded from %s", self.settings.model_root)

    @staticmethod
    def _build_water_color(image: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
        """计算水面区域颜色均值与面积占比。"""

        water_pixels = image[mask > 0]
        if water_pixels.size == 0:
            return {"water_ratio": 0.0}

        bgr_mean = np.mean(water_pixels, axis=0)
        return {
            "water_ratio": float(np.sum(mask > 0) / mask.size),
            "b_mean": round(float(bgr_mean[0]), 2),
            "g_mean": round(float(bgr_mean[1]), 2),
            "r_mean": round(float(bgr_mean[2]), 2),
        }

    @staticmethod
    def _extract_shoreline(mask: np.ndarray) -> List[List[int]]:
        """从水面掩膜提取近似岸线点。"""

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        shoreline: List[List[int]] = []
        for contour in contours:
            if len(contour) < 8:
                continue
            epsilon = 0.002 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            shoreline.extend([[int(p[0][0]), int(p[0][1])] for p in approx])
        return shoreline

    @staticmethod
    def _distance_to_water_map(mask: np.ndarray) -> np.ndarray:
        """计算每个像素到最近水面边界的距离图。"""

        return cv2.distanceTransform((mask == 0).astype(np.uint8), cv2.DIST_L2, 3)

    def _to_detection_boxes(self, raw_det: List[List[Any]], water_mask: np.ndarray) -> List[DetectionBox]:
        """将原始检测结果映射为带水面关系特征的检测框。"""

        water_mask = water_mask[:, :, 0] if water_mask.ndim == 3 else water_mask
        water_mask = (water_mask > 0).astype(np.uint8)
        dist_map = self._distance_to_water_map(water_mask)
        height, width = water_mask.shape[:2]

        boxes: List[DetectionBox] = []
        for x1, y1, x2, y2, score, label in raw_det:
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(width, int(x2)), min(height, int(y2))
            if x2 <= x1 or y2 <= y1:
                continue

            crop = water_mask[y1:y2, x1:x2]
            overlap = float(np.sum(crop > 0))
            area = float((x2 - x1) * (y2 - y1))
            overlap_ratio = overlap / area if area else 0.0

            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            distance = float(dist_map[min(center_y, height - 1), min(center_x, width - 1)])

            boxes.append(
                DetectionBox(
                    coordinate=[x1, y1, x2, y2],
                    score=float(score),
                    tagName=str(label),
                    overlapWater=round(overlap_ratio, 4),
                    distanceToWater=round(distance, 2),
                )
            )
        return boxes

    @staticmethod
    def _is_full_image_roi(roi: List[int]) -> bool:
        """判断是否为全图 ROI 哨兵值。"""

        return len(roi) >= 4 and roi[0] == -1 and roi[1] == -1 and roi[2] == -1 and roi[3] == -1

    @staticmethod
    def _bbox_intersects_roi(bbox: List[int], roi: List[int]) -> bool:
        """判断检测框与 ROI 是否相交。"""

        x1, y1, x2, y2 = bbox
        rx1, ry1, rx2, ry2 = roi
        ix1, iy1 = max(x1, rx1), max(y1, ry1)
        ix2, iy2 = min(x2, rx2), min(y2, ry2)
        return max(0, ix2 - ix1) * max(0, iy2 - iy1) > 0

    def _filter_targets_for_roi(
        self,
        detections: List[DetectionBox],
        roi_rule: RoiRule,
        image_width: int,
        image_height: int,
    ) -> List[Dict[str, Any]]:
        """按 ROI、类别、阈值筛选告警目标。"""

        roi = list(roi_rule.coordinate)
        if self._is_full_image_roi(roi):
            roi = [0, 0, image_width, image_height]

        class_set = {c.lower() for c in roi_rule.classes if c}
        targets: List[Dict[str, Any]] = []
        for det in detections:
            if det.score < roi_rule.confThreshold:
                continue
            if class_set and det.tagName.lower() not in class_set:
                continue
            if not self._bbox_intersects_roi(det.coordinate, roi):
                continue
            targets.append(det.dict())

        return targets

    def _draw_render(
        self,
        image: np.ndarray,
        water_mask: np.ndarray,
        all_boxes: List[DetectionBox],
        shoreline: List[List[int]],
    ) -> np.ndarray:
        """绘制掩膜、检测框和岸线，输出标注图。"""

        canvas = image.copy()

        overlay = np.zeros_like(canvas)
        overlay[water_mask > 0] = (255, 0, 0)
        canvas = cv2.addWeighted(canvas, 1.0, overlay, 0.25, 0)

        for det in all_boxes:
            x1, y1, x2, y2 = det.coordinate
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                canvas,
                f"{det.tagName}:{det.score:.2f}",
                (x1, max(16, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        for x, y in shoreline:
            cv2.circle(canvas, (x, y), 1, (0, 255, 255), -1)

        return canvas

    def run(self, image_path: str, tasks: List[AlarmTask]) -> InferenceOutcome:
        """执行一次完整推理流程。"""

        self._ensure_models()
        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"failed to read image: {image_path}")

        raw_det = self._detector.predict_boxes(image)
        water_mask = self._segmentor.predict_mask(image)

        detections = self._to_detection_boxes(raw_det, water_mask)

        water_mask_binary = (water_mask > 0).astype(np.uint8)
        shoreline = self._extract_shoreline(water_mask_binary)
        height, width = image.shape[:2]
        return InferenceOutcome(
            detections=detections,
            water_color=self._build_water_color(image, water_mask_binary),
            shoreline_points=shoreline,
            rendered_image=self._draw_render(image, water_mask_binary, detections, shoreline),
            image_width=width,
            image_height=height,
        )

    def build_task_results(self, tasks: List[AlarmTask], outcome: InferenceOutcome) -> List[TaskResult]:
        """将推理结果映射为对外任务结果格式（含 ROI 维度告警详情）。"""

        results: List[TaskResult] = []
        for task in tasks:
            rois_raw = task.params.get("rois", [])
            roi_rules = [RoiRule(**item) for item in rois_raw] if isinstance(rois_raw, list) else []
            if not roi_rules:
                roi_rules = [RoiRule(coordinate=[-1, -1, -1, -1], classes=[], confThreshold=0.5)]

            roi_results: List[Dict[str, Any]] = []
            total_targets = 0
            for roi_rule in roi_rules:
                targets = self._filter_targets_for_roi(
                    detections=outcome.detections,
                    roi_rule=roi_rule,
                    image_width=outcome.image_width,
                    image_height=outcome.image_height,
                )
                total_targets += len(targets)
                roi_results.append(
                    {
                        "roiId": roi_rule.roiId,
                        "coordinate": roi_rule.coordinate,
                        "classes": roi_rule.classes,
                        "confThreshold": roi_rule.confThreshold,
                        "targetCount": len(targets),
                        "alertClasses": sorted(list({t["tagName"] for t in targets})),
                        "targets": targets,
                    }
                )

            task_limit = int(task.params.get("limit", self.settings.default_limit))
            reserved = "1" if total_targets > task_limit else "0"
            results.append(
                TaskResult(
                    id=task.id,
                    reserved=reserved,
                    detail={
                        "roiResults": roi_results,
                        "waterColor": outcome.water_color,
                        "shorelinePoints": outcome.shoreline_points,
                    },
                )
            )
        return results
