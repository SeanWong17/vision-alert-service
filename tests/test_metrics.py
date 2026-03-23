"""MetricsRegistry 单元测试。

验证 HTTP 请求指标、异步任务计数、推理延迟直方图的记录逻辑，
以及 Prometheus 导出格式的正确性和多线程并发安全性。
"""

from __future__ import annotations

import threading
import unittest

from app.common.metrics import MetricsRegistry


class TestObserveHttp(unittest.TestCase):
    """测试 observe_http 方法的请求计数和延迟记录。"""

    def setUp(self):
        """每个测试用例使用全新的 MetricsRegistry 实例。"""
        self.registry = MetricsRegistry()

    def test_single_request_counter(self):
        """记录一次 HTTP 请求后，对应的计数器应为 1。"""
        self.registry.observe_http("GET", "/health", 200, 0.02)
        self.assertEqual(self.registry._http_requests_total[("GET", "/health", 200)], 1)

    def test_multiple_requests_accumulate(self):
        """同一路由多次请求，计数器应累加。"""
        for _ in range(5):
            self.registry.observe_http("POST", "/predict", 200, 0.1)
        self.assertEqual(self.registry._http_requests_total[("POST", "/predict", 200)], 5)

    def test_duration_sum_and_count(self):
        """observe_http 应正确累计延迟总和与请求次数。"""
        self.registry.observe_http("GET", "/api", 200, 0.3)
        self.registry.observe_http("GET", "/api", 200, 0.7)
        self.assertAlmostEqual(self.registry._http_duration_sum[("GET", "/api")], 1.0)
        self.assertEqual(self.registry._http_duration_count[("GET", "/api")], 2)

    def test_bucket_distribution(self):
        """延迟 0.02s 的请求应落入 le=0.05 及以上的所有桶。"""
        self.registry.observe_http("GET", "/", 200, 0.02)
        # 0.02 <= 0.05，所以 le=0.05 桶至少为 1
        self.assertGreaterEqual(self.registry._http_duration_bucket[("GET", "/", 0.05)], 1)
        # +Inf 桶始终包含所有样本
        self.assertEqual(self.registry._http_duration_bucket[("GET", "/", float("inf"))], 1)

    def test_method_uppercased(self):
        """传入小写 method 应自动转为大写。"""
        self.registry.observe_http("get", "/x", 200, 0.01)
        self.assertIn(("GET", "/x", 200), self.registry._http_requests_total)

    def test_negative_duration_clamped_to_zero(self):
        """负数延迟应被截断为 0。"""
        self.registry.observe_http("GET", "/", 200, -1.0)
        self.assertAlmostEqual(self.registry._http_duration_sum[("GET", "/")], 0.0)


class TestIncAsyncTask(unittest.TestCase):
    """测试 inc_async_task 方法的异步任务计数。"""

    def setUp(self):
        self.registry = MetricsRegistry()

    def test_single_outcome(self):
        """记录一次 success 结果，计数器应为 1。"""
        self.registry.inc_async_task("success")
        self.assertEqual(self.registry._async_tasks_total["success"], 1)

    def test_multiple_outcomes(self):
        """不同结果应分别计数。"""
        self.registry.inc_async_task("success")
        self.registry.inc_async_task("success")
        self.registry.inc_async_task("failure")
        self.assertEqual(self.registry._async_tasks_total["success"], 2)
        self.assertEqual(self.registry._async_tasks_total["failure"], 1)

    def test_none_outcome_defaults_to_unknown(self):
        """传入 None 时 outcome 应降级为 'unknown'。"""
        self.registry.inc_async_task(None)
        self.assertEqual(self.registry._async_tasks_total["unknown"], 1)


