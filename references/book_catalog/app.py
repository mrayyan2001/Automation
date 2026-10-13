"""Run with PYTHONPATH=src:. uv run uvicorn references.book_catalog.app:app."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from common.annotation.router import scan_routers, validate_router_dependencies
from common.exception.api_exception import ApiException
from common.exception.global_exception_handler import (
    exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from context import create_application_context

PACKAGE = "references.book_catalog"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Discovery and storage initialization run outside the event loop.
    routers = await asyncio.to_thread(scan_routers, PACKAGE)
    context = await asyncio.to_thread(create_application_context, [PACKAGE])
    await asyncio.to_thread(validate_router_dependencies, routers, context)
    app.state.context = context
    if not getattr(app.state, "routers_registered", False):
        for router in routers:
            app.include_router(router)
        app.state.routers_registered = True
        app.openapi_schema = None
    yield


app = FastAPI(title="Book catalog reference", lifespan=lifespan)
app.add_exception_handler(ApiException, exception_handler)
app.add_exception_handler(Exception, exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
