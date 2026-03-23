# Vision Alert Service

[中文](README.md) | [English](README.en.md)

A vision-based alerting service that delivers dual-mode inference — synchronous and asynchronous — for "zone intrusion / dangerous area proximity" scenarios, powered by YOLO object detection and MMSeg semantic segmentation.

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

![Vision Alert Service demo](docs/assets/demo-alert-result.png)

The image above shows a typical output from this service: it first runs object detection, then applies semantic segmentation masks to perform domain-specific post-processing on configured classes — labeling targets as `enter_segment` or `near_segment` rather than returning plain bounding boxes.

## What This Project Is

This is a production-oriented computer vision backend service, not a standalone model inference script. It integrates a detection model, a segmentation model, an HTTP API, an async queue, a result store, and operational metrics into a single deployable service — and translates raw model outputs into business semantics (zone entry, proximity alerts, result confirmation, and retrieval).

## Highlights

- **Dual-mode inference**: supports both synchronous analysis and asynchronous upload-and-queue
- **Detection + segmentation coupling**: not just object detection — "semantic enrichment of detection results"
- **Business-level alert labels**: outputs `enter_segment` / `near_segment` based on mask overlap ratio and distance
- **Zero-disk synchronous inference**: the sync endpoint resolves images entirely in memory, minimizing I/O
- **Async consumption pipeline**: Redis Streams + worker consumer thread + result confirmation flow
- **Structured observability**: `X-Request-ID` propagation, JSON logging, Prometheus metrics
- **Open-source collaboration ready**: includes contributing guide, security policy, code of conduct, and GitHub templates
- **Containerized delivery**: multi-stage Dockerfile with runtime and test dependencies separated

## What Problem This Solves

Many computer vision projects stall at two points in real-world deployment:

1. The model only runs offline demos and cannot serve requests reliably
2. Detection results are too "raw" to map directly onto business semantics

This project targets the second class of "last-mile engineering problems":

- Input: an image and a set of task rules
- The detection model finds targets
- The segmentation model identifies the target zone
- Business post-processing converts target-to-zone relationships into alert labels
- The server returns normalized results either synchronously or asynchronously

## Demo Image Explained

From the result image above:

- `enter_segment`: a detected target has reached the entry threshold with respect to the segmented zone
- `near_segment`: a detected target has not fully entered the zone, but overlaps it or is sufficiently close
- Other targets retain their original detection class, such as `dog`, `bench`, `bottle`

This means the system output is no longer simply "a person was detected," but rather "what is the business relationship between this person and the target zone."

## System Architecture

```text
Client
  -> FastAPI HTTP layer
    -> AlertService
      -> AlertPipeline
        -> Detector (YOLO)
        -> Segmentor (MMSeg)
      -> AlertStore
        -> Memory / Redis
      -> AlertWorker
        -> Async task consumption
```

The call chain has clearly separated responsibilities:

- `app/http`: handles parameter intake, dependency injection, and response serialization only
- `app/alerting/service.py`: business orchestration, upload persistence, sync/async flow control
- `app/alerting/pipeline.py`: detection, segmentation, result post-processing, and result image rendering
- `app/alerting/store.py`: queue, pending, result, and confirmation logic
- `app/alerting/worker.py`: background consumer thread and concurrency control
- `app/common`: configuration, logging, error codes, metrics
- `app/adapters`: Redis and vision model adapter layer

## Core Capabilities

### 1. Visual Inference and Business Post-Processing

- The detection model produces bounding boxes and class labels
- The segmentation model outputs a full-image mask
- `segmentor_target_class_ids` in config controls which segmentation classes are monitored
- `segment_postprocess_class_names` in config controls which detection classes participate in post-processing
- Outputs `enter_segment` / `near_segment` based on mask overlap ratio and minimum distance

### 2. Server Engineering Design

- FastAPI application factory pattern with unified middleware, exception handler, and lifespan registration
- Sync endpoint returns immediately; async endpoint supports upload, enqueue, result polling, and result confirmation
- Worker supports configurable concurrency and inflight cap to prevent unbounded background consumption
- Store is compatible with both in-memory mode and Redis mode for easy local development and production switching

### 3. Observability and Stability

- `GET /healthz`: process liveness probe
- `GET /readyz`: readiness probe including worker / Redis / queue status
- `GET /metrics`: Prometheus metrics export
- Request latency, inference duration, queue depth, and dead-letter size are all observable
- `ALERT_LOG_FORMAT=json` enables structured JSON logging
- `X-Request-ID` passthrough for log and request correlation

### 4. Engineering Quality

- Pydantic v2 configuration and models
- Explicit error model with typed business exception wrappers
- Unit tests, integration tests, and CI gate script
- Docker multi-stage build
- README, deployment docs, operations docs, and contributing docs kept separate

## Quick Start

### Local Run

```bash
python3 -m pip install -r requirements.txt
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001
cp runtime/config.example.json runtime/config.json
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
python3 main.py --host 0.0.0.0 --port 8011
```

After startup, the following endpoints are available by default:

- `http://127.0.0.1:8011/docs`
- `http://127.0.0.1:8011/healthz`
- `http://127.0.0.1:8011/readyz`
- `http://127.0.0.1:8011/metrics`

