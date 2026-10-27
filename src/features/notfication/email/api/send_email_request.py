"""HTTP request model for sending an email."""

from pydantic import BaseModel, Field


class SendEmailRequest(BaseModel):
    receiver: str = Field(min_length=3)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
