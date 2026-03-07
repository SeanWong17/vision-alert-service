# 部署说明

## 1. 依赖安装
```bash
cd ai_service
python3 -m pip install -r requirements.txt
```

如需 mmcv：
```bash
python3 -m pip install -U openmim
mim install "mmcv==2.0.0rc4"
```

## 2. 运行目录
先初始化：
```bash
./scripts/init_runtime_dirs.sh
```

目录为：`runtime/app_data`，包含：
- `log/`
- `images/upload/`
- `images/result/`
- `models/<version>/`

模型目录下需有：
- `det_model.pt`
- `mmseg_config.py`
- `seg_model.pt`

## 3. Docker
Docker 相关文件在仓库 `docker/` 目录。

启动：
```bash
cd docker
docker compose up -d --build
```

容器目录映射：
- 容器 `/root/.ai_alerting` -> 宿主 `ai_service/runtime/app_data`
