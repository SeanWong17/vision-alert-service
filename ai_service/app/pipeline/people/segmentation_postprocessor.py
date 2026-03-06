#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : general_post_process_seg.py
@desc          : 分割后掩膜通用后处理, 如形态学运算等
@dateTime      : 2023/08/31
@author        : ws
'''

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.utilities.logging import logger
from app.utilities.config import ZHYConfigParser

config_ai = ZHYConfigParser().config


class SegmentationGeneralPostProcessor:
    """分割结果的通用后处理类，主要包括形态学操作等.
    
    Attributes:
        eroded (bool): 是否进行腐蚀操作.
        dilate (bool): 是否进行膨胀操作.
        close (bool): 是否进行闭运算.
        open (bool): 是否进行开运算.
        kernel_size (int): 用于形态学操作的核的大小.
        iterations (int): 形态学操作的迭代次数.
    """
    
    def __init__(self, seg_pp_config):
        """初始化方法.
        
        Args:
            seg_pp_config (dict): 后处理配置字典.
        """
        self.eroded = seg_pp_config["eroded"]              # 是否进行腐蚀
        self.dilate = seg_pp_config["dilate"]              # 是否进行膨胀
        self.close = seg_pp_config["close"]                # 是否进行闭运算
        self.open = seg_pp_config["open"]                  # 是否进行开运算
        kernel_size = seg_pp_config["kernel_size"]         # 核大小
        self.iterations = seg_pp_config["iterations"]      # 迭代次数
        self.kernel = np.ones((kernel_size, kernel_size), np.uint8)  # 初始化核
        self.water_mask_color = seg_pp_config["water_mask_color"]
        self.water_mask_ratio = seg_pp_config["water_mask_ratio"]
        self.min_area = seg_pp_config["min_area_filter"]  # 最小面积过滤


    def _morphology(self, mask):
        """执行形态学操作.
        
        Args:
            mask (numpy.ndarray): 输入的掩膜图像.
        Returns:
            numpy.ndarray: 经过形态学操作后的掩膜图像.
        """
        if self.eroded:
            mask = cv2.erode(mask, self.kernel, iterations=self.iterations)  # 腐蚀操作
        if self.dilate:
            mask = cv2.dilate(mask, self.kernel, iterations=self.iterations)  # 膨胀操作
        if self.close:
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel, iterations=self.iterations)  # 闭运算
        if self.open:
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel, iterations=self.iterations)  # 开运算
        if self.min_area:
            mask = self.remove_small_areas(mask, self.min_area)  # 最小面积过滤
        return mask


    def remove_small_areas(self, mask, min_area):
        """对掩膜进行面积过滤.
        Args:
            mask (numpy.ndarray): 输入的掩膜图像.
        Returns:
            new_mask (numpy.ndarray): 经过面积过滤后的掩膜图像.
        """
        # 保证掩膜是二值图像
        mask = (mask > 0).astype(np.uint8)

        # 查找连通域
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

        # 创建一个新的空白掩膜用于保存筛选后的区域
        new_mask = np.zeros_like(mask)

        # 循环遍历找到的每个连通域
        for i in range(1, num_labels):  # 从1开始，因为0是背景
            area = stats[i, cv2.CC_STAT_AREA]
            # 如果面积大于阈值，则保留该连通域
            if area >= min_area:
                new_mask[labels == i] = 1

        return new_mask


    def process(self, mask):
        """进行所有配置好的形态学操作并返回处理后的掩膜.
        
        Args:
            mask (numpy.ndarray): 输入的掩膜图像.
        Returns:
            mask (numpy.ndarray): 经过所有配置的形态学操作后的掩膜图像.
        """
        mask = self._morphology(mask)
        return mask


    def cal_shoreline(self, mask, epsilon_factor=0.002):
        """
        计算水岸线坐标, 接口方法.

        Args:
            mask (numpy.ndarray): 分割掩码, 水面为1背景为0
            epsilon_factor (float): 用于控制多边形拟合精度的超参数，默认值为0.002, 越小拟合越准确但点越多

        Returns:
            edge_coordinates (list): 构成水岸线的坐标点的列表, 每个水域一个子列表
        """
        mask = mask.astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        approx_contours = []
        for contour in contours:
            epsilon = epsilon_factor * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            approx_contours.append(approx)

        edge_coordinates = []
        for contour in approx_contours:
            sub_list = [(int(point[0][0]), int(point[0][1])) for point in contour]
            edge_coordinates.append(sub_list)

        return edge_coordinates


    def draw_mask_result(self, img, mask):
        """
        绘制分割结果, 接口方法.

        Args:
            img (numpy.ndarray): 原始图像
            mask (numpy.ndarray): 分割掩码

        Returns:
            img (numpy.ndarray): 绘制了分割结果的图像, 无掩膜时返回原图
        """
        if img.shape[:2] == mask.shape:
            bbox_mask = mask.astype(np.bool_)
            color_mask = np.array(self.water_mask_color, dtype=np.uint8)
            img[bbox_mask] = img[bbox_mask] * (1 - self.water_mask_ratio) + color_mask * self.water_mask_ratio

        return img

    @staticmethod
    def draw_points(img, edge_coordinates, color=(0, 0, 255), radius=5, draw_line=True):
        """
        绘制点，并连接相邻点以及首尾点，接口方法。

        Args:
            img (np.ndarray): 需要绘制点的图像，应为一个NumPy数组。
            edge_coordinates (list): 各点的坐标列表，可以是列表中包含tuple (x, y)，或嵌套列表。
            color (tuple, optional): 用于绘制点和线的颜色。
            radius (int, optional): 绘制的点的半径。
            draw_line (bool, optional): 是否画线。
        Returns:
            np.ndarray: 包含绘制点和线的图像。
        """
        # 特殊情况不进行绘制
        if edge_coordinates and (edge_coordinates[0] == -1 or edge_coordinates[0] == [-1, -1]):
            return img

        # 检查edge_coordinates是不是嵌套列表
        if all(isinstance(item, (list, tuple)) for item in edge_coordinates) and all(len(item) == 2 for item in edge_coordinates):
            # 如果是单个列表，则将其包装在另一个列表中
            edge_coordinates = [edge_coordinates]

        for points in edge_coordinates:
            # 确保每个元素是可迭代的且包含两个元素
            if not all(isinstance(point, (list, tuple)) and len(point) == 2 for point in points):
                continue

            for point in points:
                cv2.circle(img, tuple(point), radius, color, -1)

            if draw_line and len(points) > 1:
                # 绘制线连接相邻点
                for i in range(len(points) - 1):
                    cv2.line(img, tuple(points[i]), tuple(points[i + 1]), color, 1)
                
                # 连接首尾点以闭合形状
                cv2.line(img, tuple(points[-1]), tuple(points[0]), color, 1)

        return img

    @staticmethod
    def draw_dict_on_image(img, info_dict, font_path=r'/root/.config/Ultralytics/simhei.ttf', font_size=32):
        """
        使用PIL在图像的右上角绘制字典的键值对。

        Args:
            img (np.ndarray): 输入图像，应为一个NumPy数组。
            info_dict (dict): 需要绘制的字典，包含0-3个键值对。
            font_path (str): 字体文件的路径。默认为'arial.ttf'。
            font_size (int): 字体大小。默认为16。

        Returns:
            np.ndarray: 包含绘制文本的图像。
        """
        # 将OpenCV图像格式转换为PIL图像格式
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        font = ImageFont.truetype(font_path, font_size)

        # 获取图像的高度和宽度
        img_width, img_height = img_pil.size

        y = 10  # 初始y坐标位置

        for key, value in info_dict.items():
            text = f"{key}: {value}"
            text_width, text_height = draw.textsize(text, font=font) # type: ignore

            # 计算文本的x坐标，使其在图像的右上角
            x = img_width - text_width - 10

            # 绘制文本
            draw.text((x, y), text, font=font, fill=(255, 0, 0, 0))

            # 更新y坐标，为下一行文本留出空间
            y += text_height + 5

        # 将PIL图像转换回OpenCV格式
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
        return img
