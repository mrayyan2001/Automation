"""Models used by the standard API error response."""

from typing import (
    Any,
)

from pydantic import (
    BaseModel,
)


class ErrorData(BaseModel):
    """Serializable details for an API error."""

    errorCode: str
    message: str
    details: Any | None = None
