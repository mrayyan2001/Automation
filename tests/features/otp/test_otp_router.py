import asyncio
from uuid import UUID

import pytest
from pydantic import ValidationError

from common.exception.api_exception import ApiException, ErrorType
from features.otp.api.otp_requests import CheckOtpRequest, SendOtpRequest
from features.otp.api.otp_router import OtpRouter
from features.otp.domain.otp_channel import OtpChannel
from features.otp.service.otp_service import OtpService


class FakeOtpService(OtpService):
    def __init__(self) -> None:
        self.send_args: dict | None = None
        self.check_args: dict | None = None

    async def send_otp(
        self,
        receiver: str,
        channel: OtpChannel,
        user_id: UUID | None,
        purpose: str,
    ) -> str:
        self.send_args = {
            "receiver": receiver,
            "channel": channel,
            "user_id": user_id,
            "purpose": purpose,
        }
        return "otp-token"

    async def check_otp(
        self,
        otp: str,
        otp_token: str,
        user_id: UUID | None,
        purpose: str,
    ) -> str:
        self.check_args = {
            "otp": otp,
            "otp_token": otp_token,
            "user_id": user_id,
            "purpose": purpose,
        }
        return "confirmation-token"

    async def consume_confirmation_token(
        self, token: str, user_id: UUID | None, purpose: str
    ) -> bool:
        raise NotImplementedError


def test_otp_routes_use_versioned_api_paths() -> None:
    routes = {route.path: route.methods for route in OtpRouter.__router__.routes}

    assert routes == {
        "/api/v1/otp/send": {"POST"},
        "/api/v1/otp/check": {"POST"},
    }


def test_send_otp_passes_selected_channel_and_context() -> None:
    async def run_request() -> None:
        service = FakeOtpService()
        user_id = UUID("8df84d2a-4f7b-4e93-97a4-f70c3372a0e0")
        request = SendOtpRequest(
            receiver="user@example.com",
            channel=OtpChannel.EMAIL,
            user_id=user_id,
            purpose="register",
        )

        result = await OtpRouter().send_otp(request, service)

        assert result == "otp-token"
        assert service.send_args == {
            "receiver": "user@example.com",
            "channel": OtpChannel.EMAIL,
            "user_id": user_id,
            "purpose": "register",
        }

    asyncio.run(run_request())


def test_check_otp_returns_confirmation_token() -> None:
    async def run_request() -> None:
        service = FakeOtpService()
        request = CheckOtpRequest(
            otp="123456",
            otp_token="otp-token",
            user_id=None,
            purpose="register",
        )

        result = await OtpRouter().check_otp(request, service)

        assert result == "confirmation-token"
        assert service.check_args == {
            "otp": "123456",
            "otp_token": "otp-token",
            "user_id": None,
            "purpose": "register",
        }

    asyncio.run(run_request())


def test_send_otp_rejects_unknown_channel() -> None:
    with pytest.raises(ValidationError):
        SendOtpRequest.model_validate(
            {
                "receiver": "user@example.com",
                "channel": "voice",
                "purpose": "register",
            }
        )


def test_send_otp_propagates_unavailable_channel_error() -> None:
    class UnavailableChannelOtpService(FakeOtpService):
        async def send_otp(
            self,
            receiver: str,
            channel: OtpChannel,
            user_id: UUID | None,
            purpose: str,
        ) -> str:
            raise ApiException(ErrorType.NOT_IMPLEMENTED)

    async def run_request() -> None:
        request = SendOtpRequest(
            receiver="+15551234567",
            channel=OtpChannel.SMS,
            purpose="register",
        )
        with pytest.raises(ApiException) as error:
            await OtpRouter().send_otp(request, UnavailableChannelOtpService())

        assert error.value.error_type is ErrorType.NOT_IMPLEMENTED

    asyncio.run(run_request())
