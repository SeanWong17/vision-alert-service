# AI Alerting Service

视觉告警服务：YOLO 目标检测 + MMSeg 语义分割，对指定类别的分割结果结合检测进行后处理，支持同步/异步双模式推理。

## 快速开始

```bash
python3 -m pip install -r requirements.txt
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001 runtime/license
cp runtime/config.example.json runtime/config.json
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
python3 main.py --host 0.0.0.0 --port 8011
```

## 文档导航

| 文档 | 说明 |
|------|------|
| [docs/API.md](docs/API.md) | HTTP 接口规范（请求/响应格式、字段说明） |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 部署配置、环境变量、Docker、License 授权 |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | 运维基线、Prometheus 监控面板、告警阈值 |
| [docs/CALL_CHAIN.md](docs/CALL_CHAIN.md) | 调用链与架构说明 |
| [docs/CONTAINER_TEST.md](docs/CONTAINER_TEST.md) | 容器 GPU 测试步骤 |
| [docs/PROTECTION.md](docs/PROTECTION.md) | 代码保护与授权机制 |

## 核心特性

- **双模推理**：异步上传入队（Redis Streams + 消费组），同步接口直接返回结果
- **模型预热**：启动时自动调用 `pipeline.warm_up()`，消除首次请求冷启动延迟（10-30s）
- **零磁盘同步推理**：`analyze_sync` 全程在内存中处理图片（`cv2.imdecode`），无磁盘 I/O
- **Redis 批量操作**：入队、保存结果、确认消费均使用 `pipeline` 批量发送，减少 RTT
- **Pydantic v2**：数据模型全面使用 v2 API（`model_dump`、`model_config`）
- **结构化日志**：设置 `ALERT_LOG_FORMAT=json` 启用 JSON 格式，适配 ELK/Loki/CloudWatch
- **推理性能指标**：`inference_duration_seconds` histogram（detection/segmentation/postprocess/total 四个 stage）
- **FastAPI DI**：路由使用 `Depends()` 注入服务依赖，测试通过 `dependency_overrides` 隔离

## 配置与授权

- 统一配置文件：`runtime/config.json`（可由 `runtime/config.example.json` 复制）
- 启动期授权校验：支持 license 到期、设备绑定、签名校验（见 `docs/DEPLOYMENT.md`）
- 可用性探针：`GET /healthz`（存活）与 `GET /readyz`（就绪）
- 追踪头：支持 `X-Request-ID` 透传，便于日志关联
- 指标导出：`GET /metrics`（Prometheus 文本格式）

## 关键环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `ALERT_LOG_FORMAT` | `json` 启用 JSON 结构化日志 | 文本格式 |
| `ALERT_DET_DEVICE` | 检测设备（`cpu`/`cuda:0`） | `cpu` |
| `ALERT_SEG_DEVICE` | 分割设备（`cpu`/`cuda:0`） | `cpu` |
| `ALERT_UPLOAD_MAX_BYTES` | 单张上传最大字节数 | `20971520`（20MB） |
| `ALERT_IMAGE_RETENTION_DAYS` | 图片保留天数 | `30` |
| `ALERT_LICENSE_ENABLED` | 启用 license 校验 | `false` |

完整变量列表见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## 目录概览

```text
app/
  common/      # 配置、日志（JSON格式）、异常（ErrorCode枚举）、指标
  adapters/    # Redis / 模型适配器
  alerting/    # 业务编排层（service、store、pipeline、worker）
  http/        # 路由层（FastAPI Depends注入）
  application.py
main.py
tests/         # 单元测试 + 集成测试（148+ 个测试用例）
scripts/       # 手动脚本（模型安装、API 烟雾测试、CI 门控）
docs/          # 文档
docker/        # 多阶段 Dockerfile + compose（含 healthcheck）
runtime/       # 本地运行目录骨架（gitignored）
pyproject.toml # 项目元数据、ruff/mypy/pytest 配置
```

## 开发与测试

```bash
# 安装 CI 依赖
pip install -r requirements-ci.txt

# 运行全部测试
pytest

# 代码检查
ruff check app tests scripts
ruff format --check app tests scripts
```

CI 使用 GitHub Actions，覆盖 Python 3.10 / 3.11 / 3.12 三个版本，并含 ruff lint 和 Docker build 验证。
