import json
from datetime import timedelta
from typing import Any

from redis.asyncio import Redis

from app_config import AppConfig
from common.annotation.component import Component
from persistence.cache.cache_client import CacheClient


@Component
class RedisClient(CacheClient):
    def __init__(self, app_config: AppConfig):
        config = app_config.config["REDIS"]
        self._client = Redis(
            host=config["HOST"],
            port=int(config["PORT"]),
            db=int(config["DB"]),
            password=config["PASSWORD"] or None,
            max_connections=int(config["MAX_CONNECTIONS"]),
            socket_connect_timeout=float(config["CONNECT_TIMEOUT_SECONDS"]),
            socket_timeout=float(config["SOCKET_TIMEOUT_SECONDS"]),
            decode_responses=True,
        )

    async def set(self, key: str, value: Any, ttl: timedelta) -> None:
        ttl_milliseconds = int(ttl.total_seconds() * 1000)
        if ttl_milliseconds <= 0:
            raise ValueError("Cache TTL must be greater than zero")
        encoded_value = value if isinstance(value, str) else json.dumps(value)
        await self._client.set(key, encoded_value, px=ttl_milliseconds)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def health_check(self) -> None:
        await self._client.ping()

    async def aclose(self) -> None:
        """Close the client and its managed connection pool."""
        await self._client.aclose()
