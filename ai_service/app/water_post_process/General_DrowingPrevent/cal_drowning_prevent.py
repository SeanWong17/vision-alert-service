#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : cal_drowning_prevent.py
@desc          : 防溺水推理
@dateTime      : 2023/08/31
@author        : ws
'''

import os
import cv2
import time

from concurrent.futures import ThreadPoolExecutor
from app.utilities.logging import logger
from app.utilities.config import ZHYConfigParser

from app.water_general_detection.predict_yolov5_detection import YOLOv5Detector                     # 检测模型
from app.water_post_process.general_post_process_det import DetectionGeneralPostProcessor           # 检测初步后处理
from app.water_general_segmentation.predict_mmsegmentation import MMImageSegmentor                  # 分割模型
from app.water_post_process.general_post_process_seg import SegmentationGeneralPostProcessor        # 分割初步后处理
from app.water_post_process.General_DrowingPrevent.drowning_prevent_utils import DrowingJudgement   # 防溺水后处理
from app.water_post_process.General_DrowingPrevent.water_color_pred import WaterColor               # 水体颜色识别
from app.water_post_process.General_DrowingPrevent.config_drowing_prevent import det_config, det_pp_config, seg_config, seg_pp_config, specific_pp_config, plot_config


config_ai = ZHYConfigParser().config
result_path = os.path.join(config_ai.filepath.result)

class DrowningPreventProcess():  # 防溺水计算类
    def __init__(self, det_model_path, mmseg_config_path, seg_model_path, det_config, det_pp_config, seg_config, seg_pp_config, specific_pp_config, plot_config):
        """
        初始化函数
        Attributes:
            det_model_path: 目标检测模型的路径
            seg_model_path: 图像分割模型的路径
            det_config: 目标检测模型的配置
            det_pp_config: 目标检测后处理的配置
            seg_config: 图像分割模型的配置
            seg_pp_config: 图像分割后处理的配置
            plot_config: 结果绘制后处理配置
        """
        self.polt_config = plot_config
        self.device = seg_config["device"]
        self.executor = ThreadPoolExecutor(max_workers=2)  # 并行推理线程池, max_workers与模型数量相同

        try:
            # 初始化目标检测器和其后处理
            self.image_detector = YOLOv5Detector(det_model_path, det_config)
            self.image_detector_general_post_process = DetectionGeneralPostProcessor(det_pp_config)
            logger.info("检测模型/后处理  加载完毕")

            # 初始化图像分割器和其后处理
            # self.image_segmentor = Yolov8Segmentor(seg_model_path, seg_config)
            self.image_segmentor = MMImageSegmentor(mmseg_config_path, seg_model_path, device=self.device)
            self.image_segmentor_general_post_process = SegmentationGeneralPostProcessor(seg_pp_config)
            logger.info("分割模型/后处理  加载完毕")

            # 防溺水后处理类
            self.drowing_prevent = DrowingJudgement(specific_pp_config)
            logger.info("防溺水类  加载完毕")

            # 水体颜色计算类
            self.water_color = WaterColor()

        except Exception as e:
            logger.error(f"防溺水模型加载遇到错误： {e}")

    def _det_inference(self, img):
        """
        执行目标检测推理
        Args:
            img: 输入图像
        Returns:
            det_res: 检测结果
            raw_det_res: 初始检测结果
        """
        raw_det_res = self.image_detector.predict_convert_cls(img)  # numpy格式的det, 类别为英文
        det_res = self.image_detector_general_post_process.process_results(raw_det_res)
        return det_res, raw_det_res

    def _seg_inference(self, img):
        """
        执行图像分割推理
        Args:
            img: 输入图像
        Returns:
            seg_res: 分割结果
        """
        raw_seg_res = self.image_segmentor.predict_seg(img) 
        seg_res = self.image_segmentor_general_post_process.process(raw_seg_res)
        return seg_res

    def _parallel_inference(self, img):
        """
        并行执行目标检测和图像分割推理
        Args:
            img_path: 图片(ndarray)
        Returns:
            det_res: 检测推理结果
            raw_det_res: 初始检测结果
            seg_res: 分割模型推理结果
        """
        # 异步提交任务
        segmentation_future = self.executor.submit(self._seg_inference, img)
        detection_future = self.executor.submit(self._det_inference, img)
        
        # 等待并获取结果
        det_res, raw_det_res = detection_future.result()
        seg_res = segmentation_future.result()

        return det_res, raw_det_res, seg_res


    def cal_drowing_judgement(self, img_path, coordinates):
        """
        防溺水推理, 接口方法
        Args:
            img_path: 输入图片路径
        Returns:
            bbox_result: 处理结果
        """
        img = cv2.imread(img_path)

        get_position_name = lambda image_path: os.path.splitext(os.path.basename(image_path))[0].split('_')[0]  # 提取文件名、去除扩展名，获取第一个下划线之前的部分
        position_name = get_position_name(img_path)
        logger.info(f"position_name: {position_name}  coordinates：{coordinates}")
        
        det_res, raw_det_res, seg_res = self._parallel_inference(img)                                    # 获取检测和分割结果
        # img = self.image_segmentor_general_post_process.draw_mask_result(img, seg_res)                    # 绘制掩膜

        bbox_result = self.drowing_prevent.predict(det_res, seg_res)                                        # 防溺水后处理结果
        logger.info(f"det_result_before_ROI: Num:{len(bbox_result)}, {bbox_result}")
        bbox_result = self.image_detector_general_post_process.filter_results_by_roi(bbox_result, position_name, coordinates)  # ROI过滤
        
        water_color_dict, num_water_pix, centers, bbox_mask, labels = self.water_color.cal_water_color(img, seg_res)  # 计算水体颜色
        img = self.water_color.draw_clusters(img, num_water_pix, centers, bbox_mask, labels)                        # 使用聚类后的颜色绘制掩膜
        img = self.image_segmentor_general_post_process.draw_dict_on_image(img, water_color_dict)              # 写入水体颜色
        
        shoreline_points = self.image_segmentor_general_post_process.cal_shoreline(seg_res)                    # 计算水岸线
        img_res = self.image_segmentor_general_post_process.draw_points(img, shoreline_points)                 # 绘制水岸线

        if coordinates[0] != -1 and len(coordinates) > 3:
            img_res = self.image_segmentor_general_post_process.draw_points(img_res, coordinates, color=(0, 0, 255))      # 绘制ROI
        
        img_res = self.image_detector_general_post_process.draw_box_result(img_res, raw_det_res, self.polt_config)     # 绘制初始检测框
        img_res = self.image_segmentor_general_post_process.draw_points(img_res, coordinates)                          # 绘制防护区域
        logger.info(f"det_result_drowing_prevent: Num:{len(bbox_result)}, {bbox_result}")

        logger.info(f"raw_det_res: {raw_det_res}")
        return bbox_result, img_res, water_color_dict, shoreline_points, raw_det_res


drowing_prevent_path = config_ai.filepath.water_general
latest = sorted([int(dir) for dir in os.listdir(drowing_prevent_path)])[-1]

det_model_dir = os.path.join(drowing_prevent_path, str(latest), 'det_model.pt')
seg_model_dir = os.path.join(drowing_prevent_path, str(latest), 'seg_model.pt')
mmseg_config_path = os.path.join(drowing_prevent_path, str(latest), 'mmseg_config.py')
logger.info(f"防溺水模型采用{latest}版本")

# 实例化类, 完成模型加载和后处理类实例化
drowing_prevent = DrowningPreventProcess(det_model_dir, mmseg_config_path, seg_model_dir, det_config, det_pp_config, seg_config, seg_pp_config, specific_pp_config, plot_config)
logger.info("防溺水模型启用")
