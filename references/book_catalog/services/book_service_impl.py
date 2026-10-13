from typing import Annotated
from uuid import uuid4

from common.annotation.primary import Primary
from common.annotation.qualifier import Qualifier
from common.annotation.service import Service
from common.exception.api_exception import ApiException, ErrorType
from references.book_catalog.domain.book import Book
from references.book_catalog.repositories.book_repository import BookRepository
from references.book_catalog.services.book_service import BookService


@Service
@Primary
@Qualifier("sqlite")
class BookServiceImpl(BookService):
    def __init__(
        self, repository: Annotated[BookRepository, Qualifier("sqlite")]
    ) -> None:
        self.repository = repository

    @property
    def backend(self) -> str:
        return "sqlite"

    async def find_all(self) -> list[Book]:
        return await self.repository.find_all()

    async def find_by_id(self, book_id: str) -> Book:
        book = await self.repository.find_by_id(book_id)
        if book is None:
            raise ApiException(ErrorType.NOT_FOUND, "Book not found")
        return book

    async def create(self, title: str, author: str) -> Book:
        title, author = title.strip(), author.strip()
        if not title or not author or len(title) > 200 or len(author) > 120:
            raise ApiException(
                ErrorType.INVALID_REQUEST,
                "Title and author must be nonempty and within length limits",
            )
        book = Book(str(uuid4()), title, author)
        await self.repository.save(book)
        return book

    async def delete(self, book_id: str) -> None:
        if not await self.repository.delete(book_id):
            raise ApiException(ErrorType.NOT_FOUND, "Book not found")
