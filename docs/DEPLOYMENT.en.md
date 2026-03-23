[中文](DEPLOYMENT.md) | [English](DEPLOYMENT.en.md)

# Deployment Guide

## 1. Installing Dependencies

```bash
python3 -m pip install -r requirements.txt
```

For real segmentation inference, you must install the **full `mmcv`** build that matches your current PyTorch / CUDA version:

```bash
python3 -m pip install -U openmim
mim install mmcv
```

Notes:
- Installing `mmsegmentation` alone is not sufficient. Real image requests import `mmseg` at runtime, and without the full `mmcv` you will see `No module named 'mmcv._ext'`.
- `mmcv-lite` cannot replace full `mmcv` for the current model inference pipeline.
- The current `Dockerfile` installs a compatible full `mmcv` via `openmim` at image build time. Non-Docker deployments still require the manual install commands above.
- The current dependencies pin `numpy` to `<2` to avoid ABI compatibility warnings or runtime errors with `torch 2.1.x` / `mmcv 2.1.x` under NumPy 2.x.

## 2. Runtime Directory

Create the runtime directory structure:

```bash
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001
cp runtime/config.example.json runtime/config.json
```

Directory layout:
- `runtime/log`
- `runtime/images/upload`
- `runtime/images/result`
- `runtime/models/<version>`
- `runtime/config.json`

Each model version directory must contain:
- `det_model.pt`
- `mmseg_config.py`
- `seg_model.pt`

To quickly download a lightweight model bundle (person detection + semantic segmentation):

```bash
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
```

If you are using an ADE20K pre-trained segmentation model, configure the target segmentation class IDs in `runtime/config.json`. The value `[2]` corresponds to the `sky` class in ADE20K and is provided only as a demo default — replace it with the class IDs required for your use case before deploying to production:

```json
{
    "alert": {
      "segmentor_target_class_ids": [2],
      "segment_postprocess_class_names": ["person"],
      "in_segment_overlap_ratio": 0.25,
      "near_segment_distance_px": 24
    }
  }
```

Notes:
- `segment_postprocess_class_names` controls which detection classes have segmentation post-processing applied. Defaults to `["person"]`.
- `in_segment_overlap_ratio` controls the threshold for the `enter_segment` determination. The current default is `0.25`.
- When a detection box overlaps the target segmentation region but has not yet reached the entry threshold, it is classified as `near_segment`.

## 3. Docker

Docker files are located in the `docker/` directory (compose file: `docker-compose.yaml`).
For detailed container testing steps, see `docs/CONTAINER_TEST.md`.

The current Dockerfile includes the following runtime system packages:
- `libgl1`
- `libglib2.0-0`
- `libsm6`
- `libxrender1`
- `libxext6`
- `tzdata`

Notes:
- `libgl1` provides the system shared library required for `import cv2` inside the container. Without it, the container will fail to start with a `libGL.so.1` error.
- The image timezone is set to `Asia/Shanghai` by default.
- The Docker build stage installs a compatible full `mmcv`, so no manual post-start installation is needed inside the container.

Start the service:

```bash
cd docker
docker compose up -d --build
```

Volume mapping:
- Container `/root/.vision_alert` -> Host `runtime`

Common environment variables (configurable in `docker-compose.yaml`):

**Inference device**
- `ALERT_DET_DEVICE`: Detection device. Use `cpu` for in-container testing.
- `ALERT_SEG_DEVICE`: Segmentation device. Use `cpu` for in-container testing.

**File management**
- `ALERT_IMAGE_RETENTION_DAYS`: Retention period in days for uploaded and result images. Default: `30`.
- `ALERT_CLEANUP_SCAN_INTERVAL_SECONDS`: Cleanup scan interval in seconds. Default: `3600`.
- `ALERT_UPLOAD_MAX_BYTES`: Maximum upload size per image in bytes. Default: `20971520` (20 MB).

**Configuration loading**
- `ALERT_CONFIG_STRICT`: Whether a failed config load prevents startup. Default: `true`.

**Logging**
- `ALERT_LOG_FORMAT`: Log output format. Set to `json` to enable structured JSON logging (suitable for ELK / Loki / CloudWatch). Default: plain text.

## 4. Recovering from a Corrupt Configuration (Strict Mode)

With the default `ALERT_CONFIG_STRICT=true`, a parse failure in `runtime/config.json` will prevent the service from starting.

Emergency recovery steps:
1. Temporarily set `ALERT_CONFIG_STRICT=false` and start the service to keep it available.
2. Fix `runtime/config.json`.
3. Restore `ALERT_CONFIG_STRICT=true`, restart the service, and verify the configuration is loaded correctly.

## 5. Startup Options

```bash
python3 main.py --host 0.0.0.0 --port 8011 --workers 4
```

| Flag | Description | Default |
|------|-------------|---------|
| `--host` | Bind address | `0.0.0.0` |
| `--port` | Bind port | `8011` |
| `--workers` | Number of Uvicorn worker processes | `1` |

> Note: With `--workers > 1`, the in-memory queue backend is not shared across processes. Use Redis in production when running multiple workers.

On startup, the service automatically warms up the models by calling `pipeline.warm_up()`, eliminating cold-start latency on the first request and shifting that cost to the process startup phase instead.

Graceful shutdown: after receiving SIGTERM, the service has a 15-second window to finish in-flight requests before stopping the background worker thread.

## 6. Production Recommendations

- Use `/healthz` and `/readyz` as liveness and readiness probes respectively.
- Scrape `/metrics` with Prometheus and configure alerting rules.
- Enable `ALERT_LOG_FORMAT=json` to forward logs to ELK, Loki, or similar log aggregation systems.
- For alert thresholds, fault drills, and capacity baselines, see `docs/OPERATIONS.md`.
