"""Sequential, bounded HIE experiment orchestration.

This layer compares an existing baseline with one hash-sealed candidate. It does
not generate candidates, persist them, change Task lifecycle state, or promote
anything. Runner adapters must be deterministic/side-effect-free and operate on
a disposable fixture; no production workspace adapter is provided here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import time
from typing import Any, Callable

from app.models.task_event_repository import create_task_event
from app.services.hie_evidence import persist_output_evidence, persist_record_evidence
from app.models.task_repository import get_task
from app.services.hie_candidate import (
    CandidateValidationError,
    candidate_diff,
    canonical_json,
    validate_candidate,
)

MAX_PROVIDER_CALLS = 4
MAX_TOOL_CALLS = 6
MAX_RETRIES = 1
MAX_INPUT_CHARS = 12_000
MAX_OUTPUT_CHARS = 6_000
MAX_WALL_SECONDS = 180.0
MAX_ARTIFACT_BYTES = 1024 * 1024


class HIEExperimentError(RuntimeError):
    """Base exception for a safely aborted HIE experiment."""


class HIEExperimentCancelled(HIEExperimentError):
    """Raised when cancellation is requested between experiment stages."""


class HIEBudgetExceeded(HIEExperimentError):
    """Raised when an experiment would exceed a configured hard budget."""


@dataclass(frozen=True)
class HIEBudgets:
    provider_calls: int = MAX_PROVIDER_CALLS
    tool_calls: int = MAX_TOOL_CALLS
    retries: int = MAX_RETRIES
    input_chars_per_call: int = MAX_INPUT_CHARS
    output_chars_per_call: int = MAX_OUTPUT_CHARS
    wall_seconds: float = MAX_WALL_SECONDS
    artifact_bytes: int = MAX_ARTIFACT_BYTES

    def validate(self) -> None:
        expected_maxima = {
            "provider_calls": MAX_PROVIDER_CALLS,
            "tool_calls": MAX_TOOL_CALLS,
            "retries": MAX_RETRIES,
            "input_chars_per_call": MAX_INPUT_CHARS,
            "output_chars_per_call": MAX_OUTPUT_CHARS,
            "wall_seconds": MAX_WALL_SECONDS,
            "artifact_bytes": MAX_ARTIFACT_BYTES,
        }
        integer_budgets = {
            "provider_calls", "tool_calls", "retries",
            "input_chars_per_call", "output_chars_per_call", "artifact_bytes",
        }
        for name, ceiling in expected_maxima.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Invalid HIE budget: {name}")
            if name in integer_budgets and not isinstance(value, int):
                raise ValueError(f"HIE budget must be an integer: {name}")
            if value <= 0 or value > ceiling:
                raise ValueError(f"HIE budget exceeds allowed ceiling: {name}")


Runner = Callable[[], dict[str, Any]]
ProbeRunner = Callable[[dict[str, Any]], dict[str, Any]]
Verifier = Callable[[str], bool]
CancellationCheck = Callable[[], bool]


def _provider_identity(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"provider", "model", "revision"}:
        raise HIEExperimentError(
            "Provider identity must explicitly include provider, model, and revision"
        )
    if any(not isinstance(value[key], str) or not value[key].strip() for key in value):
        raise HIEExperimentError("Provider identity fields must be non-empty strings")
    return {key: value[key].strip() for key in ("provider", "model", "revision")}


def _runner_output(value: Any, expected_identity: dict[str, str], stage: str, budgets: HIEBudgets) -> str:
    if not isinstance(value, dict) or set(value) != {"provider_identity", "output"}:
        raise HIEExperimentError(f"{stage} runner returned an invalid result shape")
    observed = _provider_identity(value["provider_identity"])
    if observed != expected_identity:
        raise HIEExperimentError(f"{stage} provider/model identity mismatch; comparison aborted")
    output = value["output"]
    if not isinstance(output, str):
        raise HIEExperimentError(f"{stage} output must be text")
    if len(output) > budgets.output_chars_per_call:
        raise HIEBudgetExceeded(f"{stage} output exceeds the configured character budget")
    return output


def _emit(task: Any, event_name: str, message: str, *, status: str, metadata: dict[str, Any] | None = None, level: str = "info") -> None:
    create_task_event(
        task_id=task.id,
        conversation_id=task.conversation_id,
        project_id=task.project_id,
        component="hie",
        event_name=event_name,
        message=message,
        status=status,
        metadata=metadata or {},
        level=level,
    )


def _emit_terminal_best_effort(
    task: Any,
    event_name: str,
    message: str,
    *,
    status: str,
    metadata: dict[str, Any],
    level: str = "warning",
) -> None:
    """Try to record a terminal state without masking the original failure.

    This is intentionally best-effort only for terminal error/cancellation
    events. Failure to persist such an event must never make a runner failure
    look like a different exception. The initial started event remains fail-closed.
    """
    try:
        _emit(task, event_name, message, status=status, metadata=metadata, level=level)
    except Exception:
        pass


def run_candidate_experiment(
    task_id: int,
    baseline_snapshot: dict[str, Any],
    candidate: dict[str, Any],
    *,
    provider_identity: dict[str, str],
    baseline_runner: Runner,
    probe_runner: ProbeRunner,
    verifier: Verifier,
    isolated_fixture: bool = False,
    cancelled: CancellationCheck | None = None,
    budgets: HIEBudgets | None = None,
) -> dict[str, Any]:
    """Compare baseline and one candidate sequentially; never promote.

    baseline_runner and probe_runner must only touch a disposable test fixture
    and must not perform external side effects. verifier must be deterministic
    and local; this function intentionally has no production workspace adapter.
    """
    task = get_task(task_id)
    if task is None:
        raise HIEExperimentError("HIE experiment requires an existing Core Task")
    if task.status in {"completed", "failed", "cancelled"}:
        raise HIEExperimentError("HIE experiment cannot attach to a terminal Task")
    if isolated_fixture is not True:
        raise HIEExperimentError("HIE experiments require an explicitly isolated disposable fixture")

    active_budgets = budgets or HIEBudgets()
    active_budgets.validate()
    identity = _provider_identity(provider_identity)
    validate_candidate(candidate, baseline_snapshot=baseline_snapshot)
    if len(candidate["content"]) > active_budgets.input_chars_per_call:
        raise HIEBudgetExceeded("Candidate content exceeds the configured input character budget")
    diff = candidate_diff(baseline_snapshot, candidate)
    diff_sha256 = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    candidate_sha256 = candidate["sha256"]
    started = time.monotonic()
    provider_calls = 0
    tool_calls = 0
    retries = 0

    def check_cancelled() -> None:
        if time.monotonic() - started > active_budgets.wall_seconds:
            raise HIEBudgetExceeded("HIE experiment wall-clock budget exceeded")
        if cancelled is not None and cancelled():
            raise HIEExperimentCancelled("HIE experiment cancelled between stages")

    def call(stage: str, callback: Callable[[], dict[str, Any]]) -> str:
        nonlocal provider_calls
        check_cancelled()
        if provider_calls >= active_budgets.provider_calls:
            raise HIEBudgetExceeded("HIE provider-call budget exhausted")
        provider_calls += 1
        result = _runner_output(callback(), identity, stage, active_budgets)
        check_cancelled()
        return result

    _emit(task, "hie.experiment.started", "HIE candidate comparison started", status="running", metadata={
        "candidate_sha256": candidate_sha256,
        "diff_sha256": diff_sha256,
        "target_kind": candidate["target"]["kind"],
        "provider_identity": identity,
        "budgets": asdict(active_budgets),
        "isolated_fixture": True,
    })

    try:
        _emit(task, "hie.baseline.started", "Running baseline on disposable fixture", status="running")
        baseline_output = call("baseline", baseline_runner)
        baseline_passed = verifier(baseline_output)
        if not isinstance(baseline_passed, bool):
            raise HIEExperimentError("Verifier must return a boolean result")
        _emit(task, "hie.baseline.completed", "Baseline verification completed", status="completed", metadata={
            "output_sha256": hashlib.sha256(baseline_output.encode("utf-8")).hexdigest(),
            "passed": baseline_passed,
        })

        check_cancelled()
        _emit(task, "hie.probe.started", "Running one candidate probe on disposable fixture", status="running", metadata={
            "candidate_sha256": candidate_sha256,
        })
        candidate_output = call("candidate_probe", lambda: probe_runner(candidate))
        candidate_passed = verifier(candidate_output)
        if not isinstance(candidate_passed, bool):
            raise HIEExperimentError("Verifier must return a boolean result")
        _emit(task, "hie.probe.completed", "Candidate probe verification completed", status="completed", metadata={
            "output_sha256": hashlib.sha256(candidate_output.encode("utf-8")).hexdigest(),
            "passed": candidate_passed,
        })

        if baseline_passed == candidate_passed:
            outcome = "tie"
        elif candidate_passed:
            outcome = "candidate_passed_baseline_failed"
        else:
            outcome = "regression"

        record = {
            "schema_version": 1,
            "task_id": task.id,
            "baseline_profile": {
                "slug": baseline_snapshot["slug"],
                "version": baseline_snapshot["version"],
                "sha256": baseline_snapshot["sha256"],
            },
            "candidate_sha256": candidate_sha256,
            "diff_sha256": diff_sha256,
            "target_kind": candidate["target"]["kind"],
            "provider_identity": identity,
            "baseline_output_sha256": hashlib.sha256(baseline_output.encode("utf-8")).hexdigest(),
            "candidate_output_sha256": hashlib.sha256(candidate_output.encode("utf-8")).hexdigest(),
            "baseline_passed": baseline_passed,
            "candidate_passed": candidate_passed,
            "outcome": outcome,
            "promotion": "not_performed",
            "budgets": asdict(active_budgets),
            "usage": {
                "provider_calls": provider_calls,
                "tool_calls": tool_calls,
                "retries": retries,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            },
        }

        # Reserve a bounded portion for the sealed record and its Artifact metadata.
        # Output bytes and output Artifact metadata share the same aggregate budget.
        record_reserve = min(16 * 1024, max(1, active_budgets.artifact_bytes // 4))
        output_budget = active_budgets.artifact_bytes - record_reserve
        if output_budget <= 0:
            raise HIEBudgetExceeded("HIE artifact budget cannot fit both output evidence and experiment record")
        evidence = persist_output_evidence(
            task.id, baseline_output, candidate_output, max_bytes=output_budget,
        )
        record["evidence"] = evidence
        used_bytes = sum(int(ref.get("budget_bytes", ref["size_bytes"])) for ref in evidence.values())
        remaining_bytes = active_budgets.artifact_bytes - used_bytes
        if remaining_bytes <= 0:
            raise HIEBudgetExceeded("HIE output evidence leaves no budget for the experiment record")

        record["record_sha256"] = hashlib.sha256(
            canonical_json(record).encode("utf-8")
        ).hexdigest()
        record_size = len(canonical_json(record).encode("utf-8"))
        if record_size > remaining_bytes:
            raise HIEBudgetExceeded("HIE experiment record exceeds the remaining aggregate artifact budget")
        # The sealed record deliberately does not self-reference its Artifact;
        # Core Artifact lookup remains the source for the record Artifact ID.
        persist_record_evidence(task.id, record, max_bytes=remaining_bytes)
        _emit(task, "hie.experiment.completed", "HIE comparison completed without promotion", status="completed", metadata=record)
        return record
    except HIEExperimentCancelled as exc:
        _emit_terminal_best_effort(task, "hie.experiment.cancelled", str(exc), status="cancelled", metadata={
            "candidate_sha256": candidate_sha256,
            "provider_calls": provider_calls,
        })
        raise
    except Exception as exc:
        _emit_terminal_best_effort(task, "hie.experiment.aborted", "HIE comparison aborted; baseline remains authoritative", status="failed", metadata={
            "candidate_sha256": candidate_sha256,
            "error_type": type(exc).__name__,
            "provider_calls": provider_calls,
        })
        if isinstance(exc, (HIEExperimentError, CandidateValidationError, ValueError)):
            raise
        raise HIEExperimentError("HIE comparison aborted safely") from exc
