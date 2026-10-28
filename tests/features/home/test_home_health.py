import asyncio
from types import SimpleNamespace

from starlette.requests import Request

from common.health_check_client import HealthCheckClient
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


class FakeDatabaseClient(HealthCheckClient):
    @property
    def health_check_name(self) -> str:
        return "Fake PostgreSQL"

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def health_check(self) -> None:
        if self.error:
            raise self.error


def build_request(state: SimpleNamespace | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": SimpleNamespace(state=state or SimpleNamespace()),
        }
    )


def test_home_page_reports_redis_status_and_response_time() -> None:
    async def run_request() -> None:
        response = await HomeRouter().home(
            build_request(),
            [FakeCacheClient(), FakeDatabaseClient()],
        )
        context = response.context

        assert response.status_code == 200
        assert context["health_status"] == "healthy"
        assert [check["status"] for check in context["health_checks"]] == [
            "healthy",
            "healthy",
        ]
        assert all(check["response_time_ms"] >= 0 for check in context["health_checks"])

    asyncio.run(run_request())


def test_home_page_reports_unavailable_redis() -> None:
    async def run_request() -> None:
        response = await HomeRouter().home(
            build_request(),
            [FakeCacheClient(ConnectionError()), FakeDatabaseClient()],
        )

        assert response.context["health_status"] == "unhealthy"
        assert [check["status"] for check in response.context["health_checks"]] == [
            "unhealthy",
            "healthy",
        ]

    asyncio.run(run_request())


def test_home_page_reports_unavailable_citus() -> None:
    async def run_request() -> None:
        response = await HomeRouter().home(
            build_request(),
            [FakeCacheClient(), FakeDatabaseClient(ConnectionError())],
        )

        assert response.context["health_status"] == "unhealthy"
        assert [check["status"] for check in response.context["health_checks"]] == [
            "healthy",
            "unhealthy",
        ]

    asyncio.run(run_request())


def test_home_page_shows_server_and_di_startup_times() -> None:
    async def run_request() -> None:
        request = build_request(
            SimpleNamespace(server_startup_ms=120.5, dependency_ready_ms=428.1)
        )
        response = await HomeRouter().home(request, [FakeCacheClient()])

        assert response.context["server_startup_ms"] == 120.5
        assert response.context["dependency_ready_ms"] == 428.1

    asyncio.run(run_request())
