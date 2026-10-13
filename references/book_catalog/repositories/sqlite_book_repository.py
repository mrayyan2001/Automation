import asyncio
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from common.annotation.component import Component
from common.annotation.primary import Primary
from common.annotation.qualifier import Qualifier
from references.book_catalog.domain.book import Book
from references.book_catalog.repositories.book_repository import BookRepository


@Component
@Primary
@Qualifier("sqlite")
class SqliteBookRepository(BookRepository):
    def __init__(self) -> None:
        self.path = (
            Path(os.getenv("REFERENCE_DATA_DIR", "data/reference_books"))
            / "books.sqlite3"
        )
        # Constructors are built in a worker thread by application initialization.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS books(id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    async def find_all(self) -> list[Book]:
        return await asyncio.to_thread(self._find_all)

    def _find_all(self) -> list[Book]:
        with closing(self._connect()) as db:
            return [
                Book(*row)
                for row in db.execute(
                    "SELECT id,title,author FROM books ORDER BY title,id"
                )
            ]

    async def find_by_id(self, book_id: str) -> Book | None:
        return await asyncio.to_thread(self._find_by_id, book_id)

    def _find_by_id(self, book_id: str) -> Book | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT id,title,author FROM books WHERE id=?", (book_id,)
            ).fetchone()
            return Book(*row) if row else None

    async def save(self, book: Book) -> None:
        await asyncio.to_thread(self._save, book)

    def _save(self, book: Book) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO books VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,author=excluded.author",
                (book.id, book.title, book.author),
            )

    async def delete(self, book_id: str) -> bool:
        return await asyncio.to_thread(self._delete, book_id)

    def _delete(self, book_id: str) -> bool:
        with closing(self._connect()) as db, db:
            return db.execute("DELETE FROM books WHERE id=?", (book_id,)).rowcount > 0
