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
                    "overlapWater": 0.12,
                    "distanceToWater": 3.8
                  }
                ]
              }
            ],
            "waterColor": {"water_ratio": 0.33},
            "shorelinePoints": [[1, 2], [3, 4]]
          }
        }
      ],
      "timestamp": 1700000000000
    }
  ]
}
```

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
  "licenseOk":true,
  "queueLength":0,
  "timestamp":1700000000000
}
```

## 7. 指标导出
- 方法：`GET /metrics`（注意：不带 `/api` 前缀）
- 格式：Prometheus exposition text
- 覆盖指标（当前）：
  - `http_requests_total`
  - `http_request_duration_seconds`（histogram）
  - `async_tasks_total`
  - `alert_queue_length`
  - `alert_worker_inflight`
  - `alert_dead_letter_size`
