# Model Directory

[中文](README.md) | [English](README.en.md)

The runtime automatically selects the version directory with the highest numeric name and uses it as-is — for example, `000001`.

Each version directory must contain:
- `det_model.pt`
- `mmseg_config.py`
- `seg_model.pt`

## Quick Install: Lightweight Models (Person Detection + Sky Segmentation)

Run the following from the repository root:

```bash
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
```

Available packs:

- `nano-v8-b0`: `YOLOv8n + SegFormer-B0 (ADE20K)`
- `nano-v11-b0`: `YOLO11n + SegFormer-B0 (ADE20K)` (recommended)
- `nano-v11-b1`: `YOLO11n + SegFormer-B1 (ADE20K)`

Notes:

- The pretrained models use the ADE20K dataset by default. The value `sky=2` is provided only as a ready-to-run demo default; in production you should replace it with the class IDs relevant to your use case. Set the following in `runtime/config.json`:
  - `"alert.segmentor_target_class_ids": [2]`
  - `"alert.segment_postprocess_class_names": ["person"]`
- It is recommended to keep only one version directory locally to avoid accidentally loading the wrong model.
- The service loads the version directory with the highest numeric name.
