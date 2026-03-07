"""告警存储层测试。"""

import unittest


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        import pydantic  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class AlertStoreTest(unittest.TestCase):
    """验证队列与结果存取语义。"""

    def setUp(self):
        """初始化测试存储对象并强制使用内存后端。"""

        from app.alerting.schemas import AlarmTask, QueueTask, StoredResult
        from app.alerting.store import AlertStore
        from app.common.settings import AlertSettings

        self.AlarmTask = AlarmTask
        self.QueueTask = QueueTask
        self.StoredResult = StoredResult

        settings = AlertSettings(upload_root="/tmp/u", result_root="/tmp/r", model_root="/tmp/m")
        self.store = AlertStore(settings)
        self.store.redis = None

    def test_enqueue_pop_and_pending(self):
        """写入队列后应可读取 pending 并正常 pop。"""

        task = self.QueueTask(
            image_id="img-1",
            session_id="s1",
            file_name="a.jpg",
            file_path="/tmp/a.jpg",
            tasks=[self.AlarmTask(id=1, params={"limit": 1, "coordinate": [-1, -1, -1, -1]})],
        )
        self.store.enqueue(task)
        self.assertEqual(self.store.queue_length(), 1)

        pending = self.store.get_pending("s1", "img-1")
        self.assertIsNotNone(pending)

        popped = self.store.pop()
        self.assertIsNotNone(popped)
        self.assertEqual(popped.image_id, "img-1")

    def test_result_fetch_and_confirm(self):
        """结果拉取与确认删除行为应符合预期。"""

        self.store.save_result(
            "s1",
            "img-1",
            self.StoredResult(imageId="img-1", filename="a.jpg", results=[{"reserved": "1"}]),
        )
        rows, has_more = self.store.fetch_results("s1", limit=10)
        self.assertFalse(has_more)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["imageId"], "img-1")

        self.store.save_result(
            "s1",
            "img-2",
            self.StoredResult(imageId="img-2", filename="b.jpg", results=[{"reserved": "0"}]),
        )
        self.store.confirm_results("s1", ["img-2"])
        rows2, _ = self.store.fetch_results("s1", limit=10)
        self.assertEqual(len(rows2), 1)
        self.assertEqual(rows2[0]["imageId"], "img-1")

        self.store.confirm_results("s1", ["img-1"])
        rows3, _ = self.store.fetch_results("s1", limit=10)
        self.assertEqual(rows3, [])

    def test_discard_pending_removes_snapshot(self):
        """异常兜底调用 discard_pending 后应清理 pending。"""

        task = self.QueueTask(
            image_id="img-p",
            session_id="s-p",
            file_name="p.jpg",
            file_path="/tmp/p.jpg",
            tasks=[self.AlarmTask(id=1, params={"limit": 1})],
        )
        self.store.enqueue(task)
        self.assertIsNotNone(self.store.get_pending("s-p", "img-p"))
        self.store.discard_pending("s-p", "img-p")
        self.assertIsNone(self.store.get_pending("s-p", "img-p"))

    def test_push_dead_letter_records_failure_payload(self):
        """死信记录应保存在内存死信队列。"""

        task = self.QueueTask(
            image_id="img-dlq",
            session_id="s-dlq",
            file_name="dlq.jpg",
            file_path="/tmp/dlq.jpg",
            tasks=[self.AlarmTask(id=5, params={"limit": 1})],
        )
        self.store.push_dead_letter(task, "boom")
        self.assertEqual(len(self.store._dead_letters), 1)

    def test_fetch_and_confirm_results_use_stream_ack(self):
        """Redis 分支应走 stream 消费并在确认时 ack+del。"""

        import json

        class _FakeRedis:
            def __init__(self):
                self.xgroup_create_called = 0
                self.hset_calls = []
                self.hmget_calls = []
                self.xack_calls = []
                self.xdel_calls = []
                self.hdel_calls = []
                self.xreadgroup_calls = []
                self.xautoclaim_calls = []

            def xgroup_create(self, _stream, _group, id="0", mkstream=True):
                _ = (id, mkstream)
                self.xgroup_create_called += 1

            def xreadgroup(self, groupname, consumername, streams, count):
                self.xreadgroup_calls.append((groupname, consumername, dict(streams), count))
                stream_key = list(streams.keys())[0]
                stream_id = streams[stream_key]
                if stream_id == "0":
                    return []
                if stream_id == ">":
                    return [
                        (
                            stream_key,
                            [("1710000000001-0", {"imageId": "img-2", "payload": json.dumps({"imageId": "img-2"})})],
                        )
                    ]
                return [
                    (
                        stream_key,
                        [
                            ("1710000000002-0", {"imageId": "img-x", "payload": json.dumps({"imageId": "img-x"})}),
                        ],
                    )
                ]

            def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id, count):
                self.xautoclaim_calls.append((name, groupname, consumername, min_idle_time, start_id, count))
                return (
                    "1710000000001-0",
                    [("1710000000000-0", {"imageId": "img-1", "payload": json.dumps({"imageId": "img-1"})})],
                    [],
                )

            def xpending(self, _stream, _group):
                return {"pending": 1}

            def hset(self, key, field, value):
                self.hset_calls.append((key, field, value))
                return 1

            def hmget(self, key, fields):
                self.hmget_calls.append((key, list(fields)))
                return ["1710000000000-0", "1710000000001-0"]

            def xack(self, key, group, *ids):
                self.xack_calls.append((key, group, list(ids)))
                return len(ids)

            def xdel(self, key, *ids):
                self.xdel_calls.append((key, list(ids)))
                return len(ids)

            def hdel(self, key, *fields):
                self.hdel_calls.append((key, list(fields)))
                return len(fields)

        fake_redis = _FakeRedis()
        self.store.redis = fake_redis

        rows, has_more = self.store.fetch_results("s-redis", limit=2)
        self.assertEqual(len(rows), 2)
        self.assertTrue(has_more)
        self.assertEqual(fake_redis.xgroup_create_called, 1)
        self.assertEqual(len(fake_redis.xreadgroup_calls), 2)
        self.assertEqual(list(fake_redis.xreadgroup_calls[0][2].values())[0], "0")
        self.assertEqual(list(fake_redis.xreadgroup_calls[1][2].values())[0], ">")
        self.assertEqual(len(fake_redis.xautoclaim_calls), 1)
        self.assertEqual(len(fake_redis.hset_calls), 2)

        self.store.confirm_results("s-redis", ["img-1", "img-2"])
        self.assertEqual(len(fake_redis.hmget_calls), 1)
        self.assertEqual(len(fake_redis.xack_calls), 1)
        self.assertEqual(len(fake_redis.xdel_calls), 1)
        self.assertTrue(any(len(call[1]) == 2 for call in fake_redis.hdel_calls))

    def test_fetch_results_has_more_depends_on_page_size(self):
        """hasMore 应由是否达到分页上限决定，避免 PEL 统计假阳性。"""

        import json

        class _FakeRedis:
            def xgroup_create(self, _stream, _group, id="0", mkstream=True):
                _ = (id, mkstream)
                return True

            def xreadgroup(self, groupname, consumername, streams, count):
                _ = (groupname, consumername, count)
                stream_key = list(streams.keys())[0]
                stream_id = streams[stream_key]
                if stream_id == "0":
                    return []
                return [
                    (stream_key, [("1710000000001-0", {"imageId": "img-2", "payload": json.dumps({"imageId": "img-2"})})])
                ]

            def xautoclaim(self, **_kwargs):
                return ("0-0", [], [])

            def hset(self, _key, _field, _value):
                return 1

        self.store.redis = _FakeRedis()
        rows, has_more = self.store.fetch_results("s-redis", limit=3)
        self.assertEqual(len(rows), 1)
        self.assertFalse(has_more)


if __name__ == "__main__":
    unittest.main()
