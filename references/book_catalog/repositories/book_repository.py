from abc import ABC, abstractmethod

from references.book_catalog.domain.book import Book


class BookRepository(ABC):
    @abstractmethod
    async def find_all(self) -> list[Book]: ...

    @abstractmethod
    async def find_by_id(self, book_id: str) -> Book | None: ...

    @abstractmethod
    async def save(self, book: Book) -> None: ...

    @abstractmethod
    async def delete(self, book_id: str) -> bool: ...
