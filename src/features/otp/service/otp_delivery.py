from abc import ABC, abstractmethod

from features.otp.domain.otp_channel import OtpChannel


class OtpDelivery(ABC):
    channel: OtpChannel

    @abstractmethod
    async def send(self, receiver: str, subject: str, body: str) -> bool: ...
