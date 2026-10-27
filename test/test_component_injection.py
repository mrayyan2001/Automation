"""Verify interface, collection, default and named dependency resolution."""

import unittest
from abc import ABC, abstractmethod
from typing import Annotated

import httpx
from fastapi import FastAPI

from common.annotation.primary import Primary
from common.annotation.qualifier import Qualifier
from common.annotation.router import Controller, Get
from common.annotation.service import Service
from context import ApplicationContext


class Greeting(ABC):
    @abstractmethod
    def greet(self) -> str: ...


@Service
@Primary
@Qualifier("english")
class English(Greeting):
    def greet(self):
        return "hello"


@Service
@Qualifier("spanish")
class Spanish(Greeting):
    def greet(self):
        return "hola"


@Controller("/injection")
class GreetingRouter:
    def __init__(self, greeting: Annotated[Greeting, Qualifier("spanish")]):
        self.greeting = greeting

    @Get("/")
    def greetings(
        self,
        default: Greeting,
        all_services: list[Greeting],
        named: Annotated[Greeting, Qualifier("spanish")],
    ) -> dict:
        return {
            "default": default.greet(),
            "all": [item.greet() for item in all_services],
            "named": named.greet(),
            "constructor": self.greeting.greet(),
        }


class InjectionTests(unittest.IsolatedAsyncioTestCase):
    def context(self):
        context = ApplicationContext()
        context.component_types.update([English, Spanish, GreetingRouter])
        return context

    async def test_route_and_constructor_injection(self):
        app = FastAPI()
        app.state.context = self.context()
        app.include_router(GreetingRouter.__router__)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/injection/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"],
            {
                "default": "hello",
                "all": ["hello", "hola"],
                "named": "hola",
                "constructor": "hola",
            },
        )

    def test_ambiguity_missing_and_singleton(self):
        context = self.context()
        self.assertIs(context.get(Greeting), context.get(English))
        with self.assertRaisesRegex(LookupError, "No component"):
            context.get(Annotated[Greeting, Qualifier("missing")])

        @Service
        class Alternative(Greeting):
            def greet(self):
                return "hey"

        context = ApplicationContext()
        context.component_types = {Spanish, Alternative}
        with self.assertRaisesRegex(LookupError, "Ambiguous"):
            context.get(Greeting)
        context.component_types = {Spanish}
        self.assertIsInstance(context.get(Greeting), Spanish)
        empty = ApplicationContext()
        self.assertEqual(empty.get(list[Greeting]), [])
        with self.assertRaisesRegex(LookupError, "No component"):
            empty.get(Greeting)

    def test_multiple_primary_is_ambiguous(self):
        @Primary
        @Service
        class OtherPrimary(Greeting):
            def greet(self):
                return "hey"

        context = self.context()
        context.component_types.add(OtherPrimary)
        with self.assertRaisesRegex(LookupError, "Ambiguous"):
            context.get(Greeting)


class StartupValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ambiguous_route_fails_during_initialization(self):
        from unittest.mock import patch

        from lifespan import initialize_context

        @Service
        class Alternative(Greeting):
            def greet(self):
                return "hey"

        context = ApplicationContext()
        context.component_types.update([Spanish, Alternative, GreetingRouter])
        app = FastAPI()
        with (
            patch("lifespan.scan_routers", return_value=[GreetingRouter.__router__]),
            patch("lifespan.create_application_context", return_value=context),
        ):
            with self.assertRaisesRegex(RuntimeError, "route /injection/.*Ambiguous"):
                await initialize_context(app)
        self.assertFalse(hasattr(app.state, "context"))
        self.assertNotIn("/injection/", app.openapi()["paths"])

    async def test_valid_dependencies_are_resolved_before_requests(self):
        from unittest.mock import patch

        from lifespan import initialize_context

        context = ApplicationContext()
        context.component_types.update([English, Spanish, GreetingRouter])
        app = FastAPI()
        with (
            patch("lifespan.scan_routers", return_value=[GreetingRouter.__router__]),
            patch("lifespan.create_application_context", return_value=context),
        ):
            await initialize_context(app)
        self.assertIs(app.state.context, context)
        self.assertEqual(set(context.beans), {English, Spanish, GreetingRouter})
        self.assertIn("/injection/", app.openapi()["paths"])
