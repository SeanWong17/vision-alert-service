# API Reference

[中文](API.md) | [English](API.en.md)

Base URL: `http://{host}:8011/api`

General notes:
- Clients are encouraged to send an `X-Request-ID` header; the service echoes it back in the response header. If omitted, the service generates one automatically.
- All error responses include a `requestId` field for log correlation.

## 1. Async Upload

- Method: `POST /jobs/upload`
- Content-Type: `multipart/form-data`
- Fields:
  - `file`: image file
  - `FileUpload`: JSON string containing `filename` and `sessionId`
  - `tasks`: JSON string supporting multiple ROI rules

Request example:
```json
{
  "tasks": [
    {
      "id": 1,
      "params": {
        "limit": 0,
        "rois": [
          {
            "roiId": "roi-1",
            "coordinate": [100, 100, 600, 600],
            "classes": ["person", "car"],
            "confThreshold": 0.65
          },
          {
            "roiId": "full",
            "coordinate": [-1, -1, -1, -1],
            "classes": [],
            "confThreshold": 0.5
          }
        ]
      }
    }
  ]
}
```

Notes:
- `coordinate=[-1,-1,-1,-1]` or omitting `rois` defaults to the full image.
- `classes=[]` means all classes.
- `confThreshold`: alert confidence threshold for this ROI.

Response example:
```json
{"code":0,"message":"Success","sessionId":"S001","imageId":"..."}
```

## 2. Async Result Poll

- Method: `GET /jobs/alarm_result?sessionId=S001`
- Response example:
```json
{
  "code": 0,
  "message": "Success",
  "hasMore": false,
  "items": [
    {
      "imageId": "...",
      "filename": "cam_1.jpg",
      "results": [
        {
          "id": 1,
          "reserved": "1",
          "detail": {
            "roiResults": [
              {
                "roiId": "roi-1",
                "coordinate": [100, 100, 600, 600],
                "classes": ["person", "car"],
                "confThreshold": 0.65,
                "targetCount": 2,
                "alertClasses": ["car", "person"],
                "targets": [
                  {
                    "coordinate": [120, 120, 180, 220],
                    "score": 0.91,
                    "tagName": "person",
                    "alarmTag": "enter_segment",
                    "overlapSegment": 0.12,
                    "distanceToSegment": 3.8
                  }
                ]
              }
            ]
          }
        }
      ],
      "timestamp": 1700000000000
    }
  ]
}
```

Detection box field reference:

| Field | Type | Description |
|-------|------|-------------|
| `coordinate` | `[x1,y1,x2,y2]` | Bounding box coordinates |
| `score` | float | Detection confidence |
| `tagName` | string | Raw class name from the model |
| `alarmTag` | string | Post-processed alert label (e.g., `enter_segment`, `near_segment`) |
| `overlapSegment` | float | Overlap ratio between the bounding box and the segmented zone (0–1) |
| `distanceToSegment` | float | Pixel distance from the bounding box center to the nearest boundary of the segmented zone |

`alarmTag` rules:
- Applies only to detection classes listed in `alert.segment_postprocess_class_names`; defaults to `person` only
- `enter_segment`: bounding box overlap with the segmented zone >= threshold (`in_segment_overlap_ratio`)
- `near_segment`: bounding box intersects the segmented zone but does not reach the entry threshold, or there is no intersection but the center-to-boundary distance <= threshold (`near_segment_distance_px`)
- If neither post-processing rule is matched: the original `tagName` is used

## 3. Async Result Confirmation

- Method: `POST /jobs/result_confirm`
- Content-Type: `application/json`
- Request body:
```json
{"sessionId":"S001","imageIds":["..."]}
```
- Response example:
```json
{"code":0,"message":"Success","confirmed":1}
```

## 4. Synchronous Analysis

- Method: `POST /analysis/danger`
- Content-Type: `multipart/form-data`
- Fields:
  - `image`: image file
  - `file_name`: filename
  - `tasks`: same structure as async upload (supports multiple ROIs)
- Response: an array of task results with the same structure as the async `results` field.

## 5. Liveness Probe

- Method: `GET /healthz` (note: no `/api` prefix)
- Response example:
```json
{"status":"ok","timestamp":1700000000000}
```

## 6. Readiness Probe

- Method: `GET /readyz` (note: no `/api` prefix)
- Response example:
```json
{
  "status":"ready",
  "workerRunning":true,
  "inflightTasks":0,
  "storageMode":"redis",
  "redisOk":true,
  "queueLength":0,
  "timestamp":1700000000000
}
```

## 7. Metrics Export

- Method: `GET /metrics` (note: no `/api` prefix)
- Format: Prometheus exposition text
- Covered metrics:

| Metric name | Type | Description |
|-------------|------|-------------|
| `http_requests_total` | Counter | Grouped by `path`, `method`, `status` |
| `http_request_duration_seconds` | Histogram | End-to-end request latency in seconds |
| `async_tasks_total` | Counter | Grouped by `outcome` (`success` / `failure`) |
| `alert_queue_length` | Gauge | Current pending queue depth |
| `alert_worker_inflight` | Gauge | Number of concurrently in-flight inference tasks |
| `alert_dead_letter_size` | Gauge | Dead-letter queue size |
| `inference_duration_seconds` | Histogram | Per-stage inference duration, grouped by `stage` (`detection` / `segmentation` / `postprocess` / `total`) |
