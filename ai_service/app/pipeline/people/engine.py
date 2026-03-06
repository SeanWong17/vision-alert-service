#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import cv2
from concurrent.futures import ThreadPoolExecutor

from app.utilities.logging import logger
from app.utilities.config import ZHYConfigParser
from app.pipeline.people.detector import YOLOv5Detector
from app.pipeline.people.segmentor import MMImageSegmentor
from app.pipeline.people.detection_postprocessor import DetectionGeneralPostProcessor
from app.pipeline.people.segmentation_postprocessor import SegmentationGeneralPostProcessor
from app.pipeline.people.drowning_rules import DrowningJudgement
from app.pipeline.people.water_color import WaterColor
from app.pipeline.people.config import (
    det_config,
    det_pp_config,
    seg_config,
    seg_pp_config,
    specific_pp_config,
    plot_config,
)


class PeopleInferenceEngine:
    def __init__(self, det_model_path, mmseg_config_path, seg_model_path):
        self.plot_config = plot_config
        self.device = seg_config["device"]
        self.executor = ThreadPoolExecutor(max_workers=2)

        self.detector = YOLOv5Detector(det_model_path, det_config)
        self.detector_post = DetectionGeneralPostProcessor(det_pp_config)
        logger.info("people detector loaded")

        self.segmentor = MMImageSegmentor(mmseg_config_path, seg_model_path, device=self.device)
        self.segmentor_post = SegmentationGeneralPostProcessor(seg_pp_config)
        logger.info("people segmentor loaded")

        self.drowning_judge = DrowningJudgement(specific_pp_config)
        self.water_color = WaterColor()
        logger.info("people post-processors loaded")

    def _det_inference(self, image):
        raw_det = self.detector.predict_convert_cls(image)
        det_res = self.detector_post.process_results(raw_det)
        return det_res, raw_det

    def _seg_inference(self, image):
        raw_seg = self.segmentor.predict_seg(image)
        seg_res = self.segmentor_post.process(raw_seg)
        return seg_res

    def _parallel_inference(self, image):
        seg_future = self.executor.submit(self._seg_inference, image)
        det_future = self.executor.submit(self._det_inference, image)

        det_res, raw_det = det_future.result()
        seg_res = seg_future.result()
        return det_res, raw_det, seg_res

    def analyze_image(self, image_path, coordinates):
        image = cv2.imread(image_path)
        position_name = os.path.splitext(os.path.basename(image_path))[0].split("_")[0]
        logger.info(f"position_name: {position_name}, coordinates: {coordinates}")

        det_res, raw_det_res, seg_res = self._parallel_inference(image)

        bbox_result = self.drowning_judge.predict(det_res, seg_res)
        bbox_result = self.detector_post.filter_results_by_roi(bbox_result, position_name, coordinates)

        water_color_dict, num_water_pix, centers, bbox_mask, labels = self.water_color.cal_water_color(image, seg_res)
        image = self.water_color.draw_clusters(image, num_water_pix, centers, bbox_mask, labels)
        image = self.segmentor_post.draw_dict_on_image(image, water_color_dict)

        shoreline_points = self.segmentor_post.cal_shoreline(seg_res)
        result_image = self.segmentor_post.draw_points(image, shoreline_points)

        if coordinates and coordinates[0] != -1 and len(coordinates) > 3:
            result_image = self.segmentor_post.draw_points(result_image, coordinates, color=(0, 0, 255))

        result_image = self.detector_post.draw_box_result(result_image, raw_det_res, self.plot_config)
        result_image = self.segmentor_post.draw_points(result_image, coordinates)

        return bbox_result, result_image, water_color_dict, shoreline_points, raw_det_res


def _resolve_latest_model_files():
    config_ai = ZHYConfigParser().config
    people_model_path = config_ai.filepath.water_general
    latest = sorted([int(d) for d in os.listdir(people_model_path)])[-1]

    model_root = os.path.join(people_model_path, str(latest))
    det_model = os.path.join(model_root, "det_model.pt")
    seg_model = os.path.join(model_root, "seg_model.pt")
    mmseg_cfg = os.path.join(model_root, "mmseg_config.py")

    logger.info(f"people model version: {latest}")
    return det_model, mmseg_cfg, seg_model


def _build_engine():
    det_model, mmseg_cfg, seg_model = _resolve_latest_model_files()
    return PeopleInferenceEngine(det_model, mmseg_cfg, seg_model)


people_engine = _build_engine()
