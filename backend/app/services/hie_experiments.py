"""Persisted HIE experiments with isolated, side-effect-free baseline/candidate probes."""
import json
import time
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection
from app.models.conversation_repository import get_conversation
from app.models.project_repository import get_project
from app.models.repository import get_model
from app.models.task_event_repository import create_task_event, _redact
from app.models.task_repository import create_task, get_task, update_task
from app.providers.factory import resolve_model_provider
from app.services.agent_library import get_project_agent
from app.services.hie_candidate import build_candidate, candidate_diff, validate_candidate

MAX_FIXTURES = 8
MAX_FIXTURE_PROMPT_CHARS = 2_000
MAX_ASSERTIONS = 10
MAX_OUTPUT_CHARS = 6_000
MAX_OUTPUT_TOKENS = 1_500
MAX_EXPERIMENT_DURATION_SECONDS = 300


class HieExperimentError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(experiment: dict[str, Any], event_name: str, message: str, status: str, metadata: dict[str, Any] | None = None) -> None:
    create_task_event(
        task_id=experiment["task_id"],
        conversation_id=experiment["conversation_id"],
        project_id=experiment["project_id"],
        component="hie",
        event_name=event_name,
        message=message,
        status=status,
        metadata={"experiment_id": experiment["id"], **(metadata or {})},
    )


