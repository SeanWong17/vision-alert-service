"""告警存储模块：队列与结果的 Redis/内存双实现。"""

from __future__ import annotations

import json
import threading
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

from app.alerting.config import AlertSettings
from app.alerting.schemas import QueueTask, StoredResult
from app.core.logging import logger

try:
    from app.infra.redis_client import RedisClient
except Exception:  # pragma: no cover
    RedisClient = None


class AlertStore:
    """异步任务与结果的持久化抽象。"""

    def __init__(self, settings: AlertSettings):
        """初始化存储层，优先连接 Redis，失败时回退内存。"""

        self.settings = settings
        self._lock = threading.Lock()

        # 内存回退结构：仅适合单进程开发联调。
        self._queue: deque[str] = deque()
        self._pending: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._results: Dict[str, Dict[str, str]] = defaultdict(dict)

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

    def enqueue(self, task: QueueTask) -> None:
        """写入 pending 与队列。"""

        payload = task.json(ensure_ascii=False)
        if self.redis:
            self.redis.hset(self._pending_key(task.session_id), task.image_id, payload)
            self.redis.rpush(self.settings.queue_name, payload)
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

    def pop(self) -> Optional[QueueTask]:
        """弹出一个待处理任务。"""

        if self.redis:
            payload = self.redis.lpop(self.settings.queue_name)
            return QueueTask(**json.loads(payload)) if payload else None

        with self._lock:
            if not self._queue:
                return None
            return QueueTask(**json.loads(self._queue.popleft()))

    def get_pending(self, session_id: str, image_id: str) -> Optional[QueueTask]:
        """读取 pending 中的任务快照。"""

        if self.redis:
            payload = self.redis.hget(self._pending_key(session_id), image_id)
            return QueueTask(**json.loads(payload)) if payload else None

        with self._lock:
            payload = self._pending.get(session_id, {}).get(image_id)
            return QueueTask(**json.loads(payload)) if payload else None

    def save_result(self, session_id: str, image_id: str, result: StoredResult) -> None:
        """保存处理结果并移除 pending。"""

        payload = result.json(ensure_ascii=False)
        if self.redis:
            self.redis.hset(self._result_key(session_id), image_id, payload)
            self.redis.hdel(self._pending_key(session_id), image_id)
            return

        with self._lock:
            self._results[session_id][image_id] = payload
            self._pending[session_id].pop(image_id, None)

    def fetch_results(self, session_id: str, limit: int = 50) -> Tuple[List[dict], bool]:
        """批量拉取结果并从存储中移除已拉取项。"""

        if self.redis:
            key = self._result_key(session_id)
            total = int(self.redis.hlen(key))
            has_more = total > limit
            rows: List[dict] = []
            for index, (image_id, payload) in enumerate(self.redis.hgetall(key).items()):
                rows.append(json.loads(payload))
                self.redis.hdel(key, image_id)
                if index + 1 >= limit:
                    break
            return rows, has_more

        with self._lock:
            image_map = self._results.get(session_id, {})
            image_ids = list(image_map.keys())
            has_more = len(image_ids) > limit
            rows = []
            for image_id in image_ids[:limit]:
                rows.append(json.loads(image_map[image_id]))
                del image_map[image_id]
            return rows, has_more

    def confirm_results(self, session_id: str, image_ids: List[str]) -> None:
        """确认结果并删除对应记录。"""

        if self.redis:
            key = self._result_key(session_id)
            for image_id in image_ids:
                self.redis.hdel(key, image_id)
            return

        with self._lock:
            bucket = self._results.get(session_id, {})
            for image_id in image_ids:
                bucket.pop(image_id, None)
