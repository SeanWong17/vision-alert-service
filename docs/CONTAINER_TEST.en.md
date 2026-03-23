[中文](CONTAINER_TEST.md) | [English](CONTAINER_TEST.en.md)

# Container Startup and Testing Guide

This document covers the scenario where you have a GPU on your local machine, are not using conda, and want to test directly with Docker containers.

## 1. Prepare Models and Configuration

From the repository root:

```bash
cp runtime/config.example.json runtime/config.json
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
```

This installs a lightweight model bundle into `runtime/models/000001`:

- Person detection: `yolo11n`
- Semantic segmentation: `segformer_mit-b0_ade20k`

## 2. Start the Container (CPU)

Run the unit tests inside the container first:

```bash
cd docker
docker compose --profile test build vision_alert_test
docker compose --profile test run --rm vision_alert_test
```

Alternatively, to build the test image directly from the repository root:

```bash
docker build -f docker/Dockerfile --target test -t vision-alert:test .
docker run --rm -v "$(pwd)/runtime:/root/.vision_alert" vision-alert:test
```

Notes:
- The test image already includes `pytest`. If you see `No module named pytest` inside the container, the test image was not rebuilt with the latest configuration.

Once the unit tests pass, start the service container:

```bash
cd docker
docker compose up -d --build
```

## 3. Start the Container (GPU)

Prerequisites:
- NVIDIA drivers installed
- `nvidia-container-toolkit` installed
- NVIDIA runtime visible in `docker info`

Before starting, edit `docker/docker-compose.yaml` and uncomment the GPU-related environment variables and the `deploy.resources.devices` section, then run:

```bash
cd docker
docker compose up -d --build
```

## 4. Health Checks

```bash
curl -s http://127.0.0.1:8011/healthz
curl -s http://127.0.0.1:8011/readyz
```

## 5. API Smoke Test

Prepare a local image file, then run:

```bash
python3 scripts/smoke_api.py --host 127.0.0.1 --port 8011 --image /abs/path/to/test.jpg
```

Important notes:
- Passing `/healthz` and `/readyz` only confirms that the web service, worker, and Redis connection are healthy. It does not confirm that the real model inference dependencies are fully operational.
- The current `Dockerfile` installs a compatible full `mmcv` at image build time.
- The current runtime image pins `numpy` to `<2` to avoid ABI compatibility warnings with `torch 2.1.x` / `mmcv 2.1.x` under NumPy 2.x.
- If `mmcv._ext` is still missing inside the container, the full `mmcv` installation step failed during the build or was replaced by `mmcv-lite`.

## 6. Common Troubleshooting

**Container fails to start with `libGL.so.1`:**
- The OpenCV runtime library is incomplete. The image must include `libgl1`.

**Segmentation results are always empty:**
- Verify that `alert.segmentor_target_class_ids` in `runtime/config.json` contains the target segmentation class IDs. The pre-trained model uses the ADE20K dataset by default, where `[2]` corresponds to the `sky` class. This is provided as an out-of-the-box demo value only — replace it with the class IDs required for your use case before deploying to production.

**Real image requests fail with `No module named 'mmcv._ext'`:**
- Only `mmcv-lite` is installed, or the full `mmcv` installation failed during the Docker build.
- Check the `python -m mim install "mmcv==..."` step in the image build logs.

**Real image requests fail with `ftfy` / `regex` missing during `mmseg` import:**
- This indicates that text/tokenizer-related dependencies for `mmseg` are not fully installed.
- Both packages have been added to `requirements.txt`.

**Container logs show `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x`:**
- `torch` / `mmcv` are incompatible with the installed NumPy major version.
- Dependencies are pinned to `numpy<2`. If the warning still appears, the image was not rebuilt with the latest dependencies.

**CUDA not available inside the container:**
- Run `nvidia-smi` on the host first.
- Then run `docker run --rm --gpus all nvidia/cuda:12.3.2-runtime-ubuntu22.04 nvidia-smi` to verify GPU passthrough.

**Model loading fails:**
- Check that `runtime/models/000001/` contains `det_model.pt`, `seg_model.pt`, and `mmseg_config.py`.
