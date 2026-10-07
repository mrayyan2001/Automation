"""Standard envelope for successful controller results."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    """Keep the endpoint's data type in validation and OpenAPI schemas."""

    success: Literal[True] = True
    data: DataT
