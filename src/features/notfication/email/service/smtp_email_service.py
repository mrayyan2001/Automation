"""SMTP-backed email service."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app_config import AppConfig
from common.annotation.service import Service
from features.notfication.email.service.email_service import EmailService

logger = logging.getLogger(__name__)


@Service
class SmtpEmailService(EmailService):
    """Send plain-text email through the configured SMTP server."""

    def __init__(self, app_config: AppConfig) -> None:
        self._config = app_config.config["SMTP_EMAIL"]

    async def send_email(self, receiver: str, subject: str, body: str) -> bool:
        """Send an email and return whether the SMTP server accepted it."""
        return await asyncio.to_thread(self._send_email, receiver, subject, body)

    def _send_email(self, receiver: str, subject: str, body: str) -> bool:
        message = EmailMessage()
        message["From"] = self._config["SENDER"]
        message["To"] = receiver
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(
                self._config["HOST"],
                self._config["PORT"],
                timeout=self._config["TIMEOUT"],
            ) as smtp:
                if self._config["STARTTLS"]:
                    smtp.starttls()
                username = self._config["USERNAME"]
                password = self._config["PASSWORD"]
                if username:
                    smtp.login(username, password)
                refused_recipients = smtp.send_message(message)
            return not refused_recipients
        except (OSError, smtplib.SMTPException, ValueError):
            logger.exception("Could not send email to %s", receiver)
            return False
