from pathlib import Path

from fastapi.responses import FileResponse

from common.annotation.router import Controller, Get

HOME_PAGE = Path(__file__).resolve().parents[3] / "pages" / "index.html"


@Controller("/")
class HomeRouter:
    @Get("/")
    async def home(self) -> FileResponse:
        return FileResponse(HOME_PAGE, media_type="text/html")
