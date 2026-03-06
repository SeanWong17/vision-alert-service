# External Dependency Migration (mmseg + yolo)

This service now uses external packages for segmentation/detection instead of vendored source trees.

## What changed

1. `app/water_general_segmentation/predict_mmsegmentation.py`
- Uses `from mmseg.apis import inference_model, init_model`
- No local `mmseg` source tree is required.

2. `app/water_general_detection/predict_yolov5_detection.py`
- Uses `ultralytics.YOLO` as the detector runtime.
- No local `yolov5` source tree is required.

3. `app/water_post_process/general_post_process_det.py`
- Uses `from ultralytics.utils.plotting import Annotator, colors`.

## Install guidance

Because `mmcv` is tightly coupled to your CUDA/PyTorch build, install in this order:

```bash
cd ai_service
python3 -m pip install -r requirements.in -c constraints.txt
python3 -m pip install -U openmim
mim install "mmcv==2.0.0rc4"
```

If `mim install` chooses a mismatched wheel, pin compatible `torch`/CUDA first, then run it again.

## Runtime assumptions

- Model weights remain local files under your configured model directory.
- Config path for mmseg remains your existing `mmseg_config.py`.
- Detection weights (`det_model.pt`) are loaded by `ultralytics.YOLO`.

## Rollback option

If you need to rollback quickly, restore:
- `app/water_general_segmentation/mmseg/`
- `app/water_general_detection/yolov5/`

and switch imports back to vendored paths.
