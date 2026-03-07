# AI Alerting Service

该仓库提供“检测 + 分割 + 告警后处理”的同步/异步服务。

## 快速开始
```bash
python3 -m pip install -r requirements.txt
mkdir -p runtime/log runtime/images/upload runtime/images/result runtime/models/000001
python3 main.py --host 0.0.0.0 --port 8011
```

## 文档导航
- 架构与调用链：`docs/CALL_CHAIN.md`
- API 接口文档：`docs/API.md`
- 部署与 Docker：`docs/DEPLOYMENT.md`

## 目录概览
```text
app/
  common/      # 配置、日志、异常
  adapters/    # Redis/模型适配器
  alerting/    # 业务编排层
  http/        # 路由层
  application.py
  main.py
tests/         # 单元测试、集成测试、API 烟雾脚本
docs/          # 文档
docker/        # Dockerfile 与 compose
runtime/       # 本地运行目录骨架
```
