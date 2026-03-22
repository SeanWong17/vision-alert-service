"""本地烟雾测试脚本：覆盖同步与异步接口。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time

import requests


def build_url(host: str, port: int, path: str) -> str:
    """拼接请求 URL。"""

    return f"http://{host}:{port}{path}"


def guess_mime_type(image_path: str) -> str:
    """根据文件后缀推断上传 MIME 类型。"""

    mime_type, _ = mimetypes.guess_type(image_path)
    return mime_type or "application/octet-stream"


def run_sync(host: str, port: int, image_path: str) -> None:
    """执行同步接口调用并打印结果。"""

    url = build_url(host, port, "/api/analysis/danger")
    mime_type = guess_mime_type(image_path)
    with open(image_path, "rb") as fp:
        files = {"image": (image_path, fp, mime_type)}
        data = {
            "file_name": image_path.split("/")[-1],
            "tasks": json.dumps(
                [
                    {
                        "id": 1,
                        "params": {
                            "limit": 0,
                            "rois": [
                                {
                                    "roiId": "full-image",
                                    "coordinate": [-1, -1, -1, -1],
                                    "classes": [],
                                    "confThreshold": 0.5,
                                }
                            ],
                        },
                    }
                ]
            ),
        }
        response = requests.post(url, files=files, data=data, timeout=30)
    response.raise_for_status()
    print("[sync]", response.json())


def run_async(host: str, port: int, image_path: str) -> None:
    """执行异步上传、拉取与确认全流程。"""

    session_id = f"SMOKE_{int(time.time())}"
    upload_url = build_url(host, port, "/api/transmission/upload")
    mime_type = guess_mime_type(image_path)

    with open(image_path, "rb") as fp:
        files = {"file": (image_path, fp, mime_type)}
        data = {
            "FileUpload": json.dumps({"filename": image_path.split("/")[-1], "sessionId": session_id}),
            "tasks": json.dumps(
                [
                    {
                        "id": 1,
                        "params": {
                            "limit": 0,
                            "rois": [
                                {
                                    "roiId": "full-image",
                                    "coordinate": [-1, -1, -1, -1],
                                    "classes": [],
                                    "confThreshold": 0.5,
                                }
                            ],
                        },
                    }
                ]
            ),
        }
        upload_res = requests.post(upload_url, files=files, data=data, timeout=30)
    upload_res.raise_for_status()
    print("[async upload]", upload_res.json())

    pull_url = build_url(host, port, "/api/transmission/alarm_result")
    confirm_url = build_url(host, port, "/api/transmission/result_confirm")

    image_ids = []
    for _ in range(30):
        pull_res = requests.get(pull_url, params={"sessionId": session_id}, timeout=15)
        pull_res.raise_for_status()
        payload = pull_res.json()
        items = payload.get("items", [])
        if items:
            print("[async result]", payload)
            image_ids = [item.get("imageId") for item in items if item.get("imageId")]
            break
        time.sleep(1)

    confirm_payload = {"sessionId": session_id, "imageIds": image_ids}
    confirm_res = requests.post(confirm_url, json=confirm_payload, timeout=15)
    confirm_res.raise_for_status()
    print("[async confirm]", confirm_res.json())


def main() -> None:
    """解析命令行参数并执行 smoke 流程。"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8011, type=int)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    run_sync(args.host, args.port, args.image)
    run_async(args.host, args.port, args.image)


if __name__ == "__main__":
    main()
