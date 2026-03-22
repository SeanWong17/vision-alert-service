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
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001 runtime/license
cp runtime/config.example.json runtime/config.json
```

目录说明：
- `runtime/log`
- `runtime/images/upload`
- `runtime/images/result`
- `runtime/models/<version>`
- `runtime/config.json`
- `runtime/license`

模型目录下需有：
- `det_model.pt`
- `mmseg_config.py`
- `seg_model.pt`

快速下载轻量模型（人检 + 水面分割）：
```bash
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
```

如使用 ADE20K 预训练分割模型，请在 `runtime/config.json` 配置：
```json
{
  "alert": {
    "segmentor_water_class_ids": [21]
  }
}
```

## 3. Docker
Docker 文件在 `docker/` 目录（compose 文件名为 `docker-compose.yaml`）。
容器测试细化步骤见：`docs/CONTAINER_TEST.md`。

启动：
```bash
cd docker
docker compose up -d --build
```

容器映射：
- 容器 `/root/.ai_alerting` -> 宿主 `runtime`

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

**授权**
- `ALERT_LICENSE_ENABLED`：是否启用 license 校验，默认 `false`
- `ALERT_LICENSE_PATH`：license 文件路径
- `ALERT_LICENSE_PUBLIC_KEY_PATH`：Ed25519 公钥路径（不设则使用内置公钥）
- `ALERT_LICENSE_ALLOW_HOSTNAME_FALLBACK`：machine-id 不可读时是否回退 hostname，默认 `false`
- `ALERT_LICENSE_CHECK_INTERVAL_SECONDS`：运行期 license 复查间隔（秒），默认 `300`

受保护构建（PyArmor）：
```bash
./scripts/build_protected_image.sh ai_alerting:protected
docker run -d --name ai_alerting_service \
  -p 8011:8011 \
  -v "$(pwd)/runtime:/root/.ai_alerting" \
  ai_alerting:protected
```

## 4. License（到期 + 设备绑定 + 签名）
生成密钥对：
```bash
python3 scripts/license_tool.py gen-key \
  --private-key runtime/license/private_key.pem \
  --public-key runtime/license/public_key.pem
```

读取机器 ID（Linux）：
```bash
cat /etc/machine-id
```

签发 license：
```bash
python3 scripts/license_tool.py sign \
  --private-key runtime/license/private_key.pem \
  --subject customer_a \
  --machine-id "$(cat /etc/machine-id)" \
  --expires-at 2027-12-31T23:59:59Z \
  --output runtime/license/license.json
```

启用校验（compose 环境变量）：
```yaml
ALERT_LICENSE_ENABLED: "true"
ALERT_LICENSE_PATH: /root/.ai_alerting/license/license.json
ALERT_LICENSE_PUBLIC_KEY_PATH: /root/.ai_alerting/license/public_key.pem
ALERT_LICENSE_ALLOW_HOSTNAME_FALLBACK: "false"
```

说明：
- `docker-compose` 只能编排和传配置，无法单独实现“代码加密”。
- 代码保护需在镜像构建阶段完成（如 `Dockerfile.protected` 的 PyArmor 流程）。
- 更详细的威胁模型、流程和运维建议见：`docs/PROTECTION.md`。

## 5. 配置损坏恢复（严格模式）
默认 `ALERT_CONFIG_STRICT=true`，`runtime/config.json` 解析失败会阻止启动。

应急恢复步骤：
1. 临时将 `ALERT_CONFIG_STRICT=false` 启动服务，确保业务不中断。
2. 修复 `runtime/config.json` 后恢复 `ALERT_CONFIG_STRICT=true`。
3. 重启服务并确认配置已生效。

## 6. 启动参数

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

## 7. 生产运行建议
- 使用 `/healthz` 与 `/readyz` 作为存活/就绪探针。
- 采集 `/metrics` 到 Prometheus 并配置告警。
- 启用 `ALERT_LOG_FORMAT=json` 将日志对接 ELK/Loki 等日志聚合系统。
- 告警阈值、故障演练、容量基线见 `docs/OPERATIONS.md`。
