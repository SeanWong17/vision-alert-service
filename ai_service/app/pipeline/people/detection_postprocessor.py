#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : general_post_process_det.py
@desc          : 检测框通用后处理, 如类别过滤、分类别置信度过滤、最小面积过滤、按类别ROI过滤、类别合并、结果绘制等
@dateTime      : 2023/09/07
@author        : ws
'''
from datetime import datetime
from shapely.geometry import Polygon, box
from ultralytics.utils.plotting import Annotator, colors
from app.utilities.logging import logger
from app.utilities.config import ZHYConfigParser

config = ZHYConfigParser().config


class DetectionGeneralPostProcessor:

    def __init__(self, det_pp_config):

        # 配置文件
        self.config = det_pp_config

        # 类别合并配置字典, 例如 {0: [0, 1, 2, 3], 6: [4, 5, 6], 'cat': ['cat', 'kitten']}
        self.merge_config = det_pp_config.get('merge_config', {})
    
        # 置信度配置字典, 保留对应类别大于置信度的框
        self.conf_config = det_pp_config.get('conf_config', {})

        # 类别保留列表, 保留列表内的类别
        self.cls_config = det_pp_config.get('cls_config', [])

        # 面积过滤
        self.area_config = det_pp_config.get('area_config', {})

        # 计算夜间时间, 用于过滤夜间目标
        self.time_config = det_pp_config.get('time_config', {})

        # ROI过滤
        self.roi_congfig = det_pp_config.get('roi_config', {})


    def merge_classes(self, results, merge_config_dict):
        """
        合并部分类别.

        Args:
            results: 图像推理结果, 格式[[left, top, right, bottom, confidence, class], ...]
        Returns:
            merged_results: 合并类别后的检测结果, 格式与输入相同.
        """
        # 创建一个从原类别到新类别的映射字典
        class_mapping = {}
        for new_class, old_classes in merge_config_dict.items():
            for old_class in old_classes:
                class_mapping[old_class] = new_class

        # 遍历结果并更新类别
        merged_results = []
        for result in results:
            old_class = result[5]
            new_class = class_mapping.get(old_class, old_class)  # 如果没有需要合并的, 使用原来的类别
            merged_result = result[:5] + [new_class]  # 创建新的结果
            merged_results.append(merged_result)

        return merged_results


    def filter_results_by_conf(self, results, conf_config_dict):
        """
        根据配置字典的置信度过滤结果

        Args:
            results: 图像推理结果, 格式[[left,top,right,bottom,confidence,class], ...]
        Returns:
            final_results: 去除小于分类别设置置信度后的检测结果, 格式与输入相同.
        """
            
        final_results = [
            result for result in results if result[4] > conf_config_dict.get(result[5], 0)  # 不在字典中的类别与0比较置信度, 即保留
        ]
        return final_results


    def filter_results_by_class(self, results, cls_config_list):
        """
        根据类别列表过滤推理结果。

        Args:
            results (list): 图像推理结果, 格式[[left, top, right, bottom, confidence, class], ...]
        Returns:
            final_results (list): 仅包含允许类别的检测结果, 格式与输入相同.
        """
        
        # 过滤结果, 仅保留在类别列表中的检测结果
        final_results = [
            result for result in results if result[5] in cls_config_list
        ]
        
        return final_results


    def filter_results_by_area(self, results, area_config):
        """
        根据 类别-面积字典 过滤检测结果

        Args:
            results (list): 图像推理结果, 格式[[left, top, right, bottom, confidence, class], ...]
            area_config (dict): 包含 min_area_config 和 max_area_config 的字典
                                格式 {'min_area_config': {class1: min_area1, ...},
                                      'max_area_config': {class2: max_area2, ...}}
        Returns:
            final_results (list): 根据面积阈值过滤后的检测结果, 格式与输入相同.
        """
        min_area_config_dict = area_config.get('min_area_config', {})
        max_area_config_dict = area_config.get('max_area_config', {})

        final_results = []
        for result in results:
            left, top, right, bottom, _, detected_class = result
            box_area = (right - left) * (bottom - top)  # 计算检测框的面积

            # 获取该类别的最小和最大面积配置，如果不在字典中则分别返回0和一个很大的数
            min_area = min_area_config_dict.get(detected_class, 0)
            max_area = max_area_config_dict.get(detected_class, float('inf'))

            if min_area <= box_area <= max_area:
                final_results.append(result)

        return final_results


    def filter_results_by_time_conf(self, results, time_config):
        """
        根据时间和类别置信度过滤检测结果

        Args:
            results: 图像推理结果, 格式 [[left, top, right, bottom, confidence, class], ...]
            time_config (dict): 包含夜间时间范围和时间类别置信度配置

        Returns:
            final_results: 根据时间调整的置信度过滤后的检测结果, 格式与输入相同.
        """
        # 获取夜间时间范围和时间类别置信度配置
        night_range = time_config.get('night_range', [])
        time_conf_config = time_config.get('time_conf_config', {})

        # 判断当前时间是否在夜间时间范围内
        if night_range:
            start_time = datetime.strptime(night_range[0], '%H:%M').time()
            end_time = datetime.strptime(night_range[1], '%H:%M').time()
            now = datetime.now().time()

            # 处理跨天的情况
            is_night = start_time <= now < end_time if start_time < end_time else now >= start_time or now < end_time
        else:
            is_night = False

        # 如果当前为夜间，调用 filter_results_by_conf 方法并使用 time_conf_config
        if is_night:
            return self.filter_results_by_conf(results, time_conf_config)

        return results


    def filter_results_by_roi(self, results, position_name, roi_points):
        """
        根据多边形感兴趣区域(ROI)来过滤检测结果, 接口方法。

        Args:
            results (list): 图像推理结果, 格式[[left, top, right, bottom, confidence, class], ...]
            roi_points (list): 定义多边形区域的点列表, 格式为[(x1, y1), (x2, y2), ...]
            target_classes (list, optional): 指定需要过滤的类别列表，为空则过滤所有类别。
        Returns:
            final_results (list): 仅包含符合IOF阈值的检测结果, 格式与输入相同。
        """
        def _get_roi_by_image_name(position_name, roi_config):
            for key in roi_config.keys():
                if key in position_name:
                    return roi_config[key]
            return roi_config.get("Default", [])
        
        # 后处理按点位ROI区域过滤配置文件
        roi_config_position_dict = self.roi_congfig.get('roi_config_position', {})
        roi_iof_thres = self.roi_congfig.get('roi_iof_thres', 0)
        roi_classes = self.roi_congfig.get("roi_classes", [])

        # 如果没有传入ROI, 从配置文件中读取
        if roi_points and (roi_points[0] == -1 or roi_points[0] == [-1, -1]):
            roi_points = _get_roi_by_image_name(position_name, roi_config_position_dict)
            
            # 如果配置文件中也没有坐标点, 则不进行ROI过滤
            if len(roi_points) == 0:
                return results

        # 处理无ROI和非法ROI的情况
        if not roi_points or len(roi_points) < 3:
            logger.warning("Invalid Filter_ROI !")
            return results

        logger.info(f"Post-Process Filter_ROI: {roi_points}")
        roi_shape = Polygon(roi_points)  # ROI多边形区域
        final_results = []
        for result in results:
            left, top, right, bottom, confidence, detected_class = result
            detection_box = box(left, top, right, bottom)  # 检测框区域
            intersection_area = detection_box.intersection(roi_shape).area
            box_area = detection_box.area
            iof = intersection_area / box_area if box_area > 0 else 0
            
            if iof >= roi_iof_thres:
                # 空列表时对所有类别进行过滤 否则对列表内类别过滤
                if not roi_classes or detected_class in roi_classes:
                    final_results.append(result)

        return final_results


    def process_results(self, results):
        """
        对推理结果进行综合处理, 接口方法.

        Args:
            results: 图像推理结果, 格式[[left, top, right, bottom, confidence, class], ...]
        Returns:
            processed_results: 处理后的检测结果.
        """
        processed_results = results

        # 类别合并
        if self.merge_config:
            processed_results = self.merge_classes(processed_results, self.merge_config)

        # 根据置信度过滤
        if self.conf_config:
            processed_results = self.filter_results_by_conf(processed_results, self.conf_config)

        # 根据类别过滤
        if self.cls_config:
            processed_results = self.filter_results_by_class(processed_results, self.cls_config)

        # 根据面积过滤
        if self.area_config:
            processed_results = self.filter_results_by_area(processed_results, self.area_config)

        # 根据时间段的类别置信度过滤
        if self.time_config:
            processed_results = self.filter_results_by_time_conf(processed_results, self.time_config)

        logger.info(f"det_result_general_pp: Num:{len(processed_results)}, {processed_results}")
        return processed_results


    def draw_box_result(self, img, det, plot_config):
        """
        绘制检测结果, 接口方法.

        Args:
            det: 图像推理结果, 格式[[left, top, right, bottom, confidence, class], ...] 类别为字符串
            plot_config: 结果绘制配置文件
        Returns:
            boxed_img: 绘制了检测结果的图像.
        """
        using_conf = plot_config["using_conf"]
        using_chinese = plot_config["using_chinese"]
        res_name_dict = plot_config["res_name_dict"]
        line_width = plot_config["line_width"]
        
        name_list = list(res_name_dict.values()) if using_chinese else list(res_name_dict.keys())
        
        annotator_args = {
            "line_width": line_width,
            "pil": using_chinese,
            "font": r"simhei.ttf" if using_chinese else None,  # 中文字体包为simhei, 可自定义并上传
            "example": str(name_list)
        }

        label_format = "{name} {conf:.2f}" if using_conf else "{name}"
        annotator = Annotator(img, **annotator_args)
        
        for *xyxy, conf, cls in reversed(det):
            name = res_name_dict.get(cls, cls) if using_chinese else cls
            label = label_format.format(name=name, conf=conf)
            color_index = name_list.index(name)
            annotator.box_label(xyxy, label, color=colors(color_index, True))

        return annotator.result()

    # 仅用于沂源项目过滤漂浮物
    def filter_results_by_img_ratio(self, results, img, ratio=0.8, class_list=['float_vt']):
        """
        根据面积占全图比例过滤指定类别检测结果, 接口方法

        Args:
            results (list): 图像推理结果，格式为 [[left, top, right, bottom, confidence, class], ...]，
                            其中每个元素代表一个检测框的坐标、置信度和类别。
            img (numpy.ndarray): 被检测的图像，用于计算图像尺寸。
            ratio (float, optional): 面积阈值，用于决定何种大小的检测框被保留。默认值为 0.8。
            class_list (list, optional): 指定要过滤的类别列表。默认为 ['float_vt']。

        Returns:
            list: 过滤后的检测结果，格式与输入相同。
        """
        final_results = []
        img_shape = img.shape  # 获取图像尺寸
        for result in results:
            left, top, right, bottom, _, detected_class = result
            box_area = (right - left) * (bottom - top)  # 计算检测框的面积
            # 如果检测框属于指定类别且面积占图像的比例小于给定阈值，则保留
            if detected_class in class_list and box_area <= img_shape[0] * img_shape[1] * ratio:
                final_results.append(result)
        return final_results