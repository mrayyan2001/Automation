import asyncio
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Protocol, runtime_checkable

from fastapi import FastAPI

from common.annotation.common.discovery import iter_modules
from common.annotation.router import (
    scan_routers_in_modules,
    validate_router_dependencies,
)
from common.config.config import load_config
from context import ApplicationContext, create_application_context

logger = logging.getLogger(__name__)


@runtime_checkable
class AsyncClosable(Protocol):
    async def aclose(self) -> None: ...


def log_task_error(task: asyncio.Task) -> None:
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error(
            "Background task failed",
            exc_info=(type(error), error, error.__traceback__),
        )


async def initialize_context(app: FastAPI) -> None:
    """Discover routes and build dependencies without delaying server startup."""

    startup_started_at = getattr(app.state, "startup_started_at", perf_counter())
    packages = ["features", "common", "persistence", "integrations"]
    logger.info("Scanning application controllers in the background...")
    modules = await asyncio.to_thread(lambda: list(iter_modules(packages)))
    routers = scan_routers_in_modules(modules)
    context = await asyncio.to_thread(
        create_application_context,
        packages,
        modules,
    )
    await asyncio.to_thread(validate_router_dependencies, routers, context)
    app.state.context = context
    # Publish routes on the event loop after their dependencies are ready.
    if not getattr(app.state, "routers_registered", False):
        for router in routers:
            app.include_router(router)
        app.state.routers_registered = True
    app.openapi_schema = None
    app.state.dependency_ready_ms = round(
        (perf_counter() - startup_started_at) * 1000, 2
    )
    logger.info("Application controllers and dependencies are ready.")


async def shutdown(tasks: list[asyncio.Task], app: FastAPI) -> None:
    logger.info("Server shutting down. Cleaning up resources...")
    for task in (task for task in tasks if not task.done()):
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    context: ApplicationContext | None = getattr(app.state, "context", None)
    if context is None:
        return
    for bean in reversed(tuple(context.beans.values())):
        if isinstance(bean, AsyncClosable):
            await bean.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "startup_started_at"):
        app.state.startup_started_at = perf_counter()
    if not hasattr(app.state, "config"):
        app.state.config = load_config()

    context_task = asyncio.create_task(initialize_context(app))
    context_task.add_done_callback(log_task_error)
    app.state.context_task = context_task
    try:
        yield
    finally:
        await shutdown([context_task], app)
    logger.info("Resource cleanup complete.")
