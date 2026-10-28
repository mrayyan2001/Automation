import asyncio
from typing import Any

import pytest

from integrations.litellm_client import LiteLLMClient


class FakeAppConfig:
    def __init__(self) -> None:
        self.config: dict[str, dict[str, Any]] = {
            "LITELLM": {
                "BASE_URL": "http://litellm:4000/",
                "API_KEY": "test-key",
                "HEALTH_CHECK_TIMEOUT_SECONDS": 2,
            }
        }


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


class FakeHttpxClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requested_path: str | None = None
        self.closed = False

    async def get(self, path: str) -> FakeResponse:
        self.requested_path = path
        if self.error:
            raise self.error
        return FakeResponse()

    async def aclose(self) -> None:
        self.closed = True


def test_litellm_client_checks_readiness_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = LiteLLMClient(FakeAppConfig())
    fake_httpx_client = FakeHttpxClient()
    monkeypatch.setattr(client, "_client", fake_httpx_client)

    async def run_check() -> None:
        await client.health_check()
        await client.aclose()

    asyncio.run(run_check())

    assert fake_httpx_client.requested_path == "/health/readiness"
    assert fake_httpx_client.closed


def test_litellm_client_propagates_unhealthy_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = LiteLLMClient(FakeAppConfig())
    monkeypatch.setattr(client, "_client", FakeHttpxClient(RuntimeError("unavailable")))

    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(client.health_check())
