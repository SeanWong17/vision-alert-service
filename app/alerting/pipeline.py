"""告警推理流水线：检测 + 分割 + 后处理 + 可视化。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from app.alerting.config import AlertSettings
from app.alerting.schemas import AlarmTask, DetectionBox, RoiRule, TaskResult
from app.common.logging import logger
from app.common.metrics import metrics

if TYPE_CHECKING:
    from app.adapters.vision.detector import YoloDetector
    from app.adapters.vision.segmentor import MmsegSegmentor


@dataclass
class InferenceOutcome:
    """单张图片推理的统一输出结构。"""

    detections: list[DetectionBox]
    rendered_image: np.ndarray
    image_width: int
    image_height: int
    timing_ms: dict[str, float] = field(default_factory=dict)


class AlertPipeline:
    """告警领域主流水线。"""

    SEGMENT_OVERLAY_COLOR = np.array((0, 165, 255), dtype=np.float32)
    SEGMENT_OVERLAY_ALPHA = 0.35

    def __init__(self, settings: AlertSettings):
        """初始化流水线配置和模型句柄。"""

        self.settings = settings
        self._detector: YoloDetector | None = None
        self._segmentor: MmsegSegmentor | None = None
        self._load_lock = Lock()

    def _model_paths(self) -> tuple[str, str, str]:
        """拼接检测/分割权重与配置文件路径。"""

        root = self.settings.model_root
        return (
            os.path.join(root, self.settings.det_model_name),
            os.path.join(root, self.settings.seg_config_name),
            os.path.join(root, self.settings.seg_model_name),
        )

    def warm_up(self) -> None:
        """在服务启动阶段预加载模型，消除首次请求的冷启动延迟。"""

        self._ensure_models()

    def _ensure_models(self) -> None:
        """懒加载模型，避免进程启动时阻塞。"""

        if self._detector and self._segmentor:
            return

        with self._load_lock:
            if self._detector and self._segmentor:
                return

            # 推理依赖按需加载，避免非推理路径导入重依赖。
            from app.adapters.vision.detector import YoloDetector
            from app.adapters.vision.segmentor import MmsegSegmentor

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
                target_class_ids=self.settings.segmentor_target_class_ids,
            )
            logger.info("models loaded from %s", self.settings.model_root)

    @staticmethod
    def _distance_to_segment_map(mask: np.ndarray) -> np.ndarray:
        """计算每个像素到最近分割区域边界的距离图。"""

        return cv2.distanceTransform((mask == 0).astype(np.uint8), cv2.DIST_L2, 3)

    def _uses_segment_postprocess(self, label: str) -> bool:
        """判断检测类别是否启用分割后处理。"""

        configured = {name.strip().lower() for name in self.settings.segment_postprocess_class_names}
        return (label or "").strip().lower() in configured

    def _derive_alarm_tag(self, tag_name: str, overlap_ratio: float, distance: float) -> str:
        """根据后处理规则生成告警标签。"""

        if self._uses_segment_postprocess(tag_name):
            if overlap_ratio > 0.0:
                if overlap_ratio >= self.settings.in_segment_overlap_ratio:
                    return "enter_segment"
                return "near_segment"
            if distance <= self.settings.near_segment_distance_px:
                return "near_segment"
        return tag_name

    def _to_detection_boxes(self, raw_det: list[list[Any]], seg_mask: np.ndarray) -> list[DetectionBox]:
        """将原始检测结果映射为带分割区域关系特征的检测框。"""

        seg_mask = seg_mask[:, :, 0] if seg_mask.ndim == 3 else seg_mask
        seg_mask = (seg_mask > 0).astype(np.uint8)
        dist_map = self._distance_to_segment_map(seg_mask)
        height, width = seg_mask.shape[:2]

        boxes: list[DetectionBox] = []
        for x1, y1, x2, y2, score, label in raw_det:
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(width, int(x2)), min(height, int(y2))
            if x2 <= x1 or y2 <= y1:
                continue

            crop = seg_mask[y1:y2, x1:x2]
            overlap = float(np.sum(crop > 0))
            area = float((x2 - x1) * (y2 - y1))
            overlap_ratio = overlap / area if area else 0.0

            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            distance = float(dist_map[min(center_y, height - 1), min(center_x, width - 1)])

            tag_name = str(label)
            boxes.append(
                DetectionBox(
                    coordinate=[x1, y1, x2, y2],
                    score=float(score),
                    tagName=tag_name,
                    alarmTag=self._derive_alarm_tag(tag_name, overlap_ratio, distance),
                    overlapSegment=round(overlap_ratio, 4),
                    distanceToSegment=round(distance, 2),
                )
            )
        return boxes

    @staticmethod
    def _is_full_image_roi(roi: list[int]) -> bool:
        """判断是否为全图 ROI 哨兵值。"""

        return len(roi) >= 4 and roi[0] == -1 and roi[1] == -1 and roi[2] == -1 and roi[3] == -1

    @staticmethod
    def _normalize_roi_to_image(roi: list[int], image_width: int, image_height: int) -> list[int]:
        """将 ROI 归一化到图像边界范围内。"""

        if len(roi) < 4:
            return [0, 0, image_width, image_height]

        if roi == [-1, -1, -1, -1]:
            return [0, 0, image_width, image_height]

        x1, y1, x2, y2 = roi[:4]
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        x1 = max(0, min(image_width, x1))
        x2 = max(0, min(image_width, x2))
        y1 = max(0, min(image_height, y1))
        y2 = max(0, min(image_height, y2))
        return [x1, y1, x2, y2]

    @staticmethod
    def _bbox_intersects_roi(bbox: list[int], roi: list[int]) -> bool:
        """判断检测框与 ROI 是否相交。"""

        x1, y1, x2, y2 = bbox
        rx1, ry1, rx2, ry2 = roi
        ix1, iy1 = max(x1, rx1), max(y1, ry1)
        ix2, iy2 = min(x2, rx2), min(y2, ry2)
        return max(0, ix2 - ix1) * max(0, iy2 - iy1) > 0

    def _filter_targets_for_roi(
        self,
        detections: list[DetectionBox],
        roi_rule: RoiRule,
        image_width: int,
        image_height: int,
    ) -> list[dict[str, Any]]:
        """按 ROI、类别、阈值筛选告警目标。"""

        roi = self._normalize_roi_to_image(list(roi_rule.coordinate), image_width, image_height)

        class_set = {c.lower() for c in roi_rule.classes if c}
        targets: list[dict[str, Any]] = []
        for det in detections:
            if det.score < roi_rule.confThreshold:
                continue
            if class_set and det.alarmTag.lower() not in class_set and det.tagName.lower() not in class_set:
                continue
            if not self._bbox_intersects_roi(det.coordinate, roi):
                continue
            targets.append(det.model_dump())

        return targets

    def _draw_render(
        self,
        image: np.ndarray,
        seg_mask: np.ndarray,
        all_boxes: list[DetectionBox],
    ) -> np.ndarray:
        """绘制分割掩膜和检测框，输出标注图。"""

        canvas = image.copy()

        mask = seg_mask > 0
        if np.any(mask):
            canvas_float = canvas.astype(np.float32)
            canvas_float[mask] = (
                canvas_float[mask] * (1.0 - self.SEGMENT_OVERLAY_ALPHA)
                + self.SEGMENT_OVERLAY_COLOR * self.SEGMENT_OVERLAY_ALPHA
            )
            canvas = np.clip(canvas_float, 0, 255).astype(np.uint8)
            class_label = ",".join(str(v) for v in self.settings.segmentor_target_class_ids)
            cv2.putText(
                canvas,
                f"seg:{class_label}",
                (12, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                tuple(int(v) for v in self.SEGMENT_OVERLAY_COLOR),
                2,
                cv2.LINE_AA,
            )

        for det in all_boxes:
            x1, y1, x2, y2 = det.coordinate
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                canvas,
                f"{det.alarmTag}:{det.score:.2f}",
                (x1, max(16, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        return canvas

    @staticmethod
    def _timing_ms(t0: float, t1: float, t2: float, t3: float, t_start: float) -> dict[str, float]:
        """将推理各阶段耗时统一转换为毫秒。"""

        return {
            "detection": round((t1 - t0) * 1000, 2),
            "segmentation": round((t2 - t1) * 1000, 2),
            "postprocess": round((t3 - t2) * 1000, 2),
            "total": round((t3 - t_start) * 1000, 2),
        }

    def run(self, image_path: str, tasks: list[AlarmTask]) -> InferenceOutcome:
        """执行一次完整推理流程。"""

        t_start = time.monotonic()
        self._ensure_models()
        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"failed to read image: {image_path}")

        t0 = time.monotonic()
        raw_det = self._detector.predict_boxes(image)
        t1 = time.monotonic()
        metrics.observe_inference("detection", t1 - t0)

        seg_mask = self._segmentor.predict_mask(image)
        t2 = time.monotonic()
        metrics.observe_inference("segmentation", t2 - t1)

        detections = self._to_detection_boxes(raw_det, seg_mask)

        seg_mask_binary = (seg_mask > 0).astype(np.uint8)
        height, width = image.shape[:2]
        rendered = self._draw_render(image, seg_mask_binary, detections)
        t3 = time.monotonic()
        metrics.observe_inference("postprocess", t3 - t2)
        metrics.observe_inference("total", t3 - t_start)

        return InferenceOutcome(
            detections=detections,
            rendered_image=rendered,
            image_width=width,
            image_height=height,
            timing_ms=self._timing_ms(t0, t1, t2, t3, t_start),
        )

    def run_from_buffer(self, image_bytes: bytes, tasks: list[AlarmTask]) -> InferenceOutcome:
        """从内存字节流执行推理，避免写盘再读取的 I/O 往返。"""

        t_start = time.monotonic()
        self._ensure_models()
        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("failed to decode image from buffer")

        t0 = time.monotonic()
        raw_det = self._detector.predict_boxes(image)
        t1 = time.monotonic()
        metrics.observe_inference("detection", t1 - t0)

        seg_mask = self._segmentor.predict_mask(image)
        t2 = time.monotonic()
        metrics.observe_inference("segmentation", t2 - t1)

        detections = self._to_detection_boxes(raw_det, seg_mask)

        seg_mask_binary = (seg_mask > 0).astype(np.uint8)
        height, width = image.shape[:2]
        rendered = self._draw_render(image, seg_mask_binary, detections)
        t3 = time.monotonic()
        metrics.observe_inference("postprocess", t3 - t2)
        metrics.observe_inference("total", t3 - t_start)

        return InferenceOutcome(
            detections=detections,
            rendered_image=rendered,
            image_width=width,
            image_height=height,
            timing_ms=self._timing_ms(t0, t1, t2, t3, t_start),
        )

    def build_task_results(self, tasks: list[AlarmTask], outcome: InferenceOutcome) -> list[TaskResult]:
        """将推理结果映射为对外任务结果格式（含 ROI 维度告警详情）。"""

        results: list[TaskResult] = []
        for task in tasks:
            rois_raw = task.params.get("rois", [])
            roi_rules = [RoiRule(**item) for item in rois_raw] if isinstance(rois_raw, list) else []
            if not roi_rules:
                roi_rules = [RoiRule(coordinate=[-1, -1, -1, -1], classes=[], confThreshold=0.5)]

            roi_results: list[dict[str, Any]] = []
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
                        "coordinate": self._normalize_roi_to_image(
                            list(roi_rule.coordinate), outcome.image_width, outcome.image_height
                        ),
                        "classes": roi_rule.classes,
                        "confThreshold": roi_rule.confThreshold,
                        "targetCount": len(targets),
                        "alertClasses": sorted(list({t["alarmTag"] for t in targets})),
                        "targets": targets,
                    }
                )

            task_limit = int(task.params.get("limit", self.settings.default_limit))
            reserved = "1" if total_targets >= task_limit else "0"
            results.append(
                TaskResult(
                    id=task.id,
                    reserved=reserved,
                    detail={
                        "roiResults": roi_results,
                    },
                )
            )
        return results
