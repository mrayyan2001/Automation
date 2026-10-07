import json
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel

from common.agent.usage import record_agent_usage

logger = logging.getLogger(__name__)
DEFAULT_MAX_OUTPUT_TOKENS = 4096


def _extract_batch_items(batch_output: Any) -> list[Any]:
    """Extract the collection from any structured batch output model."""
    if isinstance(batch_output, list):
        return batch_output

    model_fields = getattr(type(batch_output), "model_fields", None)
    field_names = (
        model_fields
        if model_fields is not None
        else getattr(batch_output, "__dict__", {})
    )
    for field_name in field_names:
        value = getattr(batch_output, field_name, None)
        if model_fields is None:
            value = field_names[field_name]
        if isinstance(value, list):
            return value

    return []


async def _run_agent(
    agent: Agent,
    task: str,
    operation: str,
    agent_role: str = "Builder",
    agent_name: str | None = None,
) -> Any:
    """Run an agent and log token usage and response time for the call."""
    started_at = time.perf_counter()
    logger.info(
        "%s (%s) agent request: operation=%s",
        agent_name or agent_role,
        agent_role,
        operation,
    )
    try:
        result = await agent.run(task)
    except Exception:
        response_time_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "%s (%s) agent call failed: operation=%s response_time_ms=%.2f\n"
            "request:\n```text\n%s\n```",
            agent_name or agent_role,
            agent_role,
            operation,
            response_time_ms,
            task,
        )
        raise

    usage = result.usage
    response_time_ms = (time.perf_counter() - started_at) * 1000

    output_data = (
        result.output.model_dump()
        if hasattr(result.output, "model_dump")
        else result.output
    )
    logger.info(
        "%s (%s) agent call completed: operation=%s input_tokens=%d "
        "output_tokens=%d response_time_ms=%.2f\n"
        "request:\n```text\n%s\n```\n"
        "response:\n```json\n%s\n```",
        agent_name or agent_role,
        agent_role,
        operation,
        usage.input_tokens,
        usage.output_tokens,
        response_time_ms,
        task,
        json.dumps(output_data),
    )
    record_agent_usage(
        operation=operation,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        elapsed_ms=response_time_ms,
        agent_name=agent_name or agent_role,
        request=task,
        response=output_data,
    )
    return result


class AgentBuilder[OutputT]:
    """Shared agent-backed builder implementation."""

    def __init__(
        self,
        model: OpenAIChatModel,
        output_type: type[OutputT],
        system_prompt: str,
        batch_size: int = 1,
        batch_output_type: type[Any] | None = None,
        batch_system_prompt: str | None = None,
        example_provider: Callable[[str], str] | None = None,
        agent_role: str = "Builder",
        agent_name: str | None = None,
    ) -> None:
        self.agent = Agent(
            model=model,
            output_type=output_type,
            system_prompt=system_prompt,
            model_settings={"max_tokens": DEFAULT_MAX_OUTPUT_TOKENS},
        )
        self.batch_size = max(1, int(batch_size))
        self.agent_role = agent_role
        self.agent_name = agent_name or agent_role
        self.example_provider = example_provider
        self.batch_agent = (
            Agent(
                model=model,
                output_type=batch_output_type,
                system_prompt=batch_system_prompt,
                model_settings={"max_tokens": DEFAULT_MAX_OUTPUT_TOKENS},
            )
            if batch_output_type and batch_system_prompt
            else None
        )

    @property
    def operation_name(self) -> str:
        return "plan" if self.agent_role == "Planner" else "build"

    @property
    def batch_operation_name(self) -> str:
        return "plan_batch" if self.agent_role == "Planner" else "build_batch"

    async def build(self, task: str) -> OutputT:
        result = await _run_agent(
            self.agent,
            self._add_examples(task),
            operation=self.operation_name,
            agent_role=self.agent_role,
            agent_name=self.agent_name,
        )
        return result.output

    async def run(self, user_prompt: str) -> OutputT:
        result = await _run_agent(
            self.agent,
            self._add_examples(user_prompt),
            operation=self.operation_name,
            agent_role=self.agent_role,
            agent_name=self.agent_name,
        )
        return result

    def _add_examples(self, task: str) -> str:
        if not self.example_provider:
            return task
        examples = self.example_provider(task)
        return f"{task}\n\nRelevant examples:\n{examples}" if examples else task

    async def build_batch(
        self, items: list[tuple[Any, Any | None]]
    ) -> list[tuple[Any, OutputT]]:
        """Build a batch of items in a single request."""
        if not items:
            return []

        if len(items) == 1 or not self.batch_agent:
            res: list[tuple[Any, OutputT]] = []
            for task_data, existing_item in items:
                prompt = task_data.task
                if existing_item is not None:
                    prompt = (
                        f"Existing schema to update:\n"
                        f"{existing_item.model_dump_json(indent=2)}\n\n"
                        f"Update instruction:\n{task_data.task}"
                    )
                output = await self.build(prompt)
                res.append((task_data, output))
            return res

        instructions: list[str] = []
        for idx, (task_data, existing_item) in enumerate(items, start=1):
            name = getattr(task_data, "name", f"item_{idx}")
            item_desc = [f"Item {idx}:", f"Name: {name}"]
            if existing_item is not None:
                item_desc.append(
                    f"Existing schema to update:\n{existing_item.model_dump_json(indent=2)}"
                )
            item_desc.append(f"Instruction:\n{task_data.task}")
            instructions.append("\n".join(item_desc))

        batch_prompt = (
            f"Please generate {len(items)} items corresponding to each item below:\n\n"
            + "\n\n---\n\n".join(instructions)
        )

        result = await _run_agent(
            self.batch_agent,
            self._add_examples(batch_prompt),
            operation=self.batch_operation_name,
            agent_role=self.agent_role,
            agent_name=self.agent_name,
        )
        batch_output = result.output

        output_items: list[OutputT] = _extract_batch_items(batch_output)

        # Map back to tasks by name if possible, otherwise by index
        items_by_name: dict[str, OutputT] = {
            getattr(b, "name", ""): b for b in output_items if hasattr(b, "name")
        }
        res = []
        for idx, (task_data, _) in enumerate(items):
            task_name = getattr(task_data, "name", None)
            if task_name and task_name in items_by_name:
                res.append((task_data, items_by_name[task_name]))
            elif idx < len(output_items):
                res.append((task_data, output_items[idx]))
            else:
                single_output = await self.build(task_data.task)
                res.append((task_data, single_output))

        return res
