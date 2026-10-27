"""Verify discovery does not block lifespan startup or the event loop."""

import asyncio
import threading
import unittest
from unittest.mock import patch

import httpx
from fastapi import APIRouter, FastAPI

from lifespan import lifespan


class BackgroundStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_responds_while_discovery_is_blocked(self):
        app = FastAPI(lifespan=lifespan)
        app.state.config = {}
        started = threading.Event()
        release = threading.Event()
        router = APIRouter()

        @router.get("/discovered")
        async def discovered():
            return {"ready": True}

        def scan(_packages):
            started.set()
            if not release.wait(timeout=5):
                raise TimeoutError("Test did not release discovery")
            return [router]

        with (
            patch("lifespan.scan_routers", side_effect=scan),
            patch("lifespan.create_application_context", return_value={}),
        ):
            async with app.router.lifespan_context(app):
                try:
                    for _ in range(100):
                        if started.is_set():
                            break
                        await asyncio.sleep(0.01)
                    self.assertTrue(started.is_set())
                    self.assertFalse(app.state.context_task.done())
                    app.openapi()
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        self.assertEqual(
                            (await client.get("/openapi.json")).status_code, 200
                        )
                        self.assertEqual(
                            (await client.get("/discovered")).status_code, 404
                        )
                        release.set()
                        await asyncio.wait_for(app.state.context_task, timeout=5)
                        self.assertEqual(
                            (await client.get("/discovered")).json(), {"ready": True}
                        )
                        self.assertIn("/discovered", app.openapi()["paths"])
                finally:
                    release.set()

    async def test_shutdown_cancels_initialization(self):
        app = FastAPI(lifespan=lifespan)
        app.state.config = {}

        async def initialize(_app):
            await asyncio.Event().wait()

        with patch("lifespan.initialize_context", new=initialize):
            async with app.router.lifespan_context(app):
                await asyncio.sleep(0)
                task = app.state.context_task
            self.assertTrue(task.cancelled())
