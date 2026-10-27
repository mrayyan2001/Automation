import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import yaml

from common.config.config import load_yaml
from features.notfication.email.service.smtp_email_service import SmtpEmailService

COMMON_CONFIG_PATH = (
    Path(__file__).parents[4] / "src" / "common" / "config" / "common.yaml"
)


def create_service() -> SmtpEmailService:
    config = yaml.safe_load(COMMON_CONFIG_PATH.read_text(encoding="utf-8"))
    config["SMTP_EMAIL"].update(
        {
            "HOST": "smtp.example.test",
            "PORT": 587,
            "USERNAME": "mailer",
            "PASSWORD": "secret",
            "SENDER": "sender@example.test",
            "STARTTLS": True,
            "TIMEOUT": 3,
        }
    )
    return SmtpEmailService(SimpleNamespace(config=config))


class SmtpEmailServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_smtp_configuration_defaults_to_google_smtp(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            smtp_config = load_yaml(COMMON_CONFIG_PATH)["SMTP_EMAIL"]

        self.assertEqual(smtp_config["HOST"], "smtp.gmail.com")
        self.assertEqual(smtp_config["PORT"], 587)
        self.assertIs(smtp_config["STARTTLS"], True)

    async def test_send_email_sends_message_and_authenticates(self) -> None:
        service = create_service()
        smtp = MagicMock()
        smtp.send_message.return_value = {}

        with patch(
            "features.notfication.email.service.smtp_email_service.smtplib.SMTP"
        ) as smtp_factory:
            smtp_factory.return_value.__enter__.return_value = smtp

            result = await service.send_email(
                "receiver@example.test", "Subject", "Body"
            )

        self.assertTrue(result)
        smtp_factory.assert_called_once_with("smtp.example.test", 587, timeout=3)
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with("mailer", "secret")
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["From"], "sender@example.test")
        self.assertEqual(message["To"], "receiver@example.test")
        self.assertEqual(message["Subject"], "Subject")
        self.assertEqual(message.get_content(), "Body\n")

    async def test_send_email_returns_false_when_recipient_is_refused(self) -> None:
        service = create_service()
        smtp = MagicMock()
        smtp.send_message.return_value = {"receiver@example.test": (550, b"Rejected")}

        with patch(
            "features.notfication.email.service.smtp_email_service.smtplib.SMTP"
        ) as smtp_factory:
            smtp_factory.return_value.__enter__.return_value = smtp

            result = await service.send_email(
                "receiver@example.test", "Subject", "Body"
            )

        self.assertFalse(result)

    async def test_send_email_returns_false_when_smtp_raises(self) -> None:
        service = create_service()

        with patch(
            "features.notfication.email.service.smtp_email_service.smtplib.SMTP",
            side_effect=OSError("connection failed"),
        ):
            result = await service.send_email(
                "receiver@example.test", "Subject", "Body"
            )

        self.assertFalse(result)
