"""Reusable base class for dependency-injected LangGraph workflows."""

from abc import ABC
from typing import TypeVar, cast

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseWorkflow[InputT, OutputT](ABC):
    """Base class providing a shared typed invocation method."""

    def __init__(self, workflow_entry) -> None:
        ainvoke = getattr(workflow_entry, "ainvoke", None)
        if not callable(ainvoke):
            raise TypeError(
                "workflow_entry must be a compiled workflow with a callable "
                "ainvoke(payload, ...) method. Use @entrypoint() when defining "
                "a LangGraph entrypoint."
            )
        self._workflow_entry = workflow_entry

    async def ainvoke(self, payload: InputT) -> OutputT:
        """Invoke the compiled LangGraph workflow asynchronously."""
        result = await self._workflow_entry.ainvoke(payload)
        return cast(OutputT, result)
