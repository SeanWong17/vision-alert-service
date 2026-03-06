#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : predict_mmsegmentation.py
@desc          : mmsegmentation 分割模型推理   mmcv==2.0.0rc4   mmengine==0.8.4
@dateTime      : 2023/08/30
@author        : ws
'''

import numpy as np
from mmseg.apis import inference_model, init_model


class MMImageSegmentor:
    """
    图像分割类, 用于初始化图像分割模型并进行分割预测.
    """
    def __init__(self, config_path, model_path, device):
        """
        初始化ImageSegmentor类.

        Args:
            config_path (str): 模型配置文件的路径.
            model_path (str): 预训练模型的路径.
            device: 推理设备, 如：'cuda:0'.
        """
        self.seg_model = init_model(config_path, model_path, device)

    def predict_seg(self, img):
        """
        接口函数
        
        输入一张图像, 进行模型的推理, 返回分割结果.

        Args:
            img: 图像的路径或numpy矩阵(w*h*3).
        Returns:
            result: 分割 0-1 二值掩膜(w*h).
        """
        result = inference_model(self.seg_model, img)
        result = np.uint8(result.pred_sem_seg.data[0].cpu())    # numpy格式, w*h的0-1掩膜, 0为背景, 1为水面
        # result = np.uint8(np.where(result==1, 255, 0))          # 0-1 --> 0-255
        return result

    def __call__(self, img):
        """
        类的可调用方法, 方便直接使用类实例进行图像分割.

        Args:
            im0: 输入图像, 可以是图像路径或numpy矩阵.

        Returns:
            分割结果, 与predict_seg方法返回相同.
        """
        return self.predict_seg(img)
