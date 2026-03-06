"""
  视频监控防溺水 配置文件
        识别项：
                'fishing_gear': '鱼竿',
                'person': '人员',
                'garbage': '垃圾',
                'float_vt': '漂浮物',
                'swim': '游泳',
                'fire': '火',
                'smog': '烟',
                'digger': '挖掘机',
                'enter_water': '人员进入水域',
                'near_water': '人员靠近水域',
                'rodster': '钓鱼人员',
                'ship': '船只'
"""

# 1. 基础检测模型推理配置文件, 必需
det_config = {
        "imgsz": [1280, 1280],
        "conf_thres": 0.5,    # 置信度过滤的默认值从此设置
        "iou_thres": 0.45,
        "device_id": 0
        }


# 2. 检测通用后处理配置文件, 必需
det_pp_config = {

        # 类别合并
        'merge_config': {
                'garbage': ["foam", "litter", "bottle", "litter_difficult"],
                'float_vt': ["fragment", "deadwood", "leaf", "duckweed", "algae", "waterweed"],
                'ship': ['fishing_vessels', 'boat']
                }, 

        # 置信度过滤, 保留置信度大于阈值的框
        'conf_config': {
                        "fire": 0.9,
                        "smog": 0.8,
                        "garbage": 0.7
                        },       

        # 类别过滤, 保留列表内的类别
        'cls_config': ["rodster", "adult", "teenager", "digger", "fishing_gear", "swim", "smog", "fire", "garbage", "float_vt", "ship",  # 原有需保留类别
                       'tank_truck', 'container_truck', 'dump_truck', 'heavy_truck', 'medium_truck', 'light_truck', 'box_truck', 'cementmixer', 'pushdozer', 'forklift',
                       'roller', 'digger', 'motocrane', 'car', 'van', 'bus', 'motorcycle', 'bicycle', 'awning_tricycle', 'tricycle'],   # 增加车类别用于判断

        # 面积过滤,
        'area_config': {
            'min_area_config': {  # 最小面积过滤, 保留对应类别大于最小面积的框
                "garbage": 4500,
                "float_vt": 4500
                }, 
             'max_area_config': {},  # 最大面积过滤, 保留对应类别小于最大面积的框
        },

        # 按点位区域过滤
        'roi_config': {
            'roi_config_position': {},  # 预设点位ROI {"Default": [38, 168, 177, 538],  "A100005EDFE1E9": [2974, 1669, 3048, 1753],}
            'roi_iof_thres': 0.5,   # 保留检测结果的iof阈值
            'roi_classes': [],      # 区域过滤时需要过滤的类别, []时过滤所有类别
        },    
        
        # 时间类别置信度过滤
        'time_config': {
            'night_range': ['18:00', '6:00'],
            'time_conf_config': {
                "float_vt": 0.99,
                "fire": 0.99
                }, 
        }
}


# 3. 基础分割模型配置文件, 必需
seg_config = {
        "conf_thres": 0.25,
        "device": "cuda:0",             # mmseg推理设备
        "device_id": 0,                 # yolov8seg推理设备
        'resolution': (640, 640),
        'stride': 32
        }


# 4. 分割通用后处理配置文件, 必需
seg_pp_config = {
                "eroded": False,  # 是否腐蚀
                "dilate": False,  # 是否膨胀
                "close": False,   # 是否闭运算
                "open": False,    # 是否开运算
                "kernel_size": 20,      # 核大小
                "iterations": 5,        # 迭代次数
                "water_mask_color": [0, 0, 255],  # 绘制水面掩膜颜色
                "water_mask_ratio": 0.3,          # 掩膜绘制到原图的比重
                'min_area_filter': 1000           # 删除小于此面积的掩膜
                }


# 5. 项目专用后处理类参数配置文件, 必需
specific_pp_config = {
        "config_dict": {
                'thread_horizontal': 4,
                'thread_vertical_below': 3,
                'thread_vertical_top': 0.01,
                'near_enter_distg_thread': 0,
                'car_list': ['tank_truck', 'container_truck', 'dump_truck', 'heavy_truck', 'medium_truck', 'light_truck', 'box_truck', 'cementmixer', 'pushdozer', 'forklift', 
                             'roller', 'digger', 'motocrane', 'car', 'van', 'bus', 'motorcycle', 'bicycle', 'awning_tricycle', 'tricycle'],  # 与20类车有交集的人不判为靠近水域
                'float_vt_max_area_rario': 0.8,         # 漂浮物面积大于图像该比例时过滤
                'fishing_gear_max_length_ratio': 0.9,   # 鱼竿长度大于图像该比例时过滤

                },
}

# 6. 绘制图像配置文件, 必需
plot_config = {
        "using_chinese": True,  # 标签是否使用中文
        "using_conf": True,     # 是否显示置信度
        "line_width": 3,        # 绘制线宽度

        # 类别对应字典
        "res_name_dict": {
            "rodster": "钓鱼人员",
            "adult": "成年人",
            "teenager": "未成年人",
            "tank_truck": "罐式货车",
            "container_truck": "集装箱货车",
            "dump_truck": "自卸车",
            "heavy_truck": "重型卡车",
            "medium_truck": "中型卡车",
            "light_truck": "轻型卡车",
            "box_truck": "厢式货车",
            "cementmixer": "水泥搅拌车",
            "pushdozer": "推土机",
            "forklift": "铲车",
            "roller": "压路机",
            "digger": "挖掘机",
            "motocrane": "吊车（工作/不工作）",
            "car": "小汽车",
            "van": "面包车",
            "bus": "大巴车/中巴车",
            "motorcycle": "摩托车",
            "bicycle": "两轮电动/自行车",
            "awning_tricycle": "三轮车（带棚）",
            "tricycle": "三轮车（不带棚）",
            "fishing_gear": "鱼竿",
            "fishing_net": "渔网",
            "barrel": "渔桶",
            "swim": "游泳人员",
            "drown": "溺水人员",
            "dump_garbage": "倾倒垃圾",
            "fragment": "碎屑【水面】",
            "deadwood": "植物秸秆/枯枝【水面】",
            "leaf": "堆积树叶【水面】",
            "foam": "泡沫板",
            "litter": "塑料袋",
            "bottle": "瓶状垃圾",
            "litter_difficult": "困难垃圾",
            "duckweed": "浮萍【水面】",
            "algae": "水藻【水面】",
            "waterweed": "水草【水面】",
            "sewage": "排污口排污",
            "sewage_outlet": "排污口未排污",
            "dredge": "采砂船",
            "gate_open": "闸门开",
            "gate_close": "闸门关",
            "smog": "浓烟",
            "fire": "明火",
            "fishing_vessels": "捕鱼船只",
            "boat": "普通船只",
            "bird": "鸟类",
            "sheep": "羊",
            "cattle": "牛",
            "dog": "狗（猫）",
            "duck": "鸭、鹅",
            "glint": "光斑【水面】"
            },
}