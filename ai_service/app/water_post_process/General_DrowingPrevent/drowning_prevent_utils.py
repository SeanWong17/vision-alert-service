import cv2
import numpy as np
from datetime import datetime


# 防溺水后处理
class DrowingJudgement:
    def __init__(self, specific_pp_config):

        # 分配子配置文件
        config_dict = specific_pp_config['config_dict']

        # 分配子配置文件参数
        self.thread_horizontal = config_dict['thread_horizontal']           # 身宽倍数（水平）
        self.thread_vertical_below = config_dict['thread_vertical_below']   # 身宽倍数（下方）
        self.thread_vertical_top = config_dict['thread_vertical_top']       # 身宽倍数（上方）
        self.near_enter_distg_thread = config_dict['near_enter_distg_thread']
        self.car_list = config_dict['car_list']                                             # 车辆类别列表
        self.float_vt_max_area_rario = config_dict['float_vt_max_area_rario']               # 需要过滤的漂浮物面积比例阈值
        self.fishing_gear_max_length_ratio = config_dict['fishing_gear_max_length_ratio']   # 需要过滤的鱼竿长度比例阈值
        self.night_range  = config_dict.get('time_config', ['18:00', '6:00'])               # 夜间时间, 期间不判断靠近、进入水域


    def judge_bounding(self, img_shape, top_left, bottom_right, dist_top, dist_bottom, dist_left, dist_right):
        # 判断缓冲域四个方向是否为边界，是则返回边界值
        height, width = img_shape
        bounding_top = max(0, int(top_left[1] - dist_top))  # 上
        bounding_bottom = min(height, int(bottom_right[1] + dist_bottom))  # 下
        bounding_left = max(0, int(top_left[0] - dist_left))  # 左
        bounding_right = min(width, int(bottom_right[0] + dist_right))  # 右
        return (bounding_top, bounding_bottom, bounding_left, bounding_right)


    def judge_near(self, img_shape, msk_map, thread_horizontal, thread_vertical_below, thread_vertical_top, top_left, bottom_right):
        # 根据目标宽度为目标设置缓冲域
        width_pixels = bottom_right[0] - top_left[0]  # 目标宽度占用像素数目

        width_thread_horizontal = width_pixels * thread_horizontal
        width_thread_vertical_top = width_pixels * thread_vertical_top
        width_thread_vertical_below = width_pixels * thread_vertical_below

        bounding = self.judge_bounding(img_shape, top_left, bottom_right, width_thread_vertical_top, width_thread_vertical_below, 
                                        width_thread_horizontal, width_thread_horizontal)

        sub_msk_map = msk_map[bounding[0]:bounding[1], bounding[2]:bounding[3]]
        is_near = np.any(sub_msk_map == 1)

        return is_near


    def judge_enter(self, img_shape, msk_map, near_enter_distg_thread, top_left, bottom_right):
        # 判断目标四个角是否均极其靠近水

        # 计算目标的像素宽度
        width_pixels = bottom_right[0] - top_left[0]
        # 预先计算与 near_enter_distg_thread 相关的量，避免重复计算
        precomputed_thread = width_pixels * near_enter_distg_thread

        # 定义四个角的坐标、边界和子地图
        corners = [
            {'coords': [top_left[0], bottom_right[1]], 'bounding': None, 'sub_map': None},  # bottom_left
            {'coords': bottom_right, 'bounding': None, 'sub_map': None},  # bottom_right
            {'coords': top_left, 'bounding': None, 'sub_map': None},  # top_left
            {'coords': [bottom_right[0], top_left[1]], 'bounding': None, 'sub_map': None},  # top_right
        ]

        # Lambda 函数用于获取子地图
        get_sub_map = lambda x: msk_map[x[0]:x[1] + 1, x[2]:x[3] + 1]

        # 遍历每一个角，并执行相应的操作
        for corner in corners:
            coords = corner['coords']
            # 调用 judge_bounding 函数获取边界
            corner['bounding'] = self.judge_bounding(img_shape, coords, coords, precomputed_thread, precomputed_thread, precomputed_thread, precomputed_thread)
            # 获取子地图
            corner['sub_map'] = get_sub_map(corner['bounding'])

        # 判断每一个角的子地图中是否包含1
        is_enter = all(np.any(corner['sub_map'] == 1) for corner in corners)

        return is_enter


    def judge_intersection(self, shape, res_det, indexes, top_left, bottom_right):
        # 判断是否存在交集
        img_map = np.zeros(shape, dtype=np.uint8)
        
        for i in indexes:
            coords = np.array(res_det[i][0:4], dtype=np.int)  # 只取xmin, ymin, xmax, ymax四个坐标
            y1, x1, y2, x2 = np.clip(coords, 0, [shape[0]-1, shape[1]-1, shape[0]-1, shape[1]-1])
            img_map[y1:y2, x1:x2] = 1
        
        is_near = np.any(img_map[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]])
        return bool(is_near)


    def predict(self, res_det, res_seg):
        img_shape = res_seg.shape

        # 判断是否为夜间
        start_time = datetime.strptime(self.night_range[0], '%H:%M').time()
        end_time = datetime.strptime(self.night_range[1], '%H:%M').time()
        now = datetime.now().time()
        is_night = start_time <= now < end_time if start_time < end_time else now >= start_time or now < end_time

        if res_det is None:
            return []

        objs = []
        for obj in res_det:  # 遍历每一个识别对象
            top_left = np.round(obj[:2]).astype(np.uint16)
            bottom_right = np.round(obj[2:4]).astype(np.uint16)

            # 会存在检测框越界情况，需判断
            top_left[0] = min(top_left[0], img_shape[1] - 1)
            top_left[1] = min(top_left[1], img_shape[0] - 1)
            bottom_right[0] = min(bottom_right[0], img_shape[1] - 1)
            bottom_right[1] = min(bottom_right[1], img_shape[0] - 1)

            obj_type = obj[5]
            pred_lbl = None

            # 人员判断
            if obj_type in ["adult", "teenager"]:
                is_near = self.judge_near(img_shape, res_seg, self.thread_horizontal, self.thread_vertical_below, self.thread_vertical_top, top_left, bottom_right)
                is_enter = self.judge_enter(img_shape, res_seg, self.near_enter_distg_thread, top_left, bottom_right)

                if is_enter and not is_night:
                    pred_lbl = 'enter_water'

                elif is_near and not is_night:
                    # 与车有交集的人不判为靠近水域
                    res_det = np.array(res_det)
                    indexes = [index for index, label in enumerate(res_det[:, 5]) if label in self.car_list]
                    is_intersection = self.judge_intersection(img_shape, res_det, indexes, top_left, bottom_right)
                    if is_intersection:
                        pred_lbl = 'person'
                    else:
                        pred_lbl = 'near_water'

                else:
                    pred_lbl = 'person'

            # 游泳判断
            elif obj_type == "swim":
                is_enter = self.judge_enter(img_shape, res_seg, self.near_enter_distg_thread, top_left, bottom_right)
                if is_enter:
                    pred_lbl = 'swim'
            
            # 鱼竿判断
            elif obj_type == "fishing_gear":
                # if np.isin(1, res_seg):  # 如果mask中有1(水面)
                #     pred_lbl = 'fishing_gear'

                if len(res_det) == 1:  # 若图像中仅有鱼竿一类，则视为鱼竿误报
                    return []
                
                xmin, ymin, xmax, ymax = obj[:4]
                if (ymax-ymin) / img_shape[0] < self.fishing_gear_max_length_ratio:  # 鱼竿高度小于图像高度的90%
                    pred_lbl = 'fishing_gear'

            # 漂浮物判断
            elif obj_type == "float_vt":
                xmin, ymin, xmax, ymax = obj[:4]
                if (xmax-xmin)*(ymax-ymin) < img_shape[0]*img_shape[1] * self.float_vt_max_area_rario:
                    pred_lbl = 'float_vt'

            else:
                if obj_type not in self.car_list:
                    pred_lbl = obj_type

            if pred_lbl:
                xmin, ymin, xmax, ymax = obj[:4]
                objs.append([int(xmin), int(ymin), int(xmax), int(ymax), round(float(obj[4]), 2), str(pred_lbl)])  # x y x y conf name

        return objs
