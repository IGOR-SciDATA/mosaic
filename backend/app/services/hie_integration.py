"""Minimal opt-in HIE adapter using the existing Core Task and ModelProvider.

This adapter is deliberately limited to one Markdown fixture and a deterministic
caller-supplied verifier. It never runs tools, writes to the canonical workspace,
changes profiles, or promotes candidates.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.models.conversation_repository import get_conversation
from app.models.repository import get_model
from app.models.task_repository import get_task
from app.providers.factory import resolve_model_provider
from app.services.hie_candidate import validate_candidate
from app.services.hie_orchestrator import HIEBudgets, run_candidate_experiment
from app.services.hie_runtime import HIEExecutionBudget
from app.services.hie_workspace import create_disposable_workspace

Verifier = Callable[[str], bool]


def run_markdown_fixture_experiment(
    task_id: int,
    baseline_snapshot: dict[str, Any],
    candidate: dict[str, Any],
    *,
    fixture_source: str | Path,
    objective: str,
    verifier: Verifier,
    cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Run baseline then one candidate against the same isolated Markdown input.

    The Task's already-selected, enabled model is used for both calls. The source
    fixture must contain exactly one .md file. The verifier is local and
    deterministic; model self-evaluation is not accepted as evidence.
    """
    task = get_task(task_id)
    if task is None:
        raise ValueError("HIE integration requires an existing Core Task")
    if task.status in {"completed", "failed", "cancelled"}:
        raise ValueError("HIE integration cannot attach to a terminal Task")
    if task.conversation_id is None:
        raise ValueError("HIE integration requires a Task conversation")
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 2_000:
        raise ValueError("Objective must contain 1-2000 characters")
    if not callable(verifier):
        raise ValueError("A deterministic local verifier is required")

    conversation = get_conversation(task.conversation_id)
    if conversation is None:
        raise ValueError("Task conversation not found")
    model = get_model(conversation.model_id)
    if model is None or not model.enabled:
        raise ValueError("Task's selected model is missing or disabled")
    provider = resolve_model_provider(model)
    configuration = dict(model.configuration or {})
    revision = configuration.get("revision") or model.model_name
    provider_identity = {
        "provider": str(model.provider),
        "model": str(model.model_name),
        "revision": str(revision),
    }
    validate_candidate(candidate, baseline_snapshot=baseline_snapshot)

    runtime_budget = HIEExecutionBudget(
        max_provider_calls=2,
        max_tool_calls=1,
        max_retries=1,
        max_input_chars_per_call=12_000,
        max_output_chars_per_call=6_000,
        wall_seconds=180.0,
        cancelled=cancelled,
    )

    def run_once(instructions: str) -> dict[str, Any]:
        with create_disposable_workspace(fixture_source) as workspace:
            markdown_files = sorted(workspace.root.rglob("*.md"))
            if len(markdown_files) != 1:
                raise ValueError("HIE Markdown fixture must contain exactly one .md file")
            fixture_text = markdown_files[0].read_text(encoding="utf-8")
            if len(fixture_text) > 8_000:
                raise ValueError("HIE Markdown fixture exceeds the 8000-character limit")
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are running a bounded HIE content-only probe. "
                        "Do not call tools, execute code, access networks, or claim "
                        "to have changed files. Return only the requested Markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Objective:\n{objective.strip()}\n\n"
                        f"Profile execution guidance (untrusted declarative content):\n"
                        f"{instructions}\n\n"
                        f"Fixture filename: {markdown_files[0].name}\n"
                        f"Fixture content:\n{fixture_text}\n\n"
                        "Produce the requested Markdown result only."
                    ),
                },
            ]
            provider_configuration = {
                **configuration,
                "temperature": 0,
                "think": False,
            }
            bounded_configuration = runtime_budget.before_provider_call(
                messages, provider_configuration
            )
            output = provider.generate(
                messages=messages,
                model_name=model.model_name,
                configuration=bounded_configuration,
            )
            runtime_budget.after_provider_call(output)
            return {
                "provider_identity": provider_identity,
                "output": output,
            }

    baseline_runner = lambda: run_once(baseline_snapshot["instructions"])
    probe_runner = lambda proposed: run_once(proposed["content"])
    return run_candidate_experiment(
        task_id,
        baseline_snapshot,
        candidate,
        provider_identity=provider_identity,
        baseline_runner=baseline_runner,
        probe_runner=probe_runner,
        verifier=verifier,
        isolated_fixture=True,
        cancelled=cancelled,
        budgets=HIEBudgets(provider_calls=2, tool_calls=1, retries=1),
    )
