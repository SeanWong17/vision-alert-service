# 容器启动与测试说明

本文档用于“本机有 GPU，不使用 conda，直接用容器测试”的场景。

## 1. 准备模型与配置

在仓库根目录执行：

```bash
cp runtime/config.example.json runtime/config.json
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
```

默认将安装一套轻量模型到 `runtime/models/000001`：

- 人检：`yolo11n`
- 语义分割：`segformer_mit-b0_ade20k`

## 2. 启动容器（CPU）

```bash
cd docker
docker compose up -d --build
```

## 3. 启动容器（GPU）

前置条件：

- 已安装 NVIDIA 驱动
- 已安装 `nvidia-container-toolkit`
- `docker info` 可见 NVIDIA runtime

启动命令（叠加 GPU 覆盖配置）：

```bash
cd docker
docker compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d --build
```

## 4. 健康检查

```bash
curl -s http://127.0.0.1:8011/healthz
curl -s http://127.0.0.1:8011/readyz
```

## 5. 接口烟雾测试

准备一张本地图片后执行：

```bash
python3 scripts/smoke_api.py --host 127.0.0.1 --port 8011 --image /abs/path/to/test.jpg
```

## 6. 常见排查

- 分割结果全空：
  - 确认 `runtime/config.json` 里 `alert.segmentor_target_class_ids` 为 `[21]`（ADE20K 类别 ID）。
- 容器内 CUDA 不可用：
  - 先在宿主机执行 `nvidia-smi`。
  - 再执行 `docker run --rm --gpus all nvidia/cuda:12.3.2-runtime-ubuntu22.04 nvidia-smi`。
- 模型加载失败：
  - 检查 `runtime/models/000001/` 下是否有 `det_model.pt`、`seg_model.pt`、`mmseg_config.py`。
