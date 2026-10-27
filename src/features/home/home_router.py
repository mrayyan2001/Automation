from pathlib import Path
from typing import Annotated

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from common.annotation.qualifier import Qualifier
from common.annotation.router import Controller, Get
from features.home.home_service import HomeService

HOME_PAGE = Path(__file__).resolve().parents[3] / "pages" / "index.html"
templates = Jinja2Templates(directory=HOME_PAGE.parent)


@Controller("/")
class HomeRouter:
    @Get("/")
    async def home(
        self,
        request: Request,
        home_service: Annotated[HomeService, Qualifier("MhHomeService")],
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name=HOME_PAGE.name,
            context={"title": home_service.name, "tags": home_service.tags},
        )
