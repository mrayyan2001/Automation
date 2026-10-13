import asyncio
import os
import tempfile
import unittest
from typing import Annotated
from unittest.mock import patch

import httpx

from common.annotation.qualifier import Qualifier
from references.book_catalog.app import app, lifespan
from references.book_catalog.domain.book import Book
from references.book_catalog.repositories.book_repository import BookRepository
from references.book_catalog.repositories.json_book_repository import JsonBookRepository
from references.book_catalog.repositories.sqlite_book_repository import (
    SqliteBookRepository,
)
from references.book_catalog.services.book_service import BookService


class ReferenceBookTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"REFERENCE_DATA_DIR": self.directory.name}
        )
        self.environment.start()
        self.lifespan = lifespan(app)
        await self.lifespan.__aenter__()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.environment.stop()
        self.directory.cleanup()

    async def test_selection_and_http_backends(self):
        context = app.state.context
        default = context.get(BookService)
        json_service = context.get(Annotated[BookService, Qualifier("json")])
        self.assertIsInstance(default.repository, SqliteBookRepository)
        self.assertIsInstance(json_service.repository, JsonBookRepository)
        self.assertIsInstance(context.get(BookRepository), SqliteBookRepository)
        self.assertEqual(
            {s.backend for s in context.get(list[BookService])}, {"sqlite", "json"}
        )
        for path, title in (("", "SQLite book"), ("/json", "JSON book")):
            response = await self.client.post(
                "/reference/books" + path, json={"title": title, "author": "Author"}
            )
            self.assertEqual(response.status_code, 201)
            response = await self.client.get("/reference/books" + path)
            self.assertEqual([b["title"] for b in response.json()["data"]], [title])
        result = await self.client.get("/reference/books/backends")
        self.assertEqual(
            {b["backend"]: b["count"] for b in result.json()["data"]},
            {"sqlite": 1, "json": 1},
        )
        created = (await self.client.get("/reference/books")).json()["data"][0]
        fetched = await self.client.get("/reference/books/" + created["id"])
        self.assertEqual(fetched.json()["data"], created)
        self.assertEqual(
            (await self.client.delete("/reference/books/" + created["id"])).status_code,
            200,
        )
        self.assertEqual(
            (await self.client.get("/reference/books/" + created["id"])).status_code,
            404,
        )
        invalid = await self.client.post(
            "/reference/books", json={"title": "  ", "author": "Author"}
        )
        self.assertEqual(invalid.status_code, 422)

    async def test_storage_persistence_and_concurrent_writes(self):
        for repository_type in (SqliteBookRepository, JsonBookRepository):
            with self.subTest(repository=repository_type.__name__):
                repository = await asyncio.to_thread(repository_type)
                books = [Book(str(i), f"Book {i}", "Author") for i in range(20)]
                await asyncio.gather(*(repository.save(book) for book in books))
                reopened = await asyncio.to_thread(repository_type)
                self.assertEqual(len(await reopened.find_all()), 20)
                replacement = Book("0", "Updated", "New author")
                await reopened.save(replacement)
                self.assertEqual(await repository.find_by_id("0"), replacement)
                self.assertTrue(await reopened.delete("0"))
                self.assertFalse(await reopened.delete("0"))
                self.assertIsNone(await repository.find_by_id("0"))
