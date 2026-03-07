# AI Alerting Service

该仓库提供“检测 + 分割 + 告警后处理”的同步/异步服务。

## 快速开始
```bash
cd ai_service
./scripts/init_runtime_dirs.sh
python3 -m pip install -r requirements.txt
python3 main.py --host 0.0.0.0 --port 8011
```

## 文档导航
- 架构与调用链：`docs/CALL_CHAIN.md`
- API 接口文档：`docs/API.md`
- 部署与 Docker：`docs/DEPLOYMENT.md`

## 目录概览
```text
app/
  core/        # 配置、日志、异常
  infra/       # Redis 等基础设施
  vision/      # 模型适配层
  alerting/    # 业务编排层
  api/         # 路由层
tests/         # 单元测试与集成测试
scripts/       # 运维脚本（目录初始化）
runtime/       # 本地运行数据目录骨架
```
