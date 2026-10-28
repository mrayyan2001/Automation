import asyncio
from datetime import timedelta
from typing import Any

import pytest

from common.health_check_client import HealthCheckClient
from context import create_application_context
from features.otp.service.default_otp_service import DefaultOtpService
from features.otp.service.otp_service import OtpService
from persistence.cache.cache_client import CacheClient
from persistence.cache.redis_client import RedisClient


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.last_set: tuple[str, str, int] | None = None
        self.deleted_key: str | None = None
        self.closed = False

    async def set(self, key: str, value: str, px: int) -> None:
        self.values[key] = value
        self.last_set = (key, value, px)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.deleted_key = key
        self.values.pop(key, None)

    async def aclose(self) -> None:
        self.closed = True


class FakeAppConfig:
    def __init__(self) -> None:
        self.config: dict[str, dict[str, Any]] = {
            "REDIS": {
                "HOST": "localhost",
                "PORT": 6379,
                "DB": 0,
                "PASSWORD": "",
                "MAX_CONNECTIONS": 10,
                "CONNECT_TIMEOUT_SECONDS": 1,
                "SOCKET_TIMEOUT_SECONDS": 1,
            }
        }


def test_redis_client_uses_expiring_pooled_client_operations() -> None:
    async def run_operations() -> None:
        client = RedisClient(FakeAppConfig())
        fake_redis = FakeRedis()
        client._client = fake_redis

        await client.set("session", {"active": True}, timedelta(milliseconds=1500))

        assert fake_redis.last_set == ("session", '{"active": true}', 1500)
        assert await client.get("session") == '{"active": true}'
        await client.delete("session")
        assert fake_redis.deleted_key == "session"
        assert await client.get("session") is None
        await client.aclose()
        assert fake_redis.closed

    asyncio.run(run_operations())


def test_redis_client_rejects_non_positive_ttl() -> None:
    async def run_set() -> None:
        client = RedisClient(FakeAppConfig())
        client._client = FakeRedis()
        await client.set("session", "value", timedelta(0))

    with pytest.raises(ValueError, match="Cache TTL must be greater than zero"):
        asyncio.run(run_set())


def test_application_context_discovers_redis_cache_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")

    context = create_application_context(
        ["features", "common", "persistence", "integrations"]
    )

    assert isinstance(context.get(CacheClient), RedisClient)
    assert isinstance(context.get(OtpService), DefaultOtpService)
    assert {
        client.health_check_name for client in context.get(list[HealthCheckClient])
    } == {
        "Redis",
        "Citus PostgreSQL",
        "LiteLLM",
    }
