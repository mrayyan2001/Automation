import asyncio
import logging
import time
from socket import socket

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from common.config.config import (
    load_config,
)
from common.config.logger import (
    setup_logging,
)
from common.exception.global_exception_handler import (
    exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from lifespan import lifespan

HOST_KEY = "HOST"
PORT_KEY = "PORT"
RELOAD_KEY = "RELOAD"
HTTP_SERVER_KEY = "HTTP_SERVER"

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Production Scaffold API",
    version="1.0.0",
    description="A minimalist, scalable FastAPI boilerplate setup running on Kubernetes.",
    lifespan=lifespan,
)

app.add_exception_handler(
    Exception,
    exception_handler,
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


class StartupTimedServer(uvicorn.Server):
    async def startup(self, sockets: list[socket] | None = None) -> None:
        await super().startup(sockets)
        app.state.server_startup_ms = round(
            (time.perf_counter() - app.state.startup_started_at) * 1000, 2
        )


async def run_server(
    server_config: dict,
) -> None:
    """Launch the Uvicorn server using the configured server parameters."""
    config = uvicorn.Config(
        app=app,
        host=server_config[HOST_KEY],
        port=server_config[PORT_KEY],
        reload=server_config[RELOAD_KEY],
    )
    app.state.startup_started_at = time.perf_counter()
    server = StartupTimedServer(config)
    await server.serve()


async def main() -> None:
    """Load configuration ONCE and pass server configuration to Uvicorn."""
    config = load_config()
    app.state.config = config
    await run_server(config[HTTP_SERVER_KEY])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
