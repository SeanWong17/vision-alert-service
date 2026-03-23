# 贡献指南

[中文](CONTRIBUTING.md) | [English](CONTRIBUTING.en.md)

感谢你愿意改进 Vision Alert Service。

## 开发环境

```bash
python3 -m pip install -r requirements-ci.txt
```

如需本地跑真实推理链路，再额外安装：

```bash
python3 -m pip install -r requirements.txt
```

## 提交前检查

请至少完成以下检查：

```bash
python3 -m compileall -q app tests scripts
python3 -m pytest tests/test_worker.py tests/test_settings.py
python3 scripts/ci_unittest_gate.py
```

若本地已安装 `ruff`，再执行：

```bash
ruff check app tests scripts
ruff format --check app tests scripts
```

## 代码约定

- 优先提交小而清晰的变更，避免把重构、功能、文档混在一个 PR。
- 不要在未说明的情况下修改公共 API 字段语义。
- 新增行为分支时，优先补对应测试。
- 日志、错误码、配置项变更需要同步更新文档。
- Docker、部署、运行时依赖变更需要说明回滚方案。

## Pull Request 说明

PR 描述建议包含：

- 变更背景和目标
- 核心实现思路
- 风险点与兼容性影响
- 测试范围和结果
- 如有接口变化，附请求/响应示例

## Issue 反馈

- Bug 请附复现步骤、配置片段、日志和环境信息。
- 功能请求请说明使用场景、预期收益和替代方案。
- 安全问题不要公开提交细节，请参考 [SECURITY.md](SECURITY.md)。
