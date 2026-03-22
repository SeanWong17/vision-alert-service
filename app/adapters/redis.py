"""Redis 基础设施适配器。"""

from __future__ import annotations

import os
from threading import Lock

from redis import ConnectionPool, Redis

from app.common.settings import settings


class RedisClient(Redis):
    """带连接池复用能力的 Redis 客户端。"""

    _pool: ConnectionPool | None = None
    _lock = Lock()

    def __init__(self, **kwargs):
        """初始化 Redis 连接，首次创建共享连接池。"""

        if RedisClient._pool is None:
            with RedisClient._lock:
                if RedisClient._pool is None:
                    host = kwargs.get("host") or os.getenv("ALERT_REDIS_HOST", settings.redis.host)
                    port = int(kwargs.get("port", os.getenv("ALERT_REDIS_PORT", settings.redis.port)))
                    db = int(kwargs.get("db", os.getenv("ALERT_REDIS_DB", settings.redis.database)))
                    password = kwargs.get("password", os.getenv("ALERT_REDIS_PASSWORD", settings.redis.password))
                    RedisClient._pool = ConnectionPool(
                        host=host,
                        port=port,
                        db=db,
                        password=password,
                        encoding="utf-8",
                        decode_responses=True,
                    )

        super().__init__(connection_pool=RedisClient._pool)
