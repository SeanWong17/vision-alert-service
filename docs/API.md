# API 接口文档

Base URL: `http://{host}:8011/api`

公共说明：
- 建议客户端传入 `X-Request-ID`，服务会在响应头原样返回；未传时服务自动生成。
- 所有错误响应包含 `requestId` 字段，便于日志检索。

## 1. 异步上传
- 方法：`POST /transmission/upload`
- Content-Type：`multipart/form-data`
- 字段：
  - `file`：图片文件
  - `FileUpload`：JSON 字符串，含 `filename`、`sessionId`
  - `tasks`：JSON 字符串，支持多 ROI 规则。

请求示例：
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

说明：
- `coordinate=[-1,-1,-1,-1]` 或不传 `rois`：默认全图。
- `classes=[]`：表示全类别。
- `confThreshold`：该 ROI 的告警置信度阈值。

返回示例：
```json
{"code":0,"message":"Success","sessionId":"S001","imageId":"..."}
```

## 2. 异步结果拉取
- 方法：`GET /transmission/alarm_result?sessionId=S001`
- 返回示例：
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

检测框字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `coordinate` | `[x1,y1,x2,y2]` | 检测框坐标 |
| `score` | float | 检测置信度 |
| `tagName` | string | 模型原始类别名 |
| `alarmTag` | string | 后处理告警标签（如 `enter_segment`、`near_segment`） |
| `overlapSegment` | float | 检测框与分割区域的重叠比例（0~1） |
| `distanceToSegment` | float | 检测框中心到最近分割区域边界的像素距离 |

`alarmTag` 规则：
- 仅对 `alert.segment_postprocess_class_names` 中配置的检测类别生效，默认只处理 `person`
- `enter_segment`：检测框与分割区域重叠比例 ≥ 阈值（`in_segment_overlap_ratio`）
- `near_segment`：中心距分割区域边界 ≤ 阈值（`near_segment_distance_px`）
- 未命中后处理规则时：沿用原始 `tagName`

## 3. 异步结果确认
- 方法：`POST /transmission/result_confirm`
- Content-Type：`application/json`
- 请求体：
```json
{"sessionId":"S001","imageIds":["..."]}
```
- 返回示例：
```json
{"code":0,"message":"Success","confirmed":1}
```

## 4. 同步分析
- 方法：`POST /analysis/danger`
- Content-Type：`multipart/form-data`
- 字段：
  - `image`：图片文件
  - `file_name`：文件名
  - `tasks`：与异步上传同结构（支持多 ROI）
- 返回：任务结果数组，结构与异步 `results` 一致。

## 5. 存活探针
- 方法：`GET /healthz`（注意：不带 `/api` 前缀）
- 返回示例：
```json
{"status":"ok","timestamp":1700000000000}
```

## 6. 就绪探针
- 方法：`GET /readyz`（注意：不带 `/api` 前缀）
- 返回示例：
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

## 7. 指标导出
- 方法：`GET /metrics`（注意：不带 `/api` 前缀）
- 格式：Prometheus exposition text
- 覆盖指标：

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `http_requests_total` | Counter | 按 `path`、`method`、`status` 分组 |
| `http_request_duration_seconds` | Histogram | 请求端到端延迟（秒） |
| `async_tasks_total` | Counter | 按 `outcome`（`success`/`failure`）分组 |
| `alert_queue_length` | Gauge | 当前待处理队列深度 |
| `alert_worker_inflight` | Gauge | 正在推理的并发任务数 |
| `alert_dead_letter_size` | Gauge | 死信队列大小 |
| `inference_duration_seconds` | Histogram | 推理各阶段耗时，按 `stage` 分组（`detection`/`segmentation`/`postprocess`/`total`） |
