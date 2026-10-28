from uuid import UUID

from pydantic import BaseModel, Field

from features.otp.domain.otp_channel import OtpChannel


class SendOtpRequest(BaseModel):
    receiver: str = Field(min_length=3)
    channel: OtpChannel
    user_id: UUID | None = None
    purpose: str = Field(min_length=1)


class CheckOtpRequest(BaseModel):
    otp: str = Field(min_length=1)
    otp_token: str = Field(min_length=1)
    user_id: UUID | None = None
    purpose: str = Field(min_length=1)