class TestObserveInference(unittest.TestCase):
    """测试 observe_inference 方法的推理延迟记录。"""

    def setUp(self):
        self.registry = MetricsRegistry()

    def test_single_observation(self):
        """记录一次推理延迟后，sum 和 count 应正确更新。"""
        self.registry.observe_inference("detection", 0.15)
        self.assertAlmostEqual(self.registry._inference_duration_sum["detection"], 0.15)
        self.assertEqual(self.registry._inference_duration_count["detection"], 1)

    def test_bucket_distribution(self):
        """延迟 0.15s 应落入 le=0.25 及以上的桶，不落入 le=0.1。"""
        self.registry.observe_inference("segmentation", 0.15)
        # 0.15 > 0.1，所以 le=0.1 桶不应增加
        self.assertEqual(self.registry._inference_duration_bucket.get(("segmentation", 0.1), 0), 0)
        # 0.15 <= 0.25，所以 le=0.25 桶应为 1
        self.assertEqual(self.registry._inference_duration_bucket[("segmentation", 0.25)], 1)
        # +Inf 桶始终包含所有样本
        self.assertEqual(self.registry._inference_duration_bucket[("segmentation", float("inf"))], 1)

    def test_stage_lowercased(self):
        """传入大写 stage 应自动转为小写。"""
        self.registry.observe_inference("TOTAL", 1.0)
        self.assertIn("total", self.registry._inference_duration_sum)

    def test_accumulation(self):
        """同一阶段多次观测应正确累加。"""
        self.registry.observe_inference("postprocess", 0.3)
        self.registry.observe_inference("postprocess", 0.5)
        self.assertAlmostEqual(self.registry._inference_duration_sum["postprocess"], 0.8)
        self.assertEqual(self.registry._inference_duration_count["postprocess"], 2)


class TestRenderPrometheus(unittest.TestCase):
    """测试 render_prometheus 输出的 Prometheus exposition 格式。"""

    def setUp(self):
        self.registry = MetricsRegistry()

    def test_contains_http_requests_total(self):
        """输出应包含 http_requests_total 指标及其标签。"""
        self.registry.observe_http("GET", "/health", 200, 0.01)
        output = self.registry.render_prometheus(queue_length=0, inflight_tasks=0, dead_letter_size=0)
        self.assertIn("# TYPE http_requests_total counter", output)
        self.assertIn('http_requests_total{method="GET",path="/health",status="200"} 1', output)

    def test_contains_http_histogram(self):
        """输出应包含 http_request_duration_seconds histogram 的桶和 sum/count。"""
        self.registry.observe_http("POST", "/predict", 200, 0.05)
        output = self.registry.render_prometheus(queue_length=0, inflight_tasks=0, dead_letter_size=0)
        self.assertIn("# TYPE http_request_duration_seconds histogram", output)
        self.assertIn("http_request_duration_seconds_bucket", output)
        self.assertIn("http_request_duration_seconds_sum", output)
        self.assertIn("http_request_duration_seconds_count", output)
        # +Inf 桶应存在
        self.assertIn('le="+Inf"', output)

    def test_contains_async_tasks_total(self):
        """输出应包含 async_tasks_total 指标。"""
        self.registry.inc_async_task("success")
        output = self.registry.render_prometheus(queue_length=0, inflight_tasks=0, dead_letter_size=0)
        self.assertIn("# TYPE async_tasks_total counter", output)
        self.assertIn('async_tasks_total{outcome="success"} 1', output)

    def test_contains_inference_duration(self):
        """输出应包含 inference_duration_seconds histogram。"""
        self.registry.observe_inference("detection", 0.2)
        output = self.registry.render_prometheus(queue_length=0, inflight_tasks=0, dead_letter_size=0)
        self.assertIn("# TYPE inference_duration_seconds histogram", output)
        self.assertIn("inference_duration_seconds_bucket", output)
        self.assertIn("inference_duration_seconds_sum", output)
        self.assertIn("inference_duration_seconds_count", output)

    def test_contains_gauge_metrics(self):
        """输出应包含 alert_queue_length、alert_worker_inflight、alert_dead_letter_size gauge 指标。"""
        output = self.registry.render_prometheus(queue_length=10, inflight_tasks=3, dead_letter_size=2)
        self.assertIn("# TYPE alert_queue_length gauge", output)
        self.assertIn("alert_queue_length 10", output)
        self.assertIn("# TYPE alert_worker_inflight gauge", output)
        self.assertIn("alert_worker_inflight 3", output)
        self.assertIn("# TYPE alert_dead_letter_size gauge", output)
        self.assertIn("alert_dead_letter_size 2", output)

    def test_output_ends_with_newline(self):
        """Prometheus 导出文本应以换行符结尾。"""
        output = self.registry.render_prometheus(queue_length=0, inflight_tasks=0, dead_letter_size=0)
        self.assertTrue(output.endswith("\n"))

    def test_empty_registry_still_has_gauge(self):
        """即使没有记录任何请求，gauge 指标仍应输出。"""
        output = self.registry.render_prometheus(queue_length=0, inflight_tasks=0, dead_letter_size=0)
        self.assertIn("alert_queue_length 0", output)
        self.assertIn("alert_worker_inflight 0", output)
        self.assertIn("alert_dead_letter_size 0", output)


