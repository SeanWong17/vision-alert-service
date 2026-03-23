[中文](OPERATIONS.md) | [English](OPERATIONS.en.md)

# Operations Baseline

This document defines the minimum production operations standards, with the goal of improving stability while avoiding over-engineering.

## 1. Monitoring Dashboards (Minimum Requirements)

**Request dashboard:**
- `sum(rate(http_requests_total[5m])) by (path, status)`
- `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))`

**Async pipeline dashboard:**
- `sum(rate(async_tasks_total{outcome="success"}[5m]))`
- `sum(rate(async_tasks_total{outcome="failure"}[5m]))`
- `alert_queue_length`
- `alert_worker_inflight`
- `alert_dead_letter_size`

**Inference performance dashboard:**
- `histogram_quantile(0.95, sum(rate(inference_duration_seconds_bucket{stage="total"}[5m])) by (le))`
- `histogram_quantile(0.95, sum(rate(inference_duration_seconds_bucket{stage="detection"}[5m])) by (le))`
- `histogram_quantile(0.95, sum(rate(inference_duration_seconds_bucket{stage="segmentation"}[5m])) by (le))`

## 2. Alert Thresholds (Starter Configuration)

**Availability:**
- `/readyz` returns non-200 for 2 minutes -> P1

**Error rate:**
- `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 3%` for 5 minutes -> P1

**Latency:**
- p95 `http_request_duration_seconds` > 1s for 10 minutes -> P2

**Async failures:**
- `sum(rate(async_tasks_total{outcome="failure"}[5m])) > 0` for 10 minutes -> P2

**Backlog:**
- `alert_queue_length > 500` for 10 minutes -> P2
- `alert_dead_letter_size > 0` for 5 minutes -> P2

## 3. Fault Drills (Monthly)

**Drill A: Redis brief unavailability (5 minutes)**
- Expected: `/readyz` reports not ready; readiness restored after recovery; no silent failures.

**Drill B: Model inference error (injected exception)**
- Expected: async tasks are written to the dead-letter queue; `async_tasks_total{outcome="failure"}` increases.

**Drill C: Result image write failure (disk permission / space issue)**
- Expected: request failures are observable; no scenario where a success response is returned but no result file is produced.

## 4. Capacity Baseline (Before Each Release)

Record the following metrics using a fixed input set on fixed hardware:
- Synchronous endpoint p50 / p95 latency and QPS
- Async throughput (tasks/min)
- Peak `alert_queue_length`
- Peak `alert_worker_inflight`

If any metric regresses by more than 20% compared to the previous stable release, block the release and perform a rollback analysis.

## 5. On-Call Daily Checklist

- `/healthz` and `/readyz` status
- 5xx error rate over the past 24 hours
- Any new entries in the dead-letter queue
- Whether the task queue shows sustained backlog
