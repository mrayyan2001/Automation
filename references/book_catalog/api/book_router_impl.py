from typing import Annotated

from common.annotation.qualifier import Qualifier
from common.annotation.router import Controller, Delete, Get, Post
from references.book_catalog.api.book_router import BookRouter
from references.book_catalog.api.schemas import CreateBookRequest
from references.book_catalog.domain.book import Book
from references.book_catalog.services.book_service import BookService


@Controller("/reference/books")
class BookRouterImpl(BookRouter):
    def __init__(self, service: BookService, services: list[BookService]) -> None:
        # Single injection selects @Primary. List injection includes both services.
        self.service = service
        self.services = services

    @Get("/backends")
    async def backends(self) -> list[dict[str, str | int]]:
        return [
            {"backend": service.backend, "count": len(await service.find_all())}
            for service in self.services
        ]

    @Get("/json")
    async def json_books(
        self, service: Annotated[BookService, Qualifier("json")]
    ) -> list[Book]:
        # Qualifiers also work on handler parameters, not only constructors.
        return await service.find_all()

    @Post("/json", status_code=201)
    async def create_json(
        self,
        body: CreateBookRequest,
        service: Annotated[BookService, Qualifier("json")],
    ) -> Book:
        return await service.create(body.title, body.author)

    @Get("")
    async def find_all(self) -> list[Book]:
        return await self.service.find_all()

    @Post("", status_code=201)
    async def create(self, body: CreateBookRequest) -> Book:
        return await self.service.create(body.title, body.author)

    @Get("/{book_id}")
    async def find_by_id(self, book_id: str) -> Book:
        return await self.service.find_by_id(book_id)

    @Delete("/{book_id}")
    async def delete(self, book_id: str) -> None:
        await self.service.delete(book_id)
