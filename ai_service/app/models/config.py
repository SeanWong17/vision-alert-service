#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : config.py
@desc          : 配置的数据模型
@dateTime      : 2020/03/25 17:23:51
@author        : 5km
@contact       : 5km@smslit.cn
'''
# import modules here
import os.path as op
from typing import Tuple

from pydantic import BaseModel

HOME_PATH = op.expanduser('~')
ZHY_AI_PATH = op.join(HOME_PATH, '.zhyai')
CONFIG_FILE_PATH = op.join(ZHY_AI_PATH, 'config.json')


class AppInfo(BaseModel):
    title: str = 'ZHY AI Service'
    description: str = '智洋创新 AI 图像分析服务调用接口'
    version: str = "v2.2"
    ip: str = "127.0.0.1"


class RedisCfg(BaseModel):
    host: str = '127.0.0.1'
    port: int = 6379
    database: int = 6
    password: str = None


class AutoPush(BaseModel):
    enable: bool = True
    

class WaterpeopleCfg(BaseModel):
    threshold = {
        "default": 0.5,
        "head": 0.7,
        "coat": 0.8,
        "shoe": 0.7,
        "body": 0.7,
        "body_down" : 0.8,
        "food_sundries": 0.9,
        "food_vessel": 0.8
    }
    analysis_time: list = [19, 20, 21, 22, 23, 24, 0 , 1, 2, 3, 4, 5, 6]
    # device_id: list = ['D24']
    cover_thresh = 0.1
    gnms_thresh = 0.8
    tag = ["fishing_gear","person","garbage","float_vt","swim","fire","smog", "digger"]


class WaterPart(BaseModel):
    # 是否启用crop:
    enable: bool = True
    # 识别置信度
    threshold: float = 0.7
    # 过滤交并比
    cover_thresh: float = 0.1
    # 默认crop区域过滤
    roi_config = {
            "A100005EDFE1E9": [2974, 1669, 3048, 1753],
            "A100005EDFE1E9_2": [1390, 655, 1416, 696],
            "A100005EDFE2BC_2": [1524, 663, 1575, 752],
            "A100005EDFE2BC": [3365, 1621, 3470, 1764],
            "A100005EDFE1E9_4-2": [789, 294, 1129, 746],
            #"ZYA20210600001532":[],

    }
    w_min_ratio: float = 0.05
    w_standard_ratio: float = 0.1
#水位尺
class WaterRule(BaseModel):
    # 是否启用crop
    enable: bool = True
    # 识别置信度
    threshold: float = 0.7
    # 过滤交并比
    cover_thresh: float = 0.1
    # 默认crop区域过滤
    roi_config = {}



class TransmissionCfg(BaseModel):
    """
    输电通道配置
    """
    # todo 配置生产路径(本机服务ip及port)
    ip: str = ''
    port: int = 9000
    model: str = 'transmission_channel_hidden_trouble_22'
    threshold: float = 0.5
    # 图片时间限制（秒）
    limit_second = 60 * 60 * 24
    # 是否推送
    push_enable: bool = True


class ZHYColor(BaseModel):
    red: int = 255
    green: int = 255
    blue: int = 255

    @property
    def value(self) -> Tuple[int, int, int]:
        return (self.blue, self.green, self.red)


class DrawResult(BaseModel):
    enable: bool = True
    framecolor: ZHYColor = ZHYColor(red=255, green=0, blue=0)
    fontcolor: ZHYColor = ZHYColor(red=0, green=0, blue=0)
    # 是否启动多颜色标签框
    tagframe_enable = False
    tagframe = {
                'motocrane': [ZHYColor(red=255, green=0, blue=0),
                              {"Bold": False}],   # 吊车（起吊机）
                'towercrane': [ZHYColor(red=255, green=255, blue=0),
                               {"Bold": True}],  # 塔吊(加深)
                'pushdozer': [ZHYColor(red=255, green=0, blue=0),
                              {"Bold": False}],  # 铲车/推土机
                'digger': [ZHYColor(red=255, green=0, blue=0),
                           {"Bold": False}],  # 挖掘机
                'smog': [ZHYColor(red=0, green=0, blue=128),
                         {"Bold": False}],  # 烟雾
                'fire': [ZHYColor(red=0, green=0, blue=128),
                         {"Bold": False}],  # 山火
                # 采砂船暂无
                'colorbelts': [ZHYColor(red=61, green=2, blue=60),
                               {"Bold": True}],  # 彩带（加深）
                'cementmixer': [ZHYColor(red=255, green=255, blue=0),
                                {"Bold": True}],  # 水泥搅拌车（加深）
                'pilingmachine': [ZHYColor(red=255, green=0, blue=0),
                                  {"Bold": False}],  # 打桩机
                'pumpcar': [ZHYColor(red=255, green=0, blue=0),
                            {"Bold": False}],  # 水泥泵车
                }


class CpuRamCfg(BaseModel):
    # 堆积图片性能分析
    enable: bool = False
    img_num: int = 5000
    name_key: str = "major_url"
    thread_sleep: int = 60 * 10
    url_store: int = 60 * 60 * 24
    timeout: int = 10


class AutoClean(BaseModel):
    enable: bool = True
    expired: int = 60
    clean_expired: int = 60 * 24 * 5


class AICfg(BaseModel):
    host: str = '127.0.0.1'
    port: int = 8500
    threshold: float = 0.6
    gpu_value: int = 100
    thread_sleep: float = 0.01
    # 开启异步接口
    async_api_enable = False
    # 值越大，防护区越明显
    autopush: AutoPush = AutoPush()
    draw: DrawResult = DrawResult()
    autoclean: AutoClean = AutoClean()
    transmission: TransmissionCfg = TransmissionCfg()


class FilePathCfg(BaseModel):
    root: str = ZHY_AI_PATH

    @property
    def upload(self):
        return op.join(self.root, 'images/upload')

    @property
    def upload_video(self):
        return op.join(self.root, 'images/upload_video')

    @property
    def result_video(self):
        return op.join(self.root, 'images/result_video')

    @property
    def result(self):
        return op.join(self.root, 'images/result')

    @property
    def log(self):
        return op.join(self.root, 'log')

    @property
    def data_store(self):
        return op.join(self.root, 'data_store')
    
    @property
    def crop_image(self):
        return op.join(self.root, 'crop_image')

    @property
    def model_file(self):
        return op.join(self.root, "model")

    @property
    def water_general(self):
        return op.join(self.root, "water_general")

    @property
    def water3d_file(self):
        return op.join(self.root, "water_3d")

    @property
    def water_ruler(self):
        return op.join(self.root, "water_ruler")
    
    @property
    def water_cd(self):
        return op.join(self.root, "water_cd")

    @property
    def water_segment(self):
        return op.join(self.root, "water_segment")

    @property
    def config_file(self):
        return self.root

class ServerCfg(BaseModel):
    host: str = '0.0.0.0'
    port: int = 8011


class EsCfg(BaseModel):
    token: str = 'emh5YXBpOnpoeUB6eTkxMSM='
    username: str = 'zhydev'
    password: str = 'Zhy$900dev'
    username_url: str = '58.58.111.158:21031'
    token_url: str = '58.58.111.158:21054'
    # 是否启用
    enable: bool = False


class PaddleCfg(BaseModel):
    paddle_enable: bool = False
    # 使用n号显卡
    device: str = "0"


class RsaCfg(BaseModel):
    enable: bool = False
    # 公钥
    public_key: str = ''
    # 私钥
    private_key: str = ''


class ModelAnalysis(BaseModel):
    ip: str = ''
    port: str = 9001


class Config(BaseModel):
    appinfo: AppInfo = AppInfo()
    ai: AICfg = AICfg()
    redis: RedisCfg = RedisCfg()
    server: ServerCfg = ServerCfg()
    filepath: FilePathCfg = FilePathCfg()
    es_cfg: EsCfg = EsCfg()
    cpu_ram_cfg: CpuRamCfg = CpuRamCfg()
    # 多边形
    paddle: PaddleCfg = PaddleCfg()
    rsa_cfg: RsaCfg = RsaCfg()

    # 水利crop
    water: WaterPart = WaterPart()
    #水位尺
    water_rule: WaterRule = WaterRule()
    water_people: WaterpeopleCfg = WaterpeopleCfg()
    # model_analysis_cfg: ModelAnalysis = ModelAnalysis()
