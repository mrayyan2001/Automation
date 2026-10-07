"""FastAPI integration for application-context component injection."""

from collections.abc import Callable
from typing import Any

from fastapi import Request


def get_bean(bean_type: type) -> Callable[[Request], Any]:
    """Return a FastAPI dependency that resolves ``bean_type`` from the app."""

    async def dependency(request: Request) -> Any:
        context_task = getattr(request.app.state, "context_task", None)
        if context_task is not None:
            await context_task

        try:
            context = request.app.state.context
        except AttributeError as exc:
            raise RuntimeError(
                "Application context has not been initialized on app.state.context"
            ) from exc

        return context.get(bean_type)

    return dependency
