# 部署说明

## 1. 依赖安装
```bash
python3 -m pip install -r requirements.txt
```

如需 mmcv：
```bash
python3 -m pip install -U openmim
mim install "mmcv==2.0.0rc4"
```

## 2. 运行目录
创建运行目录：
```bash
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001
```

目录说明：
- `runtime/log`
- `runtime/images/upload`
- `runtime/images/result`
- `runtime/models/<version>`

模型目录下需有：
- `det_model.pt`
- `mmseg_config.py`
- `seg_model.pt`

## 3. Docker
Docker 文件在 `docker/` 目录（compose 文件名为 `docker-compose.yaml`）。

启动：
```bash
cd docker
docker compose up -d --build
```

容器映射：
- 容器 `/root/.ai_alerting` -> 宿主 `runtime`
