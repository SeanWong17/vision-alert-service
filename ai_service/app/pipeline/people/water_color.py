import cv2
import numpy as np


class WaterColor:
    def __init__(self, k: int = 4, criteria: tuple = (1, 1000, 0), min_area_thread: float = 0.3):
        """
        初始化水体颜色处理类.
        Args:
            k: K-means 聚类的数量.
            criteria: K-means 的终止条件.
            min_area_thread: 面积占比阈值.
        """
        self.k = k
        self.criteria = criteria
        self.min_area_thread = min_area_thread

    def cal_water_color(self, orig_img: np.ndarray, mask: np.ndarray) -> tuple:
        """
        计算水体颜色.
        Args:
            orig_img: 原始图像.
            mask: 水面掩码.
        Returns:
            cluster_ratio_dict: 聚类比例字典.
            num_water_pix: 水面像素数.
            centers: 聚类中心.
            bbox_mask: 边界框掩码.
            labels: 聚类标签.
        """
        num_water_pix = np.count_nonzero(mask)
        bbox_mask = mask.astype(np.bool_)
        cluster_ratio_dict = {}
        centers, labels = [], []

        if num_water_pix:
            img_hsv = cv2.cvtColor(orig_img, cv2.COLOR_BGR2HSV)
            water_pixels = np.float32(img_hsv[bbox_mask])
            _, labels, centers = cv2.kmeans(water_pixels, self.k, None, self.criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

            # 计算每个聚类占水面像素的比例
            unique_labels, counts = np.unique(labels, return_counts=True)
            color_count = dict(zip(unique_labels, counts))

            for i, c in enumerate(centers):
                color_name = self.get_color(c)
                ratio = color_count[i] / num_water_pix
                if ratio >= self.min_area_thread:
                    cluster_ratio_dict[color_name] = round(ratio, 2)

        return cluster_ratio_dict, num_water_pix, centers, bbox_mask, labels

    @staticmethod
    def draw_clusters(orig_img: np.ndarray, num_water_pix: int, centers: list, bbox_mask: np.ndarray, labels: np.ndarray) -> np.ndarray:
        """
        绘制聚类结果.
        Args:
            orig_img: 原始图像.
            num_water_pix: 水面像素数.
            centers: 聚类中心.
            bbox_mask: 边界框掩码.
            labels: 聚类标签.
        Returns:
            img_copy: 处理后的图像.
        """
        if not num_water_pix:
            return orig_img

        img_copy = orig_img.copy()
        for i, c in enumerate(centers):
            color_rgb = cv2.cvtColor(np.uint8([[c]]), cv2.COLOR_HSV2BGR)[0][0]
            coord = np.argwhere(bbox_mask)
            label_indices = np.argwhere(labels == i).flatten()
            color_coords = coord[label_indices]
            img_copy[color_coords[:, 0], color_coords[:, 1]] = color_rgb.astype(np.uint8)

        return img_copy

    @staticmethod
    def get_color(hsv: tuple) -> str:
        """
        根据 HSV 值识别并返回颜色名称.
        Args:
            hsv: HSV色彩空间的值，包含色调（H），饱和度（S），明度（V）.
        Returns:
            color: 识别出的颜色名称，如果未识别到则返回 "未定义颜色".
        """
        # 颜色范围映射表
        color_ranges = {
            '暗红': {'H': [(0, 6), (156, 180)], 'S': (43, 256), 'V': (46, 150)},
            '红': {'H': [(0, 6), (156, 180)], 'S': (90, 256), 'V': (150, 256)},
            '淡红': {'H': [(0, 6), (156, 180)], 'S': (43, 90), 'V': (150, 256)},
            '黄褐': {'H': [(6, 27)], 'S': (30, 256), 'V': (46, 256)},
            '黄绿': {'H': [(27, 31), (31, 40)], 'S': (43, 256), 'V': (46, 150)},
            '黄': {'H': [(27, 31)], 'S': (90, 256), 'V': (150, 256)},
            '淡黄': {'H': [(27, 31)], 'S': (43, 90), 'V': (150, 256)},
            '绿': {'H': [(40, 90)], 'S': (43, 256), 'V': (46, 150)},
            '浅绿': {'H': [(40, 90)], 'S': (43, 90), 'V': (150, 256)},
            '暗青': {'H': [(90, 96)], 'S': (43, 256), 'V': (46, 150)},
            '青': {'H': [(90, 96)], 'S': (90, 256), 'V': (150, 256)},
            '淡青': {'H': [(90, 96)], 'S': (43, 90), 'V': (150, 256)},
            '蓝灰': {'H': [(96, 136)], 'S': (43, 256), 'V': (46, 150)},
            '蓝': {'H': [(96, 136)], 'S': (90, 256), 'V': (150, 256)},
            '浅蓝': {'H': [(96, 136)], 'S': (43, 90), 'V': (150, 256)},
            '暗紫': {'H': [(136, 150)], 'S': (43, 256), 'V': (46, 150)},
            '紫': {'H': [(136, 150)], 'S': (90, 256), 'V': (150, 256)},
            '淡紫': {'H': [(136, 150)], 'S': (43, 90), 'V': (150, 256)},
            '黑': {'H': [(0, 180)], 'S': (0, 256), 'V': (0, 46)},
            '灰黑': {'H': [(0, 180)], 'S': (0, 43), 'V': (46, 100)},
            '灰': {'H': [(0, 180)], 'S': (0, 43), 'V': (100, 150)},
            '白': {'H': [(0, 100)], 'S': (0, 10), 'V': (240, 256)},
            '灰白': {'H': [(0, 100)], 'S': (10, 30), 'V': (240, 256)}
        }

        h, s, v = hsv
        for color, ranges in color_ranges.items():
            h_in_range = any(low <= h <= high for low, high in ranges['H'])
            s_in_range = ranges['S'][0] <= s <= ranges['S'][1]
            v_in_range = ranges['V'][0] <= v <= ranges['V'][1]
            
            if h_in_range and s_in_range and v_in_range:
                return color
        return "未定义颜色"
