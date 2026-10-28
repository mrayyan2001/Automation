import asyncio
from asyncio import Event
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from lifespan import lifespan


def test_lifespan_runs_context_initialization_in_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run_lifespan() -> None:
        app = FastAPI()
        initialization_started = Event()
        allow_initialization_to_finish = Event()
        resource_closed = False

        class FakeResource:
            async def aclose(self) -> None:
                nonlocal resource_closed
                resource_closed = True

        async def initialize_context_in_background(app: FastAPI) -> None:
            initialization_started.set()
            await allow_initialization_to_finish.wait()
            app.state.routers_registered = True
            app.state.context = SimpleNamespace(beans={FakeResource: FakeResource()})

        monkeypatch.setattr(
            "lifespan.initialize_context", initialize_context_in_background
        )
        monkeypatch.setattr("lifespan.load_config", dict)

        async with lifespan(app):
            await asyncio.wait_for(initialization_started.wait(), timeout=1)
            assert not getattr(app.state, "routers_registered", False)
            allow_initialization_to_finish.set()
            await app.state.context_task

        assert app.state.routers_registered
        assert resource_closed

    monkeypatch.setenv("APP_ENV", "dev")
    asyncio.run(run_lifespan())