class TestMetricsThreadSafety(unittest.TestCase):
    """测试 MetricsRegistry 的多线程并发安全性。"""

    def test_concurrent_observe_http(self):
        """多线程并发调用 observe_http 不应引发异常，且计数器总和正确。"""
        registry = MetricsRegistry()
        num_threads = 8
        calls_per_thread = 200
        barrier = threading.Barrier(num_threads)

        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for i in range(calls_per_thread):
                    registry.observe_http("GET", "/concurrent", 200, 0.01 * (i % 10))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(errors), 0, f"并发 observe_http 出现异常: {errors}")
        expected_total = num_threads * calls_per_thread
        self.assertEqual(
            registry._http_requests_total[("GET", "/concurrent", 200)],
            expected_total,
        )

    def test_concurrent_mixed_operations(self):
        """多线程混合调用 observe_http、inc_async_task、observe_inference 不应崩溃。"""
        registry = MetricsRegistry()
        num_threads = 6
        calls_per_thread = 150
        barrier = threading.Barrier(num_threads)

        errors = []

        def http_worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(calls_per_thread):
                    registry.observe_http("POST", "/mix", 201, 0.05)
            except Exception as exc:
                errors.append(exc)

        def async_worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(calls_per_thread):
                    registry.inc_async_task("success")
            except Exception as exc:
                errors.append(exc)

        def inference_worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(calls_per_thread):
                    registry.observe_inference("detection", 0.2)
            except Exception as exc:
                errors.append(exc)

        threads = []
        # 每种操作各两个线程
        for factory in (http_worker, async_worker, inference_worker):
            threads.append(threading.Thread(target=factory))
            threads.append(threading.Thread(target=factory))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(errors), 0, f"并发混合操作出现异常: {errors}")

        # 验证各计数器总和
        self.assertEqual(
            registry._http_requests_total[("POST", "/mix", 201)],
            2 * calls_per_thread,
        )
        self.assertEqual(
            registry._async_tasks_total["success"],
            2 * calls_per_thread,
        )
        self.assertEqual(
            registry._inference_duration_count["detection"],
            2 * calls_per_thread,
        )

    def test_concurrent_render_prometheus(self):
        """在写入指标的同时并发调用 render_prometheus 不应崩溃。"""
        registry = MetricsRegistry()
        num_writers = 4
        num_readers = 4
        iterations = 100
        barrier = threading.Barrier(num_writers + num_readers)

        errors = []

        def write_worker():
            try:
                barrier.wait(timeout=5)
                for _i in range(iterations):
                    registry.observe_http("GET", "/render", 200, 0.01)
                    registry.inc_async_task("success")
                    registry.observe_inference("total", 0.5)
            except Exception as exc:
                errors.append(exc)

        def read_worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(iterations):
                    output = registry.render_prometheus(queue_length=1, inflight_tasks=2, dead_letter_size=0)
                    # 确保输出始终是有效字符串
                    assert isinstance(output, str) and len(output) > 0
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write_worker) for _ in range(num_writers)]
        threads += [threading.Thread(target=read_worker) for _ in range(num_readers)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(errors), 0, f"并发读写出现异常: {errors}")


if __name__ == "__main__":
    unittest.main()
