import asyncio
from pathlib import Path
from time import perf_counter

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from common.annotation.router import Controller, Get
from common.health_check_client import HealthCheckClient

HOME_PAGE = Path(__file__).resolve().parents[3] / "pages" / "index.html"
templates = Jinja2Templates(directory=HOME_PAGE.parent)


@Controller("/")
class HomeRouter:
    @Get("/")
    async def home(
        self,
        request: Request,
        health_check_clients: list[HealthCheckClient],
    ) -> HTMLResponse:
        health_checks = await asyncio.gather(
            *(check_client(client) for client in health_check_clients)
        )
        health_status = (
            "unhealthy"
            if any(check["status"] == "unhealthy" for check in health_checks)
            else "healthy"
        )
        return templates.TemplateResponse(
            request=request,
            name=HOME_PAGE.name,
            context={
                "title": "HM Company",
                "health_status": health_status,
                "health_checks": health_checks,
            },
        )


async def check_client(client: HealthCheckClient) -> dict[str, str | float]:
    started_at = perf_counter()
    try:
        await client.health_check()
        status = "healthy"
    except Exception:  # noqa: BLE001
        status = "unhealthy"
    response_time_ms = round((perf_counter() - started_at) * 1000, 2)
    return {
        "name": client.health_check_name,
        "status": status,
        "response_time_ms": response_time_ms,
    }
