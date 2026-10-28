import asyncio
from unittest.mock import Mock

from starlette.requests import Request

from features.home.home_router import HomeRouter
from persistence.cache.cache_client import CacheClient


class FakeCacheClient(CacheClient):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def set(self, key, value, ttl) -> None:
        raise NotImplementedError

    async def get(self, key):
        raise NotImplementedError

    async def delete(self, key) -> None:
        raise NotImplementedError

    async def health_check(self) -> None:
        if self.error:
            raise self.error


def build_request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def test_home_page_reports_redis_status_and_response_time() -> None:
    async def run_request() -> None:
        response = await HomeRouter().home(
            build_request(), Mock(name="Home", tags=[]), FakeCacheClient()
        )
        context = response.context

        assert response.status_code == 200
        assert context["health_status"] == "healthy"
        assert context["health_response_time_ms"] >= 0

    asyncio.run(run_request())


def test_home_page_reports_unavailable_redis() -> None:
    async def run_request() -> None:
        response = await HomeRouter().home(
            build_request(),
            Mock(name="Home", tags=[]),
            FakeCacheClient(ConnectionError()),
        )

        assert response.context["health_status"] == "unhealthy"
        assert response.context["health_response_time_ms"] >= 0

    asyncio.run(run_request())
