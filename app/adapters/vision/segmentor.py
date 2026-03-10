"""分割器适配模块：封装 MMSeg 推理能力。"""

from __future__ import annotations

import numpy as np
from mmseg.apis import inference_model, init_model


class MmsegSegmentor:
    """水面分割器封装，输出 uint8 掩膜。"""

    def __init__(
        self,
        config_path: str,
        model_path: str,
        device: str,
        water_class_ids: tuple[int, ...] | list[int] | None = None,
    ):
        """根据配置和权重初始化分割模型。"""

        self.model = init_model(config_path, model_path, device)
        self.water_class_ids = tuple(int(v) for v in (water_class_ids or (1,)))

    def predict_mask(self, image) -> np.ndarray:
        """执行分割推理并返回掩膜。"""

        result = inference_model(self.model, image)
        raw_mask = np.uint8(result.pred_sem_seg.data[0].cpu())
        if not self.water_class_ids:
            return raw_mask
        return np.uint8(np.isin(raw_mask, self.water_class_ids))

    def __call__(self, image) -> np.ndarray:
        """提供可调用语法糖，等价于 `predict_mask`。"""

        return self.predict_mask(image)
