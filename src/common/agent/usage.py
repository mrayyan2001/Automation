from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class UsageTracker:
    calls: list[dict] = field(default_factory=list)
    steps: dict[str, dict] = field(default_factory=dict)
    started_at: float = field(default_factory=perf_counter)
    on_update: Callable[[dict], None] | None = None

    def add_call(
        self,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        elapsed_ms: float,
        step: str,
        agent_name: str = "Builder",
        request: str = "",
        response: object = None,
    ) -> None:
        total_tokens = input_tokens + output_tokens
        self.calls.append(
            {
                "step": step,
                "agent_name": agent_name,
                "operation": operation,
                "request": request,
                "response": response,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "elapsed_ms": round(elapsed_ms, 2),
            }
        )
        summary = self.steps.setdefault(
            step,
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        summary["input_tokens"] += input_tokens
        summary["output_tokens"] += output_tokens
        summary["total_tokens"] += total_tokens
        self._notify()

    def add_step_time(self, step: str, elapsed_ms: float) -> None:
        summary = self.steps.setdefault(
            step,
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        summary["elapsed_ms"] = round(summary.get("elapsed_ms", 0.0) + elapsed_ms, 2)
        self._notify()

    def _notify(self) -> None:
        if self.on_update is not None:
            self.on_update(self.snapshot())

    def snapshot(self) -> dict:
        input_tokens = sum(call["input_tokens"] for call in self.calls)
        output_tokens = sum(call["output_tokens"] for call in self.calls)
        return {
            "calls": [dict(call) for call in self.calls],
            "steps": {name: dict(step) for name, step in self.steps.items()},
            "total": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "elapsed_ms": round((perf_counter() - self.started_at) * 1000, 2),
            },
        }


_tracker: ContextVar[UsageTracker | None] = ContextVar(
    "builder_usage_tracker", default=None
)
_step: ContextVar[str] = ContextVar("builder_usage_step", default="workflow")


@contextmanager
def usage_context(
    on_update: Callable[[dict], None] | None = None,
) -> Iterator[UsageTracker]:
    tracker = UsageTracker(on_update=on_update)
    token = _tracker.set(tracker)
    try:
        yield tracker
    finally:
        _tracker.reset(token)


@contextmanager
def usage_step(name: str) -> Iterator[None]:
    started_at = perf_counter()
    token = _step.set(name)
    try:
        yield
    finally:
        tracker = _tracker.get()
        if tracker is not None:
            tracker.add_step_time(name, (perf_counter() - started_at) * 1000)
        _step.reset(token)


def record_agent_usage(
    operation: str,
    input_tokens: int,
    output_tokens: int,
    elapsed_ms: float,
    agent_name: str = "Builder",
    request: str = "",
    response: object = None,
) -> None:
    tracker = _tracker.get()
    if tracker is not None:
        tracker.add_call(
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_ms=elapsed_ms,
            step=_step.get(),
            agent_name=agent_name,
            request=request,
            response=response,
        )
