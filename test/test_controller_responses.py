"""Exercise response envelopes through FastAPI's request pipeline."""

import unittest

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
import httpx

from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import PlainTextResponse

from common.annotation.router import Controller, Get
from common.exception.api_exception import ApiException, ErrorType
from common.exception.global_exception_handler import (
    exception_handler,
    http_exception_handler,
    validation_exception_handler,
)


class Item(BaseModel):
    value: int


@Controller("/test")
class TestController:
    @Get("/item")
    async def item(self, value: int) -> Item:
        return Item(value=value)

    @Get("/empty")
    def empty(self) -> None:
        return None

    @Get("/error")
    async def error(self) -> dict:
        raise ApiException(ErrorType.CONFLICT)

    @Get("/http-error")
    async def http_error(self) -> dict:
        raise HTTPException(401, "Token required", headers={"WWW-Authenticate": "Bearer"})

    @Get("/unknown")
    async def unknown(self) -> dict:
        raise RuntimeError("private diagnostic")

    @Get("/text")
    async def text(self) -> PlainTextResponse:
        return PlainTextResponse("hello")


class ControllerResponseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        app = FastAPI()
        app.add_exception_handler(Exception, exception_handler)
        app.add_exception_handler(StarletteHTTPException, http_exception_handler)
        app.add_exception_handler(RequestValidationError, validation_exception_handler)
        app.include_router(TestController.__router__)
        app.state.context = {TestController: TestController()}
        self.app = app
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_typed_success_and_schema(self):
        response = await self.client.get("/test/item?value=7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "data": {"value": 7}})
        schemas = self.app.openapi()["components"]["schemas"]
        self.assertIn("success", schemas["SuccessResponse_Item_"]["properties"])

    async def test_empty_and_explicit_response(self):
        self.assertEqual((await self.client.get("/test/empty")).json(), {"success": True, "data": None})
        self.assertEqual((await self.client.get("/test/text")).text, "hello")

    async def test_errors(self):
        for path, status, code in [
            ("/test/item?value=bad", 422, "VALIDATION_FAILED"),
            ("/test/error", 409, "CONFLICT"),
            ("/test/http-error", 401, "UNAUTHORIZED"),
            ("/missing", 404, "NOT_FOUND"),
            ("/test/unknown", 500, "UNKNOWN_ERROR"),
        ]:
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status_code, status)
                self.assertFalse(response.json()["success"])
                self.assertEqual(response.json()["errorData"]["errorCode"], code)
        self.assertEqual((await self.client.get("/test/http-error")).headers["WWW-Authenticate"], "Bearer")


if __name__ == "__main__":
    unittest.main()
