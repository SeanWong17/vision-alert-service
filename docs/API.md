# API 接口文档

Base URL: `http://{host}:8011/api`

## 1. 异步上传
- 方法：`POST /transmission/upload`
- Content-Type：`multipart/form-data`
- 字段：
  - `file`：图片文件
  - `FileUpload`：JSON 字符串，含 `filename`、`sessionId`
  - `tasks`：JSON 字符串，建议结构：
    ```json
    {
      "tasks": [
        {"id": 1, "params": {"limit": 0, "coordinate": [-1, -1, -1, -1]}}
      ]
    }
    ```
- 返回示例：
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
        "results": [...],
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
  - `tasks`：JSON 字符串（同异步）
- 返回：任务结果数组。
