from pydantic import BaseModel, ConfigDict, Field


class CreateBookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=120)
