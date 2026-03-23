"""告警存储模块：队列与结果的 Redis/内存双实现。"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from collections import defaultdict, deque

from app.alerting.config import AlertSettings
from app.alerting.schemas import QueueTask, StoredResult
from app.common.logging import logger

try:
    from app.adapters.redis import RedisClient
except Exception:  # pragma: no cover
    RedisClient = None


class AlertStore:
    """异步任务与结果的持久化抽象。

    结果存储采用两种后端：
    - 内存模式：用于本地联调（单进程）
    - Redis 模式：result stream + ack map
      1) save_result -> XADD
      2) fetch_results -> XREADGROUP/XAUTOCLAIM
      3) confirm_results -> XACK + XDEL
    """

    def __init__(self, settings: AlertSettings):
        """初始化存储层，优先连接 Redis，失败时回退内存。"""

        self.settings = settings
        self._lock = threading.Lock()
        self._consumer_name = os.getenv("ALERT_RESULT_CONSUMER", f"{socket.gethostname()}-{os.getpid()}")

        # 内存回退结构：仅适合单进程开发联调。
        self._queue: deque[str] = deque()
        self._pending: dict[str, dict[str, str]] = defaultdict(dict)
        self._results: dict[str, dict[str, str]] = defaultdict(dict)
        self._dead_letters: deque[str] = deque(maxlen=max(100, int(self.settings.dead_letter_maxlen)))

        self.redis = None
        if RedisClient is not None:
            try:
                self.redis = RedisClient()
            except Exception as exc:  # pragma: no cover
                logger.warning("redis unavailable, fallback to in-memory store: %s", exc)

    def _pending_key(self, session_id: str) -> str:
        """生成 pending 哈希键。"""

        return self.settings.pending_key(session_id)

    def _result_key(self, session_id: str) -> str:
        """生成 result 哈希键。"""

        return self.settings.result_key(session_id)

    def _result_stream_key(self, session_id: str) -> str:
        """生成 result stream 键。"""

        return self.settings.result_stream_key(session_id)

    def _result_ack_key(self, session_id: str) -> str:
        """生成 result ack 映射键。"""

        return self.settings.result_ack_key(session_id)

    def _result_group(self, session_id: str) -> str:
        """生成 result stream 消费组。"""

        return self.settings.result_group(session_id)

    def _dead_letter_queue(self) -> str:
        """死信队列 key。"""

        return self.settings.dead_letter_queue

    def _ensure_result_group(self, stream_key: str, group_name: str) -> None:
        """确保结果 stream 的消费组存在。"""

        try:
            self.redis.xgroup_create(stream_key, group_name, id="0", mkstream=True)
        except Exception as exc:  # redis.exceptions.ResponseError: BUSYGROUP
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue(self, task: QueueTask) -> None:
        """写入 pending 与队列。"""

        payload = task.model_dump_json()
        if self.redis:
            # 使用 pipeline 将两次 Redis 操作合并为一次网络往返。
            pipe = self.redis.pipeline(transaction=False)
            pipe.hset(self._pending_key(task.session_id), task.image_id, payload)
            pipe.rpush(self.settings.queue_name, payload)
            pipe.execute()
            return

        with self._lock:
            self._pending[task.session_id][task.image_id] = payload
            self._queue.append(payload)

    def queue_length(self) -> int:
        """获取当前待处理队列长度。"""

        if self.redis:
            return int(self.redis.llen(self.settings.queue_name))
        with self._lock:
            return len(self._queue)

    def dead_letter_size(self) -> int:
        """获取当前死信队列长度。"""

        if self.redis:
            return int(self.redis.llen(self._dead_letter_queue()))
        with self._lock:
            return len(self._dead_letters)

    def pop(self) -> QueueTask | None:
        """弹出一个待处理任务。"""

        if self.redis:
            payload = self.redis.lpop(self.settings.queue_name)
            return QueueTask(**json.loads(payload)) if payload else None

        with self._lock:
            if not self._queue:
                return None
            return QueueTask(**json.loads(self._queue.popleft()))

    def get_pending(self, session_id: str, image_id: str) -> QueueTask | None:
        """读取 pending 中的任务快照。"""

        if self.redis:
            payload = self.redis.hget(self._pending_key(session_id), image_id)
            return QueueTask(**json.loads(payload)) if payload else None

        with self._lock:
            payload = self._pending.get(session_id, {}).get(image_id)
            return QueueTask(**json.loads(payload)) if payload else None

    def save_result(self, session_id: str, image_id: str, result: StoredResult) -> None:
        """保存处理结果并移除 pending。"""

        payload = result.model_dump_json()
        if self.redis:
            # 使用 pipeline 将 XADD + HDEL 合并为一次网络往返。
            pipe = self.redis.pipeline(transaction=False)
            pipe.xadd(self._result_stream_key(session_id), {"imageId": image_id, "payload": payload})
            pipe.hdel(self._pending_key(session_id), image_id)
            pipe.execute()
            return

        with self._lock:
            self._results[session_id][image_id] = payload
            self._pending[session_id].pop(image_id, None)

    def fetch_results(self, session_id: str, limit: int = 50) -> tuple[list[dict], bool]:
        """批量拉取结果并从存储中移除已拉取项。"""

        if self.redis:
            stream_key = self._result_stream_key(session_id)
            group_name = self._result_group(session_id)
            ack_key = self._result_ack_key(session_id)
            safe_limit = max(1, int(limit))
            self._ensure_result_group(stream_key, group_name)
            rows: list[dict] = []

            def _consume(resp_items) -> None:
                # 把 stream entry 转为业务行，同时记录 imageId -> entryId，
                # 便于后续 confirm 时执行 XACK/XDEL。
                for _, entries in resp_items or []:
                    for entry_id, fields in entries:
                        payload = fields.get("payload")
                        image_id = fields.get("imageId")
                        if not payload:
                            continue
                        rows.append(json.loads(payload))
                        if image_id:
                            self.redis.hset(ack_key, image_id, entry_id)

            # 先拉取当前 consumer 未确认的 pending，避免结果在 PEL 中“看不见”。
            pending_resp = self.redis.xreadgroup(
                groupname=group_name,
                consumername=self._consumer_name,
                streams={stream_key: "0"},
                count=safe_limit,
            )
            _consume(pending_resp)

            remaining = safe_limit - len(rows)
            if remaining > 0:
                # 回收其他 consumer 超时未确认消息，提升多实例和重启场景可恢复性。
                try:
                    claim_resp = self.redis.xautoclaim(
                        name=stream_key,
                        groupname=group_name,
                        consumername=self._consumer_name,
                        min_idle_time=self.settings.result_claim_idle_ms,
                        start_id="0-0",
                        count=remaining,
                    )
                except Exception:
                    claim_resp = None

                claimed_entries = []
                if claim_resp and isinstance(claim_resp, (list, tuple)) and len(claim_resp) >= 2:
                    # redis-py 兼容：返回 (next_start, entries) 或 (next_start, entries, deleted_ids)
                    claimed_entries = claim_resp[1] or []
                if claimed_entries:
                    _consume([(stream_key, claimed_entries)])

            remaining = safe_limit - len(rows)
            if remaining > 0:
                # 最后读取新消息（'>'），保证实时性。
                new_resp = self.redis.xreadgroup(
                    groupname=group_name,
                    consumername=self._consumer_name,
                    streams={stream_key: ">"},
                    count=remaining,
                )
                _consume(new_resp)

            has_more = len(rows) >= safe_limit
            # 尝试用组统计信息收敛 hasMore 假阳性：
            # pending 中扣除本批已返回条数后若仍有剩余，或 lag>0，说明仍有可消费项。
            try:
                groups = self.redis.xinfo_groups(stream_key)
                group = next((item for item in groups if item.get("name") == group_name), None)
                if group:
                    pending_total = int(group.get("pending", 0))
                    lag_raw = group.get("lag")
                    lag_total = int(lag_raw) if lag_raw is not None else 0
                    extra_pending = max(0, pending_total - len(rows))
                    has_more = (extra_pending + lag_total) > 0
            except Exception:
                pass
            return rows, has_more

        with self._lock:
            image_map = self._results.get(session_id, {})
            image_ids = list(image_map.keys())
            has_more = len(image_ids) > limit
            rows = []
            for image_id in image_ids[:limit]:
                rows.append(json.loads(image_map[image_id]))
            return rows, has_more

    def confirm_results(self, session_id: str, image_ids: list[str]) -> None:
        """确认结果并删除对应记录。"""

        if self.redis:
            if not image_ids:
                return

            stream_key = self._result_stream_key(session_id)
            group_name = self._result_group(session_id)
            ack_key = self._result_ack_key(session_id)
            entry_ids = self.redis.hmget(ack_key, image_ids)
            valid_entry_ids = [entry_id for entry_id in entry_ids if entry_id]

            if valid_entry_ids:
                # 使用 pipeline 将 ACK + DEL 合并为一次网络往返。
                pipe = self.redis.pipeline(transaction=False)
                pipe.xack(stream_key, group_name, *valid_entry_ids)
                pipe.xdel(stream_key, *valid_entry_ids)
                pipe.execute()

            self.redis.hdel(ack_key, *image_ids)
            return

        with self._lock:
            bucket = self._results.get(session_id, {})
            for image_id in image_ids:
                bucket.pop(image_id, None)

    def discard_pending(self, session_id: str, image_id: str) -> None:
        """主动删除 pending 任务（用于异常兜底，避免任务长期滞留）。"""

        if self.redis:
            self.redis.hdel(self._pending_key(session_id), image_id)
            return

        with self._lock:
            self._pending.get(session_id, {}).pop(image_id, None)

    def push_dead_letter(self, task: QueueTask, reason: str) -> None:
        """记录死信任务，便于后续运维排障与重放。"""

        payload = json.dumps(
            {
                "sessionId": task.session_id,
                "imageId": task.image_id,
                "fileName": task.file_name,
                "filePath": task.file_path,
                "tasks": [item.model_dump() for item in task.tasks],
                "reason": str(reason),
                "timestamp": int(time.time() * 1000),
            },
            ensure_ascii=False,
        )
        if self.redis:
            # 使用 pipeline 将 LPUSH + LTRIM 合并为一次网络往返。
            pipe = self.redis.pipeline(transaction=False)
            pipe.lpush(self._dead_letter_queue(), payload)
            pipe.ltrim(self._dead_letter_queue(), 0, self.settings.dead_letter_maxlen - 1)
            pipe.execute()
            return

        with self._lock:
            self._dead_letters.appendleft(payload)
