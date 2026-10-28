from common.annotation.service import Service
from features.notfication.email.service.email_service import EmailService
from features.otp.domain.otp_channel import OtpChannel
from features.otp.service.otp_delivery import OtpDelivery


@Service
class EmailOtpDelivery(OtpDelivery):
    """Deliver OTP messages through the email notification service."""

    channel = OtpChannel.EMAIL

    def __init__(self, email_service: EmailService):
        self._email_service = email_service

    async def send(self, receiver: str, subject: str, body: str) -> bool:
        return await self._email_service.send_email(receiver, subject, body)
