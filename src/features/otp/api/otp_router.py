"""HTTP endpoints for requesting and verifying one-time passwords."""

from common.annotation.router import Controller, Post
from features.otp.api.otp_requests import CheckOtpRequest, SendOtpRequest
from features.otp.service.otp_service import OtpService


@Controller("/api/v1/otp")
class OtpRouter:
    @Post("/send")
    async def send_otp(self, request: SendOtpRequest, otp_service: OtpService) -> str:
        return await otp_service.send_otp(
            receiver=request.receiver,
            channel=request.channel,
            user_id=request.user_id,
            purpose=request.purpose,
        )

    @Post("/check")
    async def check_otp(self, request: CheckOtpRequest, otp_service: OtpService) -> str:
        return await otp_service.check_otp(
            otp=request.otp,
            otp_token=request.otp_token,
            user_id=request.user_id,
            purpose=request.purpose,
        )
