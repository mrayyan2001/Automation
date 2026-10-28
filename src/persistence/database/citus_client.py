import asyncio

import asyncpg

from app_config import AppConfig
from common.annotation.component import Component
from persistence.database.database_client import DatabaseClient


@Component
class CitusClient(DatabaseClient):
    def __init__(self, app_config: AppConfig) -> None:
        config = app_config.config["CITUS"]
        self._connection_options = {
            "host": config["HOST"],
            "port": int(config["PORT"]),
            "user": config["USER"],
            "password": config["PASSWORD"] or None,
            "database": config["DATABASE"],
            "timeout": float(config["CONNECT_TIMEOUT_SECONDS"]),
            "min_size": int(config["MIN_CONNECTIONS"]),
            "max_size": int(config["MAX_CONNECTIONS"]),
        }
        self._pool: asyncpg.Pool | None = None
        self._pool_lock = asyncio.Lock()

    @property
    def health_check_name(self) -> str:
        return "Citus PostgreSQL"

    async def health_check(self) -> None:
        if self._pool is None:
            async with self._pool_lock:
                if self._pool is None:
                    self._pool = await asyncpg.create_pool(**self._connection_options)
        async with self._pool.acquire() as connection:
            await connection.fetchval("SELECT 1")

    async def aclose(self) -> None:
        async with self._pool_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None
