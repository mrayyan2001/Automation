"""HTTP endpoints for sending email notifications."""

from common.annotation.router import Controller, Post
from common.exception.api_exception import ApiException, ErrorType
from features.notfication.email.api.send_email_request import SendEmailRequest
from features.notfication.email.service.email_service import EmailService


@Controller("/api/v1/notifications/email")
class EmailRouter:
    @Post("/send")
    async def send_email(
        self, request: SendEmailRequest, email_service: EmailService
    ) -> bool:
        sent = await email_service.send_email(
            receiver=request.receiver,
            subject=request.subject,
            body=request.body,
        )
        if not sent:
            raise ApiException(ErrorType.EMAIL_DELIVERY_FAILED)
        return sent
