from pathlib import Path
from time import perf_counter
from typing import Annotated

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from redis.exceptions import RedisError

from common.annotation.qualifier import Qualifier
from common.annotation.router import Controller, Get
from features.home.home_service import HomeService
from persistence.cache.cache_client import CacheClient

HOME_PAGE = Path(__file__).resolve().parents[3] / "pages" / "index.html"
templates = Jinja2Templates(directory=HOME_PAGE.parent)


@Controller("/")
class HomeRouter:
    @Get("/")
    async def home(
        self,
        request: Request,
        home_service: Annotated[HomeService, Qualifier("MhHomeService")],
        cache_client: CacheClient,
    ) -> HTMLResponse:
        dependency_started_at = perf_counter()
        try:
            await cache_client.health_check()
            dependency_status = "healthy"
        except (RedisError, OSError, TimeoutError):
            dependency_status = "unhealthy"
        dependency_response_time_ms = round(
            (perf_counter() - dependency_started_at) * 1000, 2
        )
        return templates.TemplateResponse(
            request=request,
            name=HOME_PAGE.name,
            context={
                "title": home_service.name,
                "tags": home_service.tags,
                "health_status": dependency_status,
                "health_response_time_ms": dependency_response_time_ms,
            },
        )
