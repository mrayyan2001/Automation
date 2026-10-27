import unittest

import pytest
from pydantic import ValidationError

from common.exception.api_exception import ApiException, ErrorType
from features.notfication.email.api.email_router import EmailRouter
from features.notfication.email.api.send_email_request import SendEmailRequest


def test_send_email_route_uses_versioned_api_path() -> None:
    route = EmailRouter.__router__.routes[0]

    assert route.path == "/api/v1/notifications/email/send"
    assert route.methods == {"POST"}


class FakeEmailService:
    def __init__(self, send_result: bool = True) -> None:
        self.sent_email: tuple[str, str, str] | None = None
        self.send_result = send_result

    async def send_email(self, receiver: str, subject: str, body: str) -> bool:
        self.sent_email = (receiver, subject, body)
        return self.send_result


class EmailRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_email_route_passes_request_to_service(self) -> None:
        service = FakeEmailService()
        request = SendEmailRequest(
            receiver="recipient@example.com",
            subject="Hello",
            body="Message",
        )

        result = await EmailRouter.send_email(EmailRouter(), request, service)

        self.assertTrue(result)
        self.assertEqual(
            service.sent_email, ("recipient@example.com", "Hello", "Message")
        )

    async def test_send_email_route_raises_api_error_when_service_returns_false(
        self,
    ) -> None:
        service = FakeEmailService(send_result=False)
        request = SendEmailRequest(
            receiver="recipient@example.com",
            subject="Hello",
            body="Message",
        )

        with self.assertRaises(ApiException) as error:
            await EmailRouter.send_email(EmailRouter(), request, service)

        self.assertIs(error.exception.error_type, ErrorType.EMAIL_DELIVERY_FAILED)
        self.assertEqual(error.exception.error_type.status_code, 502)


@pytest.mark.parametrize(
    "payload",
    [
        {"receiver": "", "subject": "Hello", "body": "Message"},
        {"receiver": "recipient@example.com", "subject": "", "body": "Message"},
        {"receiver": "recipient@example.com", "subject": "Hello", "body": ""},
    ],
)
def test_send_email_request_rejects_empty_required_values(
    payload: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        SendEmailRequest.model_validate(payload)
