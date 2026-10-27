"""Standard envelope for successful controller results."""

from typing import Literal, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class SuccessResponse[DataT](BaseModel):
    """Keep the endpoint's data type in validation and OpenAPI schemas."""

    success: Literal[True] = True
    data: DataT
