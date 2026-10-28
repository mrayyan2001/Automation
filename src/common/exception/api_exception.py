"""Application-specific error types and exception metadata."""

from enum import (
    Enum,
)
from typing import (
    Any,
)


class ErrorType(Enum):
    """Define the complete API metadata for one application error."""

    UNKNOWN = (
        500,
        "UNKNOWN_ERROR",
        "An unexpected error occurred.",
    )
    INVALID_REQUEST = (
        400,
        "INVALID_REQUEST",
        "The request is invalid.",
    )
    VALIDATION_FAILED = (
        422,
        "VALIDATION_FAILED",
        "Request validation failed.",
    )
    UNAUTHORIZED = (
        401,
        "UNAUTHORIZED",
        "Authentication is required.",
    )
    FORBIDDEN = (
        403,
        "FORBIDDEN",
        "You are not allowed to perform this action.",
    )
    NOT_FOUND = (
        404,
        "NOT_FOUND",
        "The requested resource was not found.",
    )
    CONFLICT = (
        409,
        "CONFLICT",
        "The request conflicts with the current state.",
    )
    EMAIL_DELIVERY_FAILED = (
        502,
        "EMAIL_DELIVERY_FAILED",
        "The email could not be delivered.",
    )
    OTP_DELIVERY_FAILED = (
        502,
        "OTP_DELIVERY_FAILED",
        "The one-time password could not be delivered.",
    )
    INTERNAL_SERVER_ERROR = (
        500,
        "INTERNAL_SERVER_ERROR",
        "An internal server error occurred.",
    )
    NOT_IMPLEMENTED = (
        501,
        "NOT_IMPLEMENTED",
        "The request is not implemented",
    )
    VALUE_ERROR = (
        400,
        "VALUE_ERROR",
        "The provided value is invalid.",
    )

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message

    @property
    def string_code(
        self,
    ) -> str:
        """Return the stable string application error code."""
        return self.code


class ApiException(Exception):
    """Represent a business error defined by an :class:`ErrorType`.

    Args:
        error_type: Error metadata, including HTTP status and description.
        details: Optional structured data supplied by the developer.
    """

    def __init__(
        self,
        error_type: ErrorType,
        details: Any = None,
    ) -> None:
        if not isinstance(
            error_type,
            ErrorType,
        ):
            raise TypeError("error_type must be an ErrorType")
        self.error_type = error_type
        self.details = details
        super().__init__(error_type.message)
