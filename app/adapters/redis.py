"""Redis 基础设施适配器。"""

from __future__ import annotations

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
                    RedisClient._pool = ConnectionPool(
                        host=kwargs.get("host", settings.redis.host),
                        port=kwargs.get("port", settings.redis.port),
                        db=kwargs.get("db", settings.redis.database),
                        password=kwargs.get("password", settings.redis.password),
                        encoding="utf-8",
                        decode_responses=True,
                    )

        super().__init__(connection_pool=RedisClient._pool)
