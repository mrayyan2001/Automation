import json
import secrets
import string
from datetime import timedelta
from uuid import UUID, uuid4

from app_config import AppConfig
from common.annotation.service import Service
from common.exception.api_exception import ApiException, ErrorType
from features.otp.domain.otp_channel import OtpChannel
from features.otp.service.otp_delivery import OtpDelivery
from features.otp.service.otp_service import OtpService
from persistence.cache.cache_client import CacheClient


@Service
class DefaultOtpService(OtpService):
    """Coordinate OTP caching, delivery, retry handling, and confirmation."""

    def __init__(
        self,
        cache_client: CacheClient,
        app_config: AppConfig,
        deliveries: list[OtpDelivery],
    ):
        self._cache_client = cache_client
        self._deliveries = {delivery.channel: delivery for delivery in deliveries}
        otp_config = app_config.config["OTP"]
        self._is_dev = bool(otp_config["IS_DEV"])
        self._ttl = timedelta(seconds=int(otp_config["TTL_SECONDS"]))
        self._confirm_ttl = timedelta(seconds=int(otp_config["CONFIRM_TTL_SECONDS"]))
        self._max_retry = int(otp_config["MAX_RETRY"])
        self._confirm_usage = int(otp_config["CONFIRM_USAGE"])
        self._only_digits = bool(otp_config["ONLY_DIGITS"])
        self._length = int(otp_config["LENGTH"])
        self._subject = otp_config["SUBJECT"]
        self._body_template = otp_config["BODY"]

        if self._ttl.total_seconds() <= 0:
            raise ValueError("OTP TTL_SECONDS must be positive")
        if self._max_retry <= 0:
            raise ValueError("OTP MAX_RETRY must be positive")
        if self._confirm_ttl.total_seconds() <= 0:
            raise ValueError("OTP CONFIRM_TTL_SECONDS must be positive")
        if self._confirm_usage <= 0:
            raise ValueError("OTP CONFIRM_USAGE must be positive")
        if self._length <= 0:
            raise ValueError("OTP LENGTH must be positive")

    async def _generate_otp(self) -> str:
        """Generate an OTP using the shared configuration."""
        if self._is_dev:
            return "0" * self._length
        alphabet = string.digits
        if not self._only_digits:
            alphabet += string.ascii_letters.upper()
        return "".join(secrets.choice(alphabet) for _ in range(self._length))

    async def send_otp(
        self,
        receiver: str,
        channel: OtpChannel,
        user_id: UUID | None,
        purpose: str,
    ) -> str:
        """Cache and deliver an OTP through the selected channel."""
        if not purpose.strip():
            raise ApiException(ErrorType.INVALID_REQUEST, "OTP purpose is required")
        if not isinstance(channel, OtpChannel):
            raise ApiException(ErrorType.INVALID_REQUEST, "OTP channel is invalid")

        delivery = self._deliveries.get(channel)
        if delivery is None and not self._is_dev:
            raise ApiException(
                ErrorType.NOT_IMPLEMENTED,
                f"OTP delivery through {channel.value} is not configured",
            )

        otp_token = uuid4().hex
        key = self._otp_cache_key(otp_token)
        otp = await self._generate_otp()
        record = {
            "otp": otp,
            "user_id": str(user_id) if user_id is not None else None,
            "purpose": purpose,
            "attempts": 0,
        }
        await self._cache_client.set(key, json.dumps(record), self._ttl)
        if self._is_dev:
            return otp_token
        assert delivery is not None, "A delivery adapter is required outside dev mode"

        subject = self._subject
        body = self._body_template.format(purpose=purpose, otp=otp)
        try:
            sent = await delivery.send(receiver, subject, body)
        except Exception:
            await self._cache_client.delete(key)
            raise
        if not sent:
            await self._cache_client.delete(key)
            raise ApiException(ErrorType.OTP_DELIVERY_FAILED)
        return otp_token

    async def check_otp(
        self,
        otp: str,
        otp_token: str,
        user_id: UUID | None,
        purpose: str,
    ) -> str:
        """Validate an OTP and issue a purpose-bound confirmation token."""
        key = self._otp_cache_key(otp_token)
        raw_record = await self._cache_client.get(key)
        if not raw_record:
            raise ApiException(ErrorType.INVALID_REQUEST, "OTP is missing or expired")
        record = json.loads(raw_record)
        if (
            record["user_id"] != (str(user_id) if user_id is not None else None)
            or record["purpose"] != purpose
        ):
            raise ApiException(ErrorType.INVALID_REQUEST, "OTP context does not match")

        if not secrets.compare_digest(str(record["otp"]), otp):
            record["attempts"] += 1
            if record["attempts"] >= self._max_retry:
                await self._cache_client.delete(key)
            else:
                await self._cache_client.set(key, json.dumps(record), self._ttl)
            raise ApiException(ErrorType.INVALID_REQUEST, "OTP is invalid")

        await self._cache_client.delete(key)
        confirm_token = uuid4().hex
        confirmation = {
            "user_id": record["user_id"],
            "purpose": purpose,
            "remaining_uses": self._confirm_usage,
        }
        await self._cache_client.set(
            self._confirmation_cache_key(confirm_token),
            json.dumps(confirmation),
            self._confirm_ttl,
        )
        return confirm_token

    async def consume_confirmation_token(
        self, token: str, user_id: UUID | None, purpose: str
    ) -> bool:
        """Validate and consume one use of a confirmation token."""
        key = self._confirmation_cache_key(token)
        raw_confirmation = await self._cache_client.get(key)
        if not raw_confirmation:
            raise ApiException(
                ErrorType.INVALID_REQUEST, "Confirmation token is missing or expired"
            )
        confirmation = json.loads(raw_confirmation)
        expected_user_id = str(user_id) if user_id is not None else None
        if (
            confirmation["user_id"] != expected_user_id
            or confirmation["purpose"] != purpose
        ):
            raise ApiException(
                ErrorType.INVALID_REQUEST, "Confirmation token context does not match"
            )
        remaining_uses = int(confirmation["remaining_uses"]) - 1
        if remaining_uses <= 0:
            await self._cache_client.delete(key)
        else:
            confirmation["remaining_uses"] = remaining_uses
            await self._cache_client.set(
                key, json.dumps(confirmation), self._confirm_ttl
            )
        return True

    @staticmethod
    def _otp_cache_key(otp_token: str) -> str:
        return f"otp:{otp_token}"

    @staticmethod
    def _confirmation_cache_key(token: str) -> str:
        return f"otp:confirm:{token}"
