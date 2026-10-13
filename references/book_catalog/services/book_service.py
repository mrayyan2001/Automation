from abc import ABC, abstractmethod

from references.book_catalog.domain.book import Book


class BookService(ABC):
    @property
    @abstractmethod
    def backend(self) -> str: ...

    @abstractmethod
    async def find_all(self) -> list[Book]: ...

    @abstractmethod
    async def find_by_id(self, book_id: str) -> Book: ...

    @abstractmethod
    async def create(self, title: str, author: str) -> Book: ...

    @abstractmethod
    async def delete(self, book_id: str) -> None: ...
