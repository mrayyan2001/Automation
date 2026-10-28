import asyncio
from datetime import timedelta
from uuid import UUID

import pytest

from common.exception.api_exception import ApiException, ErrorType
from features.otp.domain.otp_channel import OtpChannel
from features.otp.service.default_otp_service import DefaultOtpService
from persistence.cache.cache_client import CacheClient


class FakeCacheClient(CacheClient):
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, timedelta] = {}

    async def set(self, key: str, value, ttl: timedelta) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    async def get(self, key: str) -> str:
        return self.values.get(key, "")

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def health_check(self) -> None:
        return None


class FakeEmailOtpDelivery:
    channel = OtpChannel.EMAIL

    def __init__(self) -> None:
        self.delivered_otp = ""
        self.delivery_calls = 0
        self.last_subject = ""
        self.last_body = ""

    async def send(self, receiver: str, subject: str, body: str) -> bool:
        self.delivery_calls += 1
        self.last_subject = subject
        self.last_body = body
        self.delivered_otp = body.rsplit(" ", maxsplit=1)[-1].rstrip(".")
        return True


class FakeAppConfig:
    def __init__(self, otp_settings: dict):
        self.config = {"OTP": otp_settings}


def make_service(
    only_digits: bool = True, is_dev: bool = False
) -> tuple[DefaultOtpService, FakeCacheClient, FakeEmailOtpDelivery]:
    cache = FakeCacheClient()
    delivery = FakeEmailOtpDelivery()
    service = DefaultOtpService(
        cache,
        FakeAppConfig(
            {
                "IS_DEV": is_dev,
                "TTL_SECONDS": 120,
                "MAX_RETRY": 3,
                "ONLY_DIGITS": only_digits,
                "LENGTH": 6,
                "SUBJECT": "Your verification code",
                "BODY": "Your verification code for {purpose} is {otp}.",
                "CONFIRM_TTL_SECONDS": 60,
                "CONFIRM_USAGE": 1,
            }
        ),
        [delivery],
    )
    return service, cache, delivery


def test_generates_configured_digit_only_otp() -> None:
    service, _, _ = make_service(only_digits=True)

    otp = asyncio.run(service._generate_otp())

    assert len(otp) == 6
    assert otp.isdigit()
    assert service._ttl == timedelta(seconds=120)
    assert service._max_retry == 3


def test_generates_configured_mixed_otp() -> None:
    service, _, _ = make_service(only_digits=False)

    otp = asyncio.run(service._generate_otp())

    assert len(otp) == 6
    assert all(character.isalnum() for character in otp)


def test_send_and_check_issues_single_use_confirmation_token() -> None:
    async def run_flow() -> None:
        cache = FakeCacheClient()
        delivery = FakeEmailOtpDelivery()
        service = DefaultOtpService(
            cache,
            FakeAppConfig(
                {
                    "IS_DEV": False,
                    "TTL_SECONDS": 120,
                    "MAX_RETRY": 3,
                    "ONLY_DIGITS": True,
                    "LENGTH": 6,
                    "SUBJECT": "Your verification code",
                    "BODY": "Your verification code for {purpose} is {otp}.",
                    "CONFIRM_TTL_SECONDS": 60,
                    "CONFIRM_USAGE": 1,
                }
            ),
            [delivery],
        )
        user_id = UUID("8df84d2a-4f7b-4e93-97a4-f70c3372a0e0")

        otp_token = await service.send_otp(
            "user@example.com", OtpChannel.EMAIL, user_id, "register"
        )
        assert len(otp_token) == 32
        assert "-" not in otp_token
        assert f"otp:{otp_token}" in cache.values
        assert delivery.last_subject == "Your verification code"
        assert "for register is " in delivery.last_body
        token = await service.check_otp(
            delivery.delivered_otp, otp_token, user_id, "register"
        )
        assert len(token) == 32
        assert "-" not in token
        confirmation_key = f"otp:confirm:{token}"
        assert confirmation_key in cache.values
        assert cache.ttls[confirmation_key] == timedelta(seconds=60)
        assert await service.consume_confirmation_token(token, user_id, "register")
        with pytest.raises(ApiException):
            await service.consume_confirmation_token(token, user_id, "register")

    asyncio.run(run_flow())


def test_wrong_otp_is_removed_at_retry_limit() -> None:
    async def run_flow() -> None:
        service, cache, _ = make_service()
        user_id = UUID("8df84d2a-4f7b-4e93-97a4-f70c3372a0e0")
        otp_token = await service.send_otp(
            "user@example.com", OtpChannel.EMAIL, user_id, "register"
        )

        for _ in range(3):
            with pytest.raises(ApiException):
                await service.check_otp("wrong", otp_token, user_id, "register")

        assert f"otp:{otp_token}" not in cache.values

    asyncio.run(run_flow())


def test_dev_mode_caches_zero_otp_without_delivery() -> None:
    async def run_flow() -> None:
        service, cache, delivery = make_service(only_digits=False, is_dev=True)
        otp_token = await service.send_otp(
            "user@example.com", OtpChannel.EMAIL, None, "register"
        )

        assert await service._generate_otp() == "000000"
        assert delivery.delivery_calls == 0
        assert f"otp:{otp_token}" in cache.values

    asyncio.run(run_flow())


def test_sms_channel_is_not_implemented_until_delivery_is_added() -> None:
    async def run_flow() -> None:
        service, cache, delivery = make_service()

        with pytest.raises(ApiException) as error:
            await service.send_otp("+15551234567", OtpChannel.SMS, None, "register")

        assert error.value.error_type is ErrorType.NOT_IMPLEMENTED
        assert not cache.values
        assert delivery.delivery_calls == 0

    asyncio.run(run_flow())
