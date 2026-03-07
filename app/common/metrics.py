"""轻量指标采集模块（Prometheus 文本格式）。"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Dict, Tuple


class MetricsRegistry:
    """进程内指标注册表。"""

    _HTTP_BUCKETS = (0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0)

    def __init__(self):
        self._lock = threading.Lock()
        self._http_requests_total: Dict[Tuple[str, str, int], int] = defaultdict(int)
        self._http_duration_bucket: Dict[Tuple[str, str, float], int] = defaultdict(int)
        self._http_duration_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        self._http_duration_count: Dict[Tuple[str, str], int] = defaultdict(int)
        self._async_tasks_total: Dict[str, int] = defaultdict(int)

    def observe_http(self, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        """记录 HTTP 请求计数和延迟分布。"""

        m = (method or "").upper()
        p = path or "/"
        s = int(status_code)
        d = max(0.0, float(duration_seconds))

        with self._lock:
            self._http_requests_total[(m, p, s)] += 1
            self._http_duration_sum[(m, p)] += d
            self._http_duration_count[(m, p)] += 1
            for bucket in self._HTTP_BUCKETS:
                if d <= bucket:
                    self._http_duration_bucket[(m, p, bucket)] += 1
            self._http_duration_bucket[(m, p, float("inf"))] += 1

    def inc_async_task(self, outcome: str) -> None:
        """记录异步任务处理计数。"""

        key = (outcome or "unknown").lower()
        with self._lock:
            self._async_tasks_total[key] += 1

    def render_prometheus(self, queue_length: int, inflight_tasks: int, dead_letter_size: int) -> str:
        """导出 Prometheus exposition 格式文本。"""

        lines = []
        with self._lock:
            lines.append("# HELP http_requests_total Total HTTP requests.")
            lines.append("# TYPE http_requests_total counter")
            for (method, path, status), value in sorted(self._http_requests_total.items()):
                lines.append(
                    f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {value}'
                )

            lines.append("# HELP http_request_duration_seconds HTTP request latency in seconds.")
            lines.append("# TYPE http_request_duration_seconds histogram")
            keys = sorted(set((method, path) for method, path, _ in self._http_duration_bucket.keys()))
            for method, path in keys:
                for bucket in self._HTTP_BUCKETS:
                    count = self._http_duration_bucket.get((method, path, bucket), 0)
                    lines.append(
                        f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{bucket}"}} {count}'
                    )
                inf_count = self._http_duration_bucket.get((method, path, float("inf")), 0)
                lines.append(
                    f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="+Inf"}} {inf_count}'
                )
                lines.append(
                    f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {self._http_duration_sum.get((method, path), 0.0)}'
                )
                lines.append(
                    f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {self._http_duration_count.get((method, path), 0)}'
                )

            lines.append("# HELP async_tasks_total Total async task outcomes.")
            lines.append("# TYPE async_tasks_total counter")
            for outcome, value in sorted(self._async_tasks_total.items()):
                lines.append(f'async_tasks_total{{outcome="{outcome}"}} {value}')

        lines.append("# HELP alert_queue_length Current pending queue length.")
        lines.append("# TYPE alert_queue_length gauge")
        lines.append(f"alert_queue_length {int(queue_length)}")

        lines.append("# HELP alert_worker_inflight Current in-flight async tasks.")
        lines.append("# TYPE alert_worker_inflight gauge")
        lines.append(f"alert_worker_inflight {int(inflight_tasks)}")

        lines.append("# HELP alert_dead_letter_size Current dead-letter queue size.")
        lines.append("# TYPE alert_dead_letter_size gauge")
        lines.append(f"alert_dead_letter_size {int(dead_letter_size)}")
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