def _insert_experiment_event(
    connection, experiment: dict[str, Any], event_name: str, message: str,
    status: str, metadata: dict[str, Any] | None = None,
) -> None:
    safe_metadata = _redact({"experiment_id": experiment["id"], **(metadata or {})})
    encoded = json.dumps(safe_metadata, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > 4000:
        encoded = json.dumps({"truncated": True, "preview": encoded[:3960]})
    connection.execute(
        """INSERT INTO task_events (
            task_id, conversation_id, project_id, tool_call_id, action_id,
            timestamp, level, component, event_name, message, duration_ms, status, metadata
        ) VALUES (?, ?, ?, NULL, NULL, ?, 'info', 'hie', ?, ?, NULL, ?, ?)""",
        (
            experiment["task_id"], experiment["conversation_id"], experiment["project_id"],
            _now(), event_name[:120], message[:500], status[:80], encoded,
        ),
    )


def _row_to_experiment(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "source_task_id": row["source_task_id"],
        "conversation_id": row["conversation_id"],
        "project_id": row["project_id"],
        "profile_slug": row["profile_slug"],
        "candidate_origin": row["candidate_origin"],
        "provider": row["provider"],
        "model_name": row["model_name"],
        "budget": json.loads(row["budget_json"]),
        "status": row["status"],
        "baseline_snapshot": json.loads(row["baseline_snapshot"]),
        "candidate": json.loads(row["candidate"]),
        "fixtures": json.loads(row["fixtures"]),
        "candidate_diff": row["candidate_diff"],
        "results": json.loads(row["results"]) if row["results"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_experiment(experiment_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM hie_experiments WHERE id = ?", (experiment_id,)).fetchone()
    return _row_to_experiment(row) if row else None


def list_experiments(*, task_id: int | None = None, conversation_id: int | None = None) -> list[dict[str, Any]]:
    if (task_id is None) == (conversation_id is None):
        raise HieExperimentError("Provide exactly one of task_id or conversation_id")
    with get_connection() as connection:
        if task_id is not None:
            rows = connection.execute(
                "SELECT * FROM hie_experiments WHERE task_id = ? OR source_task_id = ? ORDER BY id DESC",
                (task_id, task_id),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM hie_experiments WHERE conversation_id = ? ORDER BY id DESC",
                (conversation_id,),
            ).fetchall()
    return [_row_to_experiment(row) for row in rows]


def _hie_enabled(scope: str, scope_id: int) -> bool:
    column = "task_id" if scope == "task" else "conversation_id"
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT enabled FROM hie_sessions WHERE {column} = ?", (scope_id,)
        ).fetchone()
    return bool(row and row["enabled"])


def create_experiment(
    *,
    conversation_id: int | None,
    task_id: int | None,
    profile_slug: str,
    candidate_content: str,
    fixtures: list[dict[str, Any]],
) -> dict[str, Any]:
    if (conversation_id is None) == (task_id is None):
        raise HieExperimentError("Provide exactly one of conversation_id or task_id")
    if not isinstance(profile_slug, str) or not profile_slug:
        raise HieExperimentError("profile_slug is required")
    if not isinstance(candidate_content, str) or not candidate_content.strip():
        raise HieExperimentError("candidate_content must not be empty")
    if not isinstance(fixtures, list) or not 1 <= len(fixtures) <= MAX_FIXTURES:
        raise HieExperimentError(f"Provide 1 to {MAX_FIXTURES} fixtures")

    source_task = get_task(task_id) if task_id is not None else None
    if task_id is not None and source_task is None:
        raise HieExperimentError("Task not found")
    resolved_conversation_id = source_task.conversation_id if source_task else conversation_id
    if resolved_conversation_id is None:
        raise HieExperimentError("Task must be linked to a conversation")
    conversation = get_conversation(resolved_conversation_id)
    if conversation is None:
        raise HieExperimentError("Conversation not found")
    project_id = conversation.project_id if conversation.project_id is not None else (source_task.project_id if source_task else None)
    if project_id is None:
        raise HieExperimentError("HIE experiments require a project-scoped conversation and agent profile")
    hie_is_enabled = (
        _hie_enabled("task", task_id)
        if task_id is not None
        else _hie_enabled("conversation", resolved_conversation_id)
    )
    if not hie_is_enabled:
        raise HieExperimentError("HIE must be explicitly enabled for this scope before starting an experiment")

    project = get_project(project_id)
    if project is None:
        raise HieExperimentError("Project not found")
    model = get_model(conversation.model_id)
    if model is None or not model.enabled:
        raise HieExperimentError("The conversation model is missing or disabled")
    baseline = get_project_agent(project_id, profile_slug)
    if baseline is None:
        raise HieExperimentError("Agent profile not found in this project")
    candidate = build_candidate(baseline, candidate_content)
    diff = candidate_diff(baseline, candidate)

    normalized_fixtures = []
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            raise HieExperimentError(f"Fixture {index + 1} must be an object")
        prompt = fixture.get("prompt")
        expected_contains = fixture.get("expected_contains", [])
        expected_not_contains = fixture.get("expected_not_contains", [])
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_FIXTURE_PROMPT_CHARS:
            raise HieExperimentError(f"Fixture {index + 1} prompt must contain 1-{MAX_FIXTURE_PROMPT_CHARS} characters")
        if not isinstance(expected_contains, list) or not isinstance(expected_not_contains, list):
            raise HieExperimentError(f"Fixture {index + 1} assertions must be lists")
        if len(expected_contains) + len(expected_not_contains) > MAX_ASSERTIONS:
            raise HieExperimentError(f"Fixture {index + 1} has too many assertions")
        if not expected_contains and not expected_not_contains:
            raise HieExperimentError(f"Fixture {index + 1} needs at least one deterministic assertion")
        if any(not isinstance(item, str) or not item or len(item) > 300 for item in expected_contains + expected_not_contains):
            raise HieExperimentError(f"Fixture {index + 1} assertions must be non-empty strings up to 300 characters")
        normalized_fixtures.append({
            "id": f"fixture-{index + 1}",
            "prompt": prompt.strip(),
            "expected_contains": expected_contains,
            "expected_not_contains": expected_not_contains,
        })

    # Every experiment runs in its own Task so it cannot race or overwrite the source Task's lifecycle.
    experiment_task = create_task(
        type="analysis",
        mode="create",
        conversation_id=resolved_conversation_id,
        project_id=project_id,
        plan={"goal": f"HIE experiment for /{profile_slug}", "hie_experiment": True, "source_task_id": task_id},
    )
    now = _now()
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO hie_sessions (task_id, enabled, created_at, updated_at)
               VALUES (?, 1, ?, ?) ON CONFLICT(task_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at""",
            (experiment_task.id, now, now),
        )
        cursor = connection.execute(
            """INSERT INTO hie_experiments (
                task_id, source_task_id, conversation_id, project_id, profile_slug, provider, model_name, budget_json, status,
                baseline_snapshot, candidate, fixtures, candidate_diff, results, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, NULL, ?, ?)""",
            (
                experiment_task.id, task_id, resolved_conversation_id, project_id, profile_slug,
                model.provider, model.model_name,
                json.dumps({
                    "max_fixtures": MAX_FIXTURES,
                    "max_provider_calls": len(normalized_fixtures) * 2,
                    "max_output_chars_per_call": MAX_OUTPUT_CHARS,
                    "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
                    "max_duration_seconds": MAX_EXPERIMENT_DURATION_SECONDS,
                    "max_request_timeout_seconds": 90,
                    "max_candidate_chars": 12000,
                    "fixture_count": len(normalized_fixtures),
                    "estimated_provider_calls": len(normalized_fixtures) * 2,
                }),
                json.dumps(baseline, ensure_ascii=False),
                json.dumps(candidate, ensure_ascii=False),
                json.dumps(normalized_fixtures, ensure_ascii=False),
                diff, now, now,
            ),
        )
        connection.commit()
    experiment = get_experiment(cursor.lastrowid)
    _emit(experiment, "hie.experiment_created", "HIE experiment created with a hash-sealed declarative candidate.", "draft", {
        "profile_slug": profile_slug,
        "baseline_version": baseline["version"],
        "baseline_sha256": baseline["sha256"],
        "candidate_sha256": candidate["sha256"],
        "fixture_count": len(normalized_fixtures),
    })
    return experiment


def queue_experiment(experiment_id: int) -> dict[str, Any]:
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HieExperimentError("Experiment not found")
    if experiment["status"] != "draft":
        raise HieExperimentError(f"Experiment cannot run from status {experiment['status']}")
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        running = connection.execute(
            "SELECT id FROM hie_experiments WHERE status IN ('queued', 'running') LIMIT 1"
        ).fetchone()
        if running:
            raise HieExperimentError("Another HIE experiment is already queued or running")
        cursor = connection.execute(
            "UPDATE hie_experiments SET status = 'queued', updated_at = ? WHERE id = ? AND status = 'draft'",
            (_now(), experiment_id),
        )
        connection.commit()
        if cursor.rowcount != 1:
            raise HieExperimentError("Experiment state changed; refresh and try again")
    experiment = get_experiment(experiment_id)
    _emit(experiment, "hie.experiment_queued", "HIE experiment queued for isolated baseline/candidate probes.", "queued", {
        "candidate_sha256": experiment["candidate"]["sha256"],
        "fixture_count": len(experiment["fixtures"]),
    })
    return experiment


def _evaluate(output: str, fixture: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for expected in fixture["expected_contains"]:
        if expected.casefold() not in output.casefold():
            failures.append({"type": "contains", "expected": expected})
    for forbidden in fixture["expected_not_contains"]:
        if forbidden.casefold() in output.casefold():
            failures.append({"type": "not_contains", "unexpected": forbidden})
    return {"passed": not failures, "failures": failures, "output_chars": len(output)}


def _bounded_provider_configuration(model_configuration: dict[str, Any], provider_name: str) -> dict[str, Any]:
    """Return an HIE-local config that enforces provider-call ceilings where supported.

    The ModelProvider interface remains unchanged. The concrete providers already
    honor request_timeout_seconds and these output limits (Ollama num_predict,
    OpenAI/remote max_output_tokens). Unknown providers fail closed for HIE rather
    than silently making an unbounded request.
    """
    configuration = dict(model_configuration or {})
    current_timeout = configuration.get("request_timeout_seconds", 90)
    try:
        timeout_seconds = float(current_timeout)
    except (TypeError, ValueError) as exc:
        raise HieExperimentError("Model request_timeout_seconds must be numeric for HIE") from exc
    if timeout_seconds < 1:
        raise HieExperimentError("Model request_timeout_seconds must be at least 1 second")
    configuration["request_timeout_seconds"] = min(timeout_seconds, 90)

    provider = (provider_name or "").strip().lower()
    if provider == "ollama":
        # Ollama uses num_predict in its request payload and request_timeout_seconds
        # for its network timeout.
        existing = configuration.get("num_predict", MAX_OUTPUT_TOKENS)
        try:
            existing = int(existing)
        except (TypeError, ValueError) as exc:
            raise HieExperimentError("Model num_predict must be a positive integer for HIE") from exc
        if existing < 1:
            raise HieExperimentError("Model num_predict must be a positive integer for HIE")
        configuration["num_predict"] = min(existing, MAX_OUTPUT_TOKENS)
    elif provider in {"openai", "remote_inference"}:
        existing = configuration.get("max_output_tokens", configuration.get("num_predict", MAX_OUTPUT_TOKENS))
        try:
            existing = int(existing)
        except (TypeError, ValueError) as exc:
            raise HieExperimentError("Model max_output_tokens must be a positive integer for HIE") from exc
        if existing < 1:
            raise HieExperimentError("Model max_output_tokens must be a positive integer for HIE")
        configuration["max_output_tokens"] = min(existing, MAX_OUTPUT_TOKENS)
    else:
        raise HieExperimentError("This provider does not have an HIE-enforceable call budget")
    return configuration


def _budget_for_experiment(experiment: dict[str, Any]) -> dict[str, Any]:
    budget = experiment.get("budget") or {}
    fixture_count = len(experiment["fixtures"])
    max_provider_calls = fixture_count * 2
    if (
        budget.get("max_provider_calls") != max_provider_calls
        or budget.get("fixture_count") != fixture_count
        or budget.get("estimated_provider_calls") != max_provider_calls
    ):
        raise HieExperimentError("Persisted HIE budget does not match the fixtures; recreate the experiment")
    return {
        **budget,
        "max_provider_calls": max_provider_calls,
        "max_output_chars_per_call": MAX_OUTPUT_CHARS,
        "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
        "max_request_timeout_seconds": 90,
        "max_duration_seconds": MAX_EXPERIMENT_DURATION_SECONDS,
        "max_candidate_chars": 12_000,
    }


def run_experiment(experiment_id: int) -> None:
    # Claim queued work with a conditional state transition. Another request or
    # recovery process may have changed status since the initial read.
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            "UPDATE hie_experiments SET status = 'running', updated_at = ? WHERE id = ? AND status = 'queued'",
            (_now(), experiment_id),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return
    experiment = get_experiment(experiment_id)
    if experiment is None:
        return
    task = get_task(experiment["task_id"])
    if task is not None and task.status == "pending":
        update_task(task.id, status="executing")
    _emit(experiment, "hie.experiment_started", "Running baseline and candidate against the same fixtures without tools or external actions.", "running", {
        "candidate_sha256": experiment["candidate"]["sha256"],
        "fixture_count": len(experiment["fixtures"]),
        "automatic_promotion": False,
    })
    total_started = time.monotonic()
    partial_evidence: list[dict[str, Any]] = []
    provider_calls = 0
    try:
        budget = _budget_for_experiment(experiment)
        baseline = experiment["baseline_snapshot"]
        candidate = experiment["candidate"]
        validate_candidate(candidate, baseline_snapshot=baseline)
        current = get_project_agent(experiment["project_id"], experiment["profile_slug"])
        if current is None or current["sha256"] != baseline["sha256"] or current["version"] != baseline["version"]:
            raise HieExperimentError("Active profile changed since baseline capture; create a new experiment")
        conversation = get_conversation(experiment["conversation_id"])
        model = get_model(conversation.model_id) if conversation else None
        if model is None or model.provider != experiment["provider"] or model.model_name != experiment["model_name"]:
            raise HieExperimentError("Conversation model changed after experiment creation; create a new experiment")
        provider = resolve_model_provider(model)
        provider_configuration = _bounded_provider_configuration(model.configuration, model.provider)
        baseline_content = baseline["instructions"]
        candidate_content = candidate["content"]
        active_skills = [skill for skill in baseline.get("skills", []) if skill.get("enabled") is True]
        fixed_skills_context = "\\n\\n".join(
            f"## {skill['name']} v{skill['version']}\\n{skill['content']}"
            for skill in active_skills
        ) or "(no enabled Skills in the baseline snapshot)"
        outputs = []
        for fixture in experiment["fixtures"]:
            case_result = {"fixture_id": fixture["id"]}
            for variant, instructions in (("baseline", baseline_content), ("candidate", candidate_content)):
                if provider_calls >= budget["max_provider_calls"]:
                    raise HieExperimentError("HIE provider-call budget exhausted before model invocation")
                if time.monotonic() - total_started >= budget["max_duration_seconds"]:
                    raise HieExperimentError("HIE experiment time budget exhausted before model invocation")
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are participating in an isolated HIE evaluation probe. Follow the supplied "
                            "declarative instructions as guidance only. Do not call tools, perform external "
                            "actions, claim to have changed system state, or reveal private reasoning. "
                            "Answer only the test prompt. This is an evaluation only; no active profile is changed.\\n\\n"
                            f"Profile: /{baseline['slug']} v{baseline['version']}\\n"
                            f"Instructions under test:\\n{instructions}\\n\\n"
                            f"Enabled Skills held constant across variants:\\n{fixed_skills_context}"
                        ),
                    },
                    {"role": "user", "content": fixture["prompt"]},
                ]
                # Budget guards run before the provider call; all shipped concrete
                # providers support the configuration keys capped above.
                provider_calls += 1
                started = time.monotonic()
                output = provider.generate(
                    messages=messages,
                    model_name=model.model_name,
                    configuration=provider_configuration,
                )
                duration_ms = max(0, int((time.monotonic() - started) * 1000))
                if not isinstance(output, str) or not output.strip():
                    raise HieExperimentError(f"{variant} returned an empty output for {fixture['id']}")
                # Bound persisted evidence even if a provider violates its output-token contract.
                output = output[:MAX_OUTPUT_CHARS]
                case_result[variant] = {
                    "output": output,
                    "evaluation": _evaluate(output, fixture),
                    "duration_ms": duration_ms,
                    "output_sha256": __import__("hashlib").sha256(output.encode("utf-8")).hexdigest(),
                }
            outputs.append(case_result)
            partial_evidence = outputs.copy()
            checkpoint = {
                "fixture_count": len(partial_evidence),
                "provider_calls": provider_calls,
                "execution_mode": "isolated_prompt_probe_no_tools",
                "assessment_scope": "submitted_deterministic_fixtures_only",
                "automatic_promotion": False,
                "partial": True,
                "evidence": partial_evidence,
            }
            # Evidence and its event are one durable unit: if event insertion fails,
            # the checkpoint is rolled back and the outer handler records failure.
            with get_connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    "UPDATE hie_experiments SET results = ?, updated_at = ? WHERE id = ? AND status = 'running'",
                    (json.dumps(checkpoint, ensure_ascii=False), _now(), experiment_id),
                )
                if cursor.rowcount != 1:
                    raise HieExperimentError("Experiment state changed before evidence checkpoint")
                _insert_experiment_event(
                    connection, experiment, "hie.fixture_evaluated",
                    f"Fixture {fixture['id']} completed for baseline and candidate.", "completed", {
                        "fixture_id": fixture["id"],
                        "baseline_passed": case_result["baseline"]["evaluation"]["passed"],
                        "candidate_passed": case_result["candidate"]["evaluation"]["passed"],
                        "baseline_output_sha256": case_result["baseline"]["output_sha256"],
                        "candidate_output_sha256": case_result["candidate"]["output_sha256"],
                        "provider_calls": provider_calls,
                    },
                )
                connection.commit()
        baseline_passes = sum(1 for item in outputs if item["baseline"]["evaluation"]["passed"])
        candidate_passes = sum(1 for item in outputs if item["candidate"]["evaluation"]["passed"])
        results = {
            "fixture_count": len(outputs),
            "provider_calls": provider_calls,
            "duration_ms": max(0, int((time.monotonic() - total_started) * 1000)),
            "execution_mode": "isolated_prompt_probe_no_tools",
            "baseline_passed": baseline_passes,
            "candidate_passed": candidate_passes,
            "baseline_pass_rate": baseline_passes / len(outputs),
            "candidate_pass_rate": candidate_passes / len(outputs),
            "delta_pass_rate": (candidate_passes - baseline_passes) / len(outputs),
            # This label summarizes only the user's deterministic fixture assertions.
            "assessment": (
                "candidate_better" if candidate_passes > baseline_passes
                else "candidate_regressed" if candidate_passes < baseline_passes
                else "inconclusive"
            ),
            "assessment_scope": "submitted_deterministic_fixtures_only",
            "automatic_promotion": False,
            "evidence": outputs,
        }
        with get_connection() as connection:
            connection.execute(
                "UPDATE hie_experiments SET status = 'completed', results = ?, updated_at = ? WHERE id = ? AND status = 'running'",
                (json.dumps(results, ensure_ascii=False), _now(), experiment_id),
            )
            connection.commit()
        experiment = get_experiment(experiment_id)
        task = get_task(experiment["task_id"])
        if task is not None and task.status == "executing":
            update_task(task.id, status="completed", result={"hie_experiment_id": experiment_id, "assessment": results["assessment"], "results": results})
        _emit(experiment, "hie.experiment_completed", "Baseline/candidate probes and deterministic fixture checks completed; no candidate was promoted.", "completed", {
            "assessment": results["assessment"],
            "assessment_scope": results["assessment_scope"],
            "baseline_pass_rate": results["baseline_pass_rate"],
            "candidate_pass_rate": results["candidate_pass_rate"],
            "candidate_sha256": candidate["sha256"],
            "automatic_promotion": False,
        })
    except Exception as exc:
        safe_error = f"{type(exc).__name__}: {str(exc)}"[:500]
        partial_results = {
            "error": safe_error,
            "error_type": type(exc).__name__,
            "fixture_count": len(partial_evidence),
            "provider_calls": provider_calls,
            "duration_ms": max(0, int((time.monotonic() - total_started) * 1000)),
            "execution_mode": "isolated_prompt_probe_no_tools",
            "assessment_scope": "submitted_deterministic_fixtures_only",
            "automatic_promotion": False,
            "recovery_requires_user": True,
            "evidence": partial_evidence,
        }
        with get_connection() as connection:
            connection.execute(
                "UPDATE hie_experiments SET status = 'failed', results = ?, updated_at = ? WHERE id = ? AND status IN ('running', 'queued')",
                (json.dumps(partial_results, ensure_ascii=False), _now(), experiment_id),
            )
            connection.commit()
        experiment = get_experiment(experiment_id)
        task = get_task(experiment["task_id"])
        if task is not None and task.status in {"pending", "executing"}:
            try:
                update_task(task.id, status="failed", result={"hie_experiment_id": experiment_id, "error": safe_error})
            except ValueError:
                pass
        _emit(experiment, "hie.experiment_failed", "HIE experiment failed; active profile was not modified and completed fixture evidence was preserved.", "failed", {
            "error_type": type(exc).__name__,
            "provider_calls": provider_calls,
            "completed_fixtures": len(partial_evidence),
            "candidate_sha256": experiment["candidate"]["sha256"],
            "automatic_promotion": False,
        })

def reject_experiment(experiment_id: int) -> dict[str, Any]:
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HieExperimentError("Experiment not found")
    if experiment["status"] not in {"draft", "completed", "failed"}:
        raise HieExperimentError(f"Experiment cannot be rejected from status {experiment['status']}")
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE hie_experiments SET status = 'rejected', updated_at = ? WHERE id = ? AND status = ?",
            (_now(), experiment_id, experiment["status"]),
        )
        connection.commit()
        if cursor.rowcount != 1:
            raise HieExperimentError("Experiment state changed; refresh and try again")
    experiment = get_experiment(experiment_id)
    _emit(experiment, "hie.experiment_rejected", "Candidate rejected by explicit user action; active profile was not modified.", "rejected", {
        "candidate_sha256": experiment["candidate"]["sha256"],
        "automatic_promotion": False,
    })
    return experiment
