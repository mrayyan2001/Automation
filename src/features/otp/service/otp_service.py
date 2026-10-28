from abc import ABC, abstractmethod
from uuid import UUID

from features.otp.domain.otp_channel import OtpChannel


class OtpService(ABC):
    @abstractmethod
    async def send_otp(
        self,
        receiver: str,
        channel: OtpChannel,
        user_id: UUID | None,
        purpose: str,
    ) -> str: ...

    @abstractmethod
    async def check_otp(
        self,
        otp: str,
        otp_token: str,
        user_id: UUID | None,
        purpose: str,
    ) -> str: ...

    @abstractmethod
    async def consume_confirmation_token(
        self, token: str, user_id: UUID | None, purpose: str
    ) -> bool: ...