### Docker Run

```bash
cd docker
docker compose up -d --build
```

The container mounts:

- Host `runtime/`
- Container `/root/.vision_alert`

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs/upload` | `POST` | Upload image asynchronously and enqueue |
| `/api/jobs/alarm_result` | `GET` | Poll async alert results |
| `/api/jobs/result_confirm` | `POST` | Confirm and clean up results |
| `/api/analysis/danger` | `POST` | Synchronous inference, returns result immediately |
| `/healthz` | `GET` | Liveness probe |
| `/readyz` | `GET` | Readiness probe |
| `/metrics` | `GET` | Prometheus metrics |

For full request/response field documentation, see [docs/API.en.md](docs/API.en.md).

## Post-Processing Strategy

- Object detection runs first, then semantic segmentation is applied to the full image; masks corresponding to `alert.segmentor_target_class_ids` are extracted
- Segmentation post-processing is applied only to detection classes listed in `alert.segment_postprocess_class_names`
- If the detection box overlaps the target mask by `overlapSegment >= alert.in_segment_overlap_ratio`, it is labeled `enter_segment`
- If the detection box intersects the target mask but does not reach the entry threshold, or if the center-to-nearest-mask-boundary distance `distanceToSegment <= alert.near_segment_distance_px`, it is labeled `near_segment`
- All other detected targets retain their original `tagName`

Default thresholds are intentionally conservative; adjust them based on false positive / false negative rates for your deployment.

## Tech Stack

- **Web**: FastAPI, Starlette, Uvicorn
- **Configuration and models**: Pydantic v2
- **Visual inference**: PyTorch, Ultralytics, MMEngine, MMSegmentation, MMCV
- **Image processing**: OpenCV
- **Async result storage**: Redis
- **Quality assurance**: pytest, unittest, Ruff
- **Delivery**: Docker, Docker Compose, GitHub Actions

## Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ALERT_LOG_FORMAT` | Set to `json` to enable structured JSON logging | plain text |
| `ALERT_DET_DEVICE` | Detection device (`cpu` / `cuda:0`) | `cpu` |
| `ALERT_SEG_DEVICE` | Segmentation device (`cpu` / `cuda:0`) | `cpu` |
| `ALERT_UPLOAD_MAX_BYTES` | Maximum upload size per image in bytes | `20971520` |
| `ALERT_IMAGE_RETENTION_DAYS` | Number of days to retain uploaded images | `30` |
| `ALERT_WORKER_THREADS` | Number of background worker threads | `4` |
| `ALERT_WORKER_MAX_INFLIGHT` | Maximum number of concurrently in-flight tasks | `64` |

For complete configuration and deployment details, see [docs/DEPLOYMENT.en.md](docs/DEPLOYMENT.en.md).

## Project Structure

```text
app/
  common/      # config, logging, exceptions, metrics
  adapters/    # Redis / model adapters
  alerting/    # service, pipeline, store, worker, schema
  http/        # API routes
  application.py
main.py
tests/
scripts/
docs/
docker/
runtime/
```

## Development and Testing

```bash
# Install CI dependencies
python3 -m pip install -r requirements-ci.txt

# Run tests
python3 scripts/ci_unittest_gate.py
pytest

# Lint and format
ruff check app tests scripts
ruff format --check app tests scripts

# Build test image
docker build -f docker/Dockerfile --target test -t vision-alert:test .
docker run --rm -v "$(pwd)/runtime:/root/.vision_alert" vision-alert:test
```

Engineering coverage includes:

- CI gate script that prevents "zero tests discovered" or mass-skip scenarios
- HTTP routes, worker lifecycle, config loading, metrics, and service/store/pipeline tests
- Runtime and test dependencies cleanly separated in Docker

## Documentation

| Document | Description |
|----------|-------------|
| [docs/API.en.md](docs/API.en.md) | HTTP API specification |
| [docs/DEPLOYMENT.en.md](docs/DEPLOYMENT.en.md) | Deployment config, environment variables, Docker |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Operations baseline, Prometheus dashboards, alert thresholds |
| [docs/CALL_CHAIN.en.md](docs/CALL_CHAIN.en.md) | Call chain and architecture walkthrough |
| [docs/CONTAINER_TEST.md](docs/CONTAINER_TEST.md) | Container GPU test procedure |
| [CONTRIBUTING.en.md](CONTRIBUTING.en.md) | Contribution workflow, pre-commit checks, PR conventions |
| [SECURITY.en.md](SECURITY.en.md) | Vulnerability reporting and security disclosure process |
| [CODE_OF_CONDUCT.en.md](CODE_OF_CONDUCT.en.md) | Community conduct baseline |

## Open-Source Collaboration

- Before contributing, read [CONTRIBUTING.en.md](CONTRIBUTING.en.md)
- For security issues, refer to [SECURITY.en.md](SECURITY.en.md)
- Community conduct guidelines are in [CODE_OF_CONDUCT.en.md](CODE_OF_CONDUCT.en.md)

## License

This project is licensed under [CC BY-NC 4.0](LICENSE). **Commercial use of any kind is prohibited.**
