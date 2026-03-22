# 模型目录说明

运行时会自动选择数值最大的版本目录，并保留原始目录名，例如 `000001`。
每个版本目录需包含：
- `det_model.pt`
- `mmseg_config.py`
- `seg_model.pt`

## 快速安装轻量模型（人检 + 水面分割）

在仓库根目录执行：

```bash
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
```

可用 pack：

- `nano-v8-b0`：`YOLOv8n + SegFormer-B0(ADE20K)`
- `nano-v11-b0`：`YOLO11n + SegFormer-B0(ADE20K)`（推荐）
- `nano-v11-b1`：`YOLO11n + SegFormer-B1(ADE20K)`

说明：

- 水面类别默认使用 ADE20K 的 `water=21`，请在 `runtime/config.json` 设置：
  - `"alert.segmentor_water_class_ids": [21]`
- 建议本地仅保留一个版本目录，避免切换误用。
- 服务会加载数值最大的版本目录。
