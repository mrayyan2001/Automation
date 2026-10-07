"""Application-wide FastAPI exception handlers."""

import logging
from typing import (
    Any,
)

from fastapi import (
    Request,
)
from fastapi.encoders import (
    jsonable_encoder,
)
from fastapi.responses import (
    JSONResponse,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from common.exception.api_exception import (
    ApiException,
    ErrorType,
)
from common.exception.error_data import (
    ErrorData,
)

logger = logging.getLogger(__name__)


async def log_exception(
    exc: Exception,
    status_code: int,
) -> None:
    """Log a handled exception with safe diagnostic details."""
    logger.warning(
        "Exception [%d] %s: %s | Details: %s",
        status_code,
        type(exc).__name__,
        str(exc),
        getattr(
            exc,
            "details",
            None,
        ),
    )


def error_response(
    error_type: ErrorType,
    details: Any | None = None,
) -> JSONResponse:
    """Build the common API error response envelope."""
    content: dict[
        str,
        Any,
    ] = {
        "success": False,
        "errorData": ErrorData(
            errorCode=error_type.code,
            message=error_type.message,
            details=details,
        ).model_dump(exclude_none=True),
    }

    return JSONResponse(
        status_code=error_type.status_code,
        content=jsonable_encoder(content),
    )


async def exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Dispatch application errors while mapping everything else to unknown."""
    details = None
    error_type = ErrorType.UNKNOWN
    match exc:
        case ApiException():
            error_type = exc.error_type
            details = exc.details
        case NotImplementedError():
            error_type = ErrorType.NOT_IMPLEMENTED

    await log_exception(
        exc,
        error_type.status_code,
    )
    return error_response(
        error_type=error_type,
        details=details,
    )


async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Use the API envelope for invalid request parameters and bodies."""
    return error_response(ErrorType.VALIDATION_FAILED, exc.errors())


async def http_exception_handler(
    _request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Preserve HTTP status and headers while normalizing the error body."""
    error_type = next(
        (error for error in ErrorType if error.status_code == exc.status_code),
        ErrorType.UNKNOWN,
    )
    response = error_response(error_type, exc.detail)
    response.status_code = exc.status_code
    if exc.headers:
        response.headers.update(exc.headers)
    return response
