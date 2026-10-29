"""Per-experiment execution budgets for real Core provider/tool boundaries.

This opt-in helper owns no Task lifecycle or persistence. Callers provide it to
the existing agent decision and execution functions; without it, normal Harness
behavior is unchanged. Synchronous provider requests cannot be forcefully
interrupted, so the remaining wall budget is passed as the provider timeout.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable


class HIERuntimeLimitExceeded(RuntimeError):
    """An HIE operation was blocked before it could exceed its budget."""


class HIERuntimeCancelled(HIERuntimeLimitExceeded):
    """The experiment was cancelled at an execution boundary."""


@dataclass
class HIEExecutionBudget:
    max_provider_calls: int = 4
    max_tool_calls: int = 6
    max_retries: int = 1
    max_input_chars_per_call: int = 12_000
    max_output_chars_per_call: int = 6_000
    wall_seconds: float = 180.0
    cancelled: Callable[[], bool] | None = None
    started_at: float = field(default_factory=time.monotonic)
    provider_calls: int = 0
    tool_calls: int = 0
    retries: int = 0

    def _remaining(self) -> float:
        remaining = self.wall_seconds - (time.monotonic() - self.started_at)
        if remaining <= 0:
            raise HIERuntimeLimitExceeded("HIE wall-clock budget exhausted")
        if self.cancelled is not None and self.cancelled():
            raise HIERuntimeCancelled("HIE execution cancelled at a safe boundary")
        return remaining

    def before_provider_call(
        self,
        messages: list[dict[str, Any]],
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Reserve one real provider request and cap its network timeout."""
        remaining = self._remaining()
        input_chars = sum(
            len(content)
            for message in messages
            if isinstance(message, dict)
            for content in [message.get("content")]
            if isinstance(content, str)
        )
        if input_chars > self.max_input_chars_per_call:
            raise HIERuntimeLimitExceeded("HIE provider input exceeds the per-call character budget")
        if self.provider_calls >= self.max_provider_calls:
            raise HIERuntimeLimitExceeded("HIE provider-call budget exhausted")
        timeout = min(float(configuration.get("request_timeout_seconds", remaining)), remaining)
        if timeout < 1:
            raise HIERuntimeLimitExceeded("Insufficient wall-clock budget to start another provider request")
        self.provider_calls += 1
        return {**configuration, "request_timeout_seconds": timeout}

    def after_provider_call(self, output: str) -> None:
        """Reject oversized output and check cancellation/deadline after the call."""
        if len(output) > self.max_output_chars_per_call:
            raise HIERuntimeLimitExceeded("HIE provider output exceeds the per-call character budget")
        self._remaining()

    def check_tool_call(self) -> None:
        """Check whether a tool call may be proposed without consuming execution budget."""
        self._remaining()
        if self.tool_calls >= self.max_tool_calls:
            raise HIERuntimeLimitExceeded("HIE tool-call budget exhausted")

    def before_tool_call(self) -> None:
        """Reserve one real tool execution before the executor is invoked."""
        self.check_tool_call()
        self.tool_calls += 1

    def before_retry(self) -> None:
        """Count a retry only when the decision loop is about to retry."""
        self._remaining()
        if self.retries >= self.max_retries:
            raise HIERuntimeLimitExceeded("HIE retry budget exhausted")
        self.retries += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "provider_calls": self.provider_calls,
            "tool_calls": self.tool_calls,
            "retries": self.retries,
            "elapsed_ms": max(0, int((time.monotonic() - self.started_at) * 1000)),
        }
