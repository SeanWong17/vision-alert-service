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

先运行容器内单元测试：

```bash
cd docker
docker compose --profile test build ai_alerting_test
docker compose --profile test run --rm ai_alerting_test
```

如果只想直接构建测试镜像，也可以在仓库根目录执行：

```bash
docker build -f docker/Dockerfile --target test -t ai-alerting:test .
docker run --rm -v "$(pwd)/runtime:/root/.ai_alerting" ai-alerting:test
```

说明：
- 测试镜像已经包含 `pytest`；如容器内出现 `No module named pytest`，说明测试依赖镜像未按最新配置重建。

单元测试通过后，再启动服务容器：

```bash
cd docker
docker compose up -d --build
```

## 3. 启动容器（GPU）

前置条件：

- 已安装 NVIDIA 驱动
- 已安装 `nvidia-container-toolkit`
- `docker info` 可见 NVIDIA runtime

启动前，先编辑 `docker/docker-compose.yaml`，取消注释 GPU 相关的环境变量和 `deploy.resources.devices` 配置，然后执行：

```bash
cd docker
docker compose up -d --build
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

重要说明：
- `/healthz` 和 `/readyz` 通过，只代表 Web 服务、worker 和 Redis 链路正常，不代表真实模型推理依赖已经闭合。
- 当前 `Dockerfile` 已在镜像构建阶段固化安装兼容的 full `mmcv`。
- 当前运行镜像已将 `numpy` 固定为 `<2`，避免 `torch 2.1.x` / `mmcv 2.1.x` 在 NumPy 2.x 下出现 ABI 兼容告警。
- 如果镜像内仍然出现 `mmcv._ext` 缺失，说明 full `mmcv` 安装阶段失败或被替换成了 `mmcv-lite`。

## 6. 常见排查

- 容器启动时报 `libGL.so.1`：
  - 说明 OpenCV 运行库不完整；镜像需包含 `libgl1`。
- 分割结果全空：
  - 确认 `runtime/config.json` 里 `alert.segmentor_target_class_ids` 包含目标分割类别 ID。预训练模型默认使用 ADE20K 数据集，`[2]` 对应 `sky` 类别，仅作为开箱即用的演示值；实际部署时应替换为业务所需的类别 ID。
- 真实图片请求报 `No module named 'mmcv._ext'`：
  - 说明当前只有 `mmcv-lite`，或 Docker 构建阶段的 full `mmcv` 安装失败。
  - 优先检查镜像构建日志中的 `python -m mim install "mmcv==..."` 步骤。
- 真实图片请求在 `mmseg` 导入阶段报 `ftfy` / `regex` 缺失：
  - 这是 `mmseg` 文本/Tokenizer 相关依赖未装齐的表现。
  - 当前这两个包已同步加入 `requirements.txt`。
- 容器日志出现 `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x`：
  - 说明 `torch/mmcv` 与 NumPy 主版本不兼容。
  - 当前依赖已固定为 `numpy<2`；如果仍看到该告警，说明镜像未按最新依赖重建。
- 容器内 CUDA 不可用：
  - 先在宿主机执行 `nvidia-smi`。
  - 再执行 `docker run --rm --gpus all nvidia/cuda:12.3.2-runtime-ubuntu22.04 nvidia-smi`。
- 模型加载失败：
  - 检查 `runtime/models/000001/` 下是否有 `det_model.pt`、`seg_model.pt`、`mmseg_config.py`。
