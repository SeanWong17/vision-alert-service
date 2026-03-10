# AI Alerting Service

该仓库提供“检测 + 分割 + 告警后处理”的同步/异步服务。

## 快速开始
```bash
python3 -m pip install -r requirements.txt
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001 runtime/license
cp runtime/config.example.json runtime/config.json
python3 scripts/install_light_models.py --model-root runtime/models --packs nano-v11-b0
python3 main.py --host 0.0.0.0 --port 8011
```

## 文档导航
- 架构与调用链：`docs/CALL_CHAIN.md`
- API 接口文档：`docs/API.md`
- 部署与 Docker：`docs/DEPLOYMENT.md`
- 容器启动与测试：`docs/CONTAINER_TEST.md`
- 运行与运维基线：`docs/OPERATIONS.md`
- 代码保护与授权：`docs/PROTECTION.md`

## 配置与授权
- 统一配置文件：`runtime/config.json`（可由 `runtime/config.example.json` 复制）
- 启动期授权校验：支持 license 到期、设备绑定、签名校验（见 `docs/DEPLOYMENT.md`）
- 可用性探针：`GET /healthz`（存活）与 `GET /readyz`（就绪）
- 追踪头：支持 `X-Request-ID` 透传，便于日志关联
- 指标导出：`GET /metrics`（Prometheus 文本格式）

## 目录概览
```text
app/
  common/      # 配置、日志、异常
  adapters/    # Redis/模型适配器
  alerting/    # 业务编排层
  http/        # 路由层
  application.py
  main.py
tests/         # 单元测试、集成测试
scripts/       # 手动脚本（如 API 烟雾测试）
docs/          # 文档
docker/        # Dockerfile 与 compose
runtime/       # 本地运行目录骨架
```
