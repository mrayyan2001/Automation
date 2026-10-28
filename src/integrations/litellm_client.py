import httpx

from app_config import AppConfig
from common.annotation.component import Component
from common.health_check_client import HealthCheckClient


@Component
class LiteLLMClient(HealthCheckClient):
    def __init__(self, app_config: AppConfig) -> None:
        config = app_config.config["LITELLM"]
        headers = {}
        if api_key := config["API_KEY"]:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=config["BASE_URL"].rstrip("/"),
            headers=headers,
            timeout=float(config["HEALTH_CHECK_TIMEOUT_SECONDS"]),
        )

    async def health_check(self) -> None:
        response = await self._client.get("/health/readiness")
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
