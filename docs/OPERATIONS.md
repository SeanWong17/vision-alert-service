# 运行与运维基线

本文件定义最小生产运维标准，目标是提高稳定性并避免过度开发。

## 1. 监控面板（最低要求）
- 请求面板：
  - `sum(rate(http_requests_total[5m])) by (path, status)`
  - `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))`
- 异步链路面板：
  - `sum(rate(async_tasks_total{outcome="success"}[5m]))`
  - `sum(rate(async_tasks_total{outcome="failure"}[5m]))`
  - `alert_queue_length`
  - `alert_worker_inflight`
  - `alert_dead_letter_size`

## 2. 告警阈值（起步版）
- 可用性：
  - `/readyz` 返回非 200 持续 2 分钟 -> P1
- 错误率：
  - `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 3%` 持续 5 分钟 -> P1
- 延迟：
  - p95 `http_request_duration_seconds` > 1s 持续 10 分钟 -> P2
- 异步失败：
  - `sum(rate(async_tasks_total{outcome="failure"}[5m])) > 0` 持续 10 分钟 -> P2
- 积压：
  - `alert_queue_length > 500` 持续 10 分钟 -> P2
  - `alert_dead_letter_size > 0` 持续 5 分钟 -> P2

## 3. 故障演练（每月一次）
- 演练 A：Redis 短暂不可用（5 分钟）
  - 预期：`/readyz` 非 ready；恢复后就绪恢复；无 silent failure
- 演练 B：模型推理异常（注入异常）
  - 预期：异步任务写入 dead-letter；`async_tasks_total{outcome="failure"}` 增长
- 演练 C：结果图写入失败（磁盘权限/空间）
  - 预期：请求失败可观测；无“成功响应但无结果文件”

## 4. 容量基线（每次版本发布前）
- 记录以下数据（固定输入集、固定机器规格）：
  - 同步接口 p50/p95 延迟与 QPS
  - 异步吞吐（tasks/min）
  - `alert_queue_length` 峰值
  - `alert_worker_inflight` 峰值
- 若与上一个稳定版本相比退化超过 20%，阻止发布并回滚分析。

## 5. 值班检查清单（每日）
- `/healthz` 与 `/readyz` 状态
- 前 24 小时 5xx 错误率
- dead-letter 是否新增
- 队列是否持续积压
