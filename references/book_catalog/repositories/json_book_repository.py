import asyncio
import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from common.annotation.component import Component
from common.annotation.qualifier import Qualifier
from references.book_catalog.domain.book import Book
from references.book_catalog.repositories.book_repository import BookRepository


@Component
@Qualifier("json")
class JsonBookRepository(BookRepository):
    def __init__(self) -> None:
        self.path = (
            Path(os.getenv("REFERENCE_DATA_DIR", "data/reference_books")) / "books.json"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        # Lock a stable sidecar file, not the data inode replaced by atomic writes.
        with self.lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _read(self) -> dict[str, Book]:
        if not self.path.exists():
            return {}
        return {
            item["id"]: Book(**item)
            for item in json.loads(self.path.read_text(encoding="utf-8"))
        }

    def _write(self, books: dict[str, Book]) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.path.parent, encoding="utf-8", delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(
                    [asdict(book) for book in books.values()],
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    async def find_all(self) -> list[Book]:
        return await asyncio.to_thread(self._find_all)

    def _find_all(self) -> list[Book]:
        with self._locked():
            return sorted(self._read().values(), key=lambda book: (book.title, book.id))

    async def find_by_id(self, book_id: str) -> Book | None:
        return await asyncio.to_thread(self._find_by_id, book_id)

    def _find_by_id(self, book_id: str) -> Book | None:
        with self._locked():
            return self._read().get(book_id)

    async def save(self, book: Book) -> None:
        await asyncio.to_thread(self._save, book)

    def _save(self, book: Book) -> None:
        with self._locked():
            books = self._read()
            books[book.id] = book
            self._write(books)

    async def delete(self, book_id: str) -> bool:
        return await asyncio.to_thread(self._delete, book_id)

    def _delete(self, book_id: str) -> bool:
        with self._locked():
            books = self._read()
            if book_id not in books:
                return False
            del books[book_id]
            self._write(books)
            return True
