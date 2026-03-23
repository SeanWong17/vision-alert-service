# 部署说明

[中文](DEPLOYMENT.md) | [English](DEPLOYMENT.en.md)

## 1. 依赖安装
```bash
python3 -m pip install -r requirements.txt
```

如需真实分割推理，必须安装与当前 PyTorch / CUDA 匹配的 **full `mmcv`**：
```bash
python3 -m pip install -U openmim
mim install mmcv
```

注意事项：
- 仅安装 `mmsegmentation` 不够；真实图片请求会在运行期导入 `mmseg`，缺少 full `mmcv` 时会报 `No module named 'mmcv._ext'`。
- `mmcv-lite` 不能替代 full `mmcv` 完成当前模型推理链路。
- 当前 `Dockerfile` 已在镜像构建阶段通过 `openmim` 固化安装兼容的 full `mmcv`；非 Docker 部署仍需按上面命令手工安装。
- 当前依赖已将 `numpy` 固定为 `<2`，避免 `torch 2.1.x` / `mmcv 2.1.x` 在 NumPy 2.x 下出现 ABI 兼容告警或运行时异常。

## 2. 运行目录
创建运行目录：
```bash
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001
cp runtime/config.example.json runtime/config.json
```

目录说明：
- `runtime/log`
- `runtime/images/upload`
- `runtime/images/result`
- `runtime/models/<version>`
- `runtime/config.json`

模型目录下需有：
- `det_model.pt`
- `mmseg_config.py`
- `seg_model.pt`

快速下载轻量模型（人检 + 语义分割）：
```bash
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
```

如使用 ADE20K 预训练分割模型，请在 `runtime/config.json` 配置目标分割类别 ID（`[2]` 对应 ADE20K 的 `sky` 类别，仅作为演示默认值，实际部署时应替换为业务所需的类别 ID）：
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

说明：
- `segment_postprocess_class_names` 控制哪些检测类别会套用分割后处理，默认只包含 `person`。
- `in_segment_overlap_ratio` 控制 `enter_segment` 判定阈值；当前默认值为 `0.25`。
- 当检测框与目标分割区域存在正交集但尚未达到进入阈值时，会判为 `near_segment`。

## 3. Docker
Docker 文件在 `docker/` 目录（compose 文件名为 `docker-compose.yaml`）。
容器测试细化步骤见：`docs/CONTAINER_TEST.md`。

当前 Dockerfile 已内置以下运行时系统包：
- `libgl1`
- `libglib2.0-0`
- `libsm6`
- `libxrender1`
- `libxext6`
- `tzdata`

注意事项：
- `libgl1` 是当前镜像内 `import cv2` 所需的系统动态库；缺失时容器启动会报 `libGL.so.1`。
- 镜像默认时区已设为 `Asia/Shanghai`。
- Docker 构建阶段会额外安装兼容的 full `mmcv`，不再依赖容器启动后手工补装。

启动：
```bash
cd docker
docker compose up -d --build
```

容器映射：
- 容器 `/root/.vision_alert` -> 宿主 `runtime`

常用环境变量（可在 `docker-compose.yaml` 中配置）：

**推理设备**
- `ALERT_DET_DEVICE`：检测设备，容器内测试建议 `cpu`
- `ALERT_SEG_DEVICE`：分割设备，容器内测试建议 `cpu`

**文件管理**
- `ALERT_IMAGE_RETENTION_DAYS`：上传图与结果图保留天数，默认 `30`
- `ALERT_CLEANUP_SCAN_INTERVAL_SECONDS`：清理扫描周期（秒），默认 `3600`
- `ALERT_UPLOAD_MAX_BYTES`：单张上传最大字节数，默认 `20971520`（20MB）

**配置加载**
- `ALERT_CONFIG_STRICT`：配置文件加载失败是否阻止启动，默认 `true`

**日志**
- `ALERT_LOG_FORMAT`：日志输出格式，`json` 启用 JSON 结构化格式（适用于 ELK/Loki/CloudWatch），默认文本格式

## 4. 配置损坏恢复（严格模式）
默认 `ALERT_CONFIG_STRICT=true`，`runtime/config.json` 解析失败会阻止启动。

应急恢复步骤：
1. 临时将 `ALERT_CONFIG_STRICT=false` 启动服务，确保业务不中断。
2. 修复 `runtime/config.json` 后恢复 `ALERT_CONFIG_STRICT=true`。
3. 重启服务并确认配置已生效。

## 5. 启动参数

```bash
python3 main.py --host 0.0.0.0 --port 8011 --workers 4
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--host` | 监听地址 | `0.0.0.0` |
| `--port` | 监听端口 | `8011` |
| `--workers` | Uvicorn worker 进程数 | `1` |

> 注意：`--workers > 1` 时内存后端队列不跨进程共享，生产环境建议配合 Redis 使用。

服务启动时会自动预热模型（调用 `pipeline.warm_up()`），消除首次请求的冷启动延迟，冷启动耗时转移到进程启动阶段。

优雅停机：服务接收到 SIGTERM 后有 15 秒窗口处理已接受的请求，随后停止后台 worker 线程。

## 6. 生产运行建议
- 使用 `/healthz` 与 `/readyz` 作为存活/就绪探针。
- 采集 `/metrics` 到 Prometheus 并配置告警。
- 启用 `ALERT_LOG_FORMAT=json` 将日志对接 ELK/Loki 等日志聚合系统。
- 告警阈值、故障演练、容量基线见 `docs/OPERATIONS.md`。
