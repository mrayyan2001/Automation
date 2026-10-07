import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.annotation.router import scan_routers
from common.config.config import load_config
from context import create_application_context

logger = logging.getLogger(__name__)

def log_task_error(task: asyncio.Task) -> None:
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error(
            "Background task failed",
            exc_info=(type(error), error, error.__traceback__),
        )


async def initialize_context(app: FastAPI) -> None:
    """Discover routes and build dependencies without delaying server startup."""

    packages = ["features", "common"]
    logger.info("Scanning application controllers in the background...")
    routers = await asyncio.to_thread(scan_routers, packages)
    app.state.context = await asyncio.to_thread(
        create_application_context,
        packages,
    )
    # Publish routes on the event loop after their dependencies are ready.
    if not getattr(app.state, "routers_registered", False):
        for router in routers:
            app.include_router(router)
        app.state.routers_registered = True
    app.openapi_schema = None
    logger.info("Application controllers and dependencies are ready.")


async def shutdown(tasks: list[asyncio.Task]) -> None:
    logger.info("Server shutting down. Cleaning up resources...")
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "config"):
        app.state.config = load_config()

    context_task = asyncio.create_task(initialize_context(app))
    context_task.add_done_callback(log_task_error)
    app.state.context_task = context_task
    try:
        yield
    finally:
        await shutdown([context_task])
    logger.info("Resource cleanup complete.")
