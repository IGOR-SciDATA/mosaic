"""Persisted HIE experiments with isolated, side-effect-free baseline/candidate probes."""
import hashlib
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.database import get_connection
from app.models.conversation_repository import get_conversation
from app.models.project_repository import get_project
from app.models.repository import get_model
from app.models.task_event_repository import create_task_event
from app.models.task_repository import create_task, get_task, update_task
from app.providers.factory import resolve_model_provider
from app.services.agent_library import get_project_agent
from app.services.hie_candidate import build_candidate, candidate_diff, validate_candidate
from app.services.hie_fixture_adapter import run_disposable_fixture_experiment
from app.services.hie_orchestrator import HIEBudgets, MAX_ARTIFACT_BYTES
from app.services.hie_runtime import HIEExecutionBudget, HIERuntimeLimitExceeded

MAX_FIXTURES = 8
MAX_FIXTURE_PROMPT_CHARS = 2_000
MAX_ASSERTIONS = 10
MAX_OUTPUT_CHARS = 6_000
MAX_OUTPUT_TOKENS = 1_500
MAX_INPUT_CHARS_PER_CALL = 12_000
MAX_TOTAL_INPUT_CHARS = 192_000
MAX_OUTPUT_PREVIEW_CHARS = 1_000
PROVIDER_TIMEOUT_SECONDS = 90
MAX_PERSISTED_EVIDENCE_CHARS = MAX_FIXTURES * 2 * MAX_OUTPUT_CHARS + 20_000


class HieExperimentError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(experiment: dict[str, Any], event_name: str, message: str, status: str, metadata: dict[str, Any] | None = None, connection=None) -> None:
    create_task_event(
        task_id=experiment["task_id"],
        conversation_id=experiment["conversation_id"],
        project_id=experiment["project_id"],
        component="hie",
        event_name=event_name,
        message=message,
        status=status,
        metadata={"experiment_id": experiment["id"], **(metadata or {})},
        connection=connection,
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
    if model.provider.casefold() not in {"ollama", "remote_inference"}:
        raise HieExperimentError("The selected provider does not expose the output-token and request-timeout controls required by HIE")
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
    try:
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
                        "max_provider_calls": MAX_FIXTURES * 2,
                        "max_output_chars_per_call": MAX_OUTPUT_CHARS,
                        "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
                        "max_input_chars_per_call": MAX_INPUT_CHARS_PER_CALL,
                        "max_total_input_chars": MAX_TOTAL_INPUT_CHARS,
                        "provider_request_timeout_seconds": PROVIDER_TIMEOUT_SECONDS,
                        "max_wall_seconds": PROVIDER_TIMEOUT_SECONDS * 2,
                        "max_artifact_bytes": MAX_ARTIFACT_BYTES,
                        "max_persisted_evidence_chars": MAX_PERSISTED_EVIDENCE_CHARS,
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
            experiment = _row_to_experiment(
                connection.execute("SELECT * FROM hie_experiments WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )
            _emit(experiment, "hie.experiment_created", "HIE experiment created with a hash-sealed declarative candidate.", "draft", {
                "profile_slug": profile_slug,
                "baseline_version": baseline["version"],
                "baseline_sha256": baseline["sha256"],
                "candidate_sha256": candidate["sha256"],
                "fixture_count": len(normalized_fixtures),
            }, connection=connection)
            connection.commit()
    except Exception as exc:
        # The Task was created using the Core repository before this transaction.
        # Keep its lifecycle explicit if the experiment row/event cannot be persisted.
        try:
            update_task(
                experiment_task.id,
                status="failed",
                result={"hie_experiment_creation_failed": True, "error_type": type(exc).__name__},
            )
        except Exception:
            pass
        raise HieExperimentError("HIE experiment creation could not be persisted safely") from exc
    return experiment


def queue_experiment(experiment_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM hie_experiments WHERE id = ?", (experiment_id,)).fetchone()
        if row is None:
            raise HieExperimentError("Experiment not found")
        if row["status"] != "draft":
            raise HieExperimentError(f"Experiment cannot run from status {row['status']}")
        running = connection.execute(
            "SELECT id FROM hie_experiments WHERE status IN ('queued', 'running') LIMIT 1"
        ).fetchone()
        if running:
            raise HieExperimentError("Another HIE experiment is already queued or running")
        cursor = connection.execute(
            "UPDATE hie_experiments SET status = 'queued', updated_at = ? WHERE id = ? AND status = 'draft'",
            (_now(), experiment_id),
        )
        if cursor.rowcount != 1:
            raise HieExperimentError("Experiment state changed; refresh and try again")
        experiment = _row_to_experiment(
            connection.execute("SELECT * FROM hie_experiments WHERE id = ?", (experiment_id,)).fetchone()
        )
        _emit(experiment, "hie.experiment_queued", "HIE experiment queued for isolated baseline/candidate probes.", "queued", {
            "candidate_sha256": experiment["candidate"]["sha256"],
            "fixture_count": len(experiment["fixtures"]),
        }, connection=connection)
        connection.commit()
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


def run_experiment(experiment_id: int) -> None:
    experiment = get_experiment(experiment_id)
    if experiment is None or experiment["status"] != "queued":
        return
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE hie_experiments SET status = 'running', updated_at = ? WHERE id = ? AND status = 'queued'",
            (_now(), experiment_id),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return
    experiment = get_experiment(experiment_id)
    task = get_task(experiment["task_id"])
    if task is not None and task.status == "pending":
        update_task(task.id, status="executing")
    total_started = time.monotonic()
    try:
        _emit(experiment, "hie.experiment_started", "Running baseline and candidate against the same fixtures without tools or external actions.", "running", {
            "candidate_sha256": experiment["candidate"]["sha256"],
            "fixture_count": len(experiment["fixtures"]),
        })
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
        baseline_content = baseline["instructions"]
        candidate_content = candidate["content"]
        active_skills = [skill for skill in baseline.get("skills", []) if skill.get("enabled") is True]
        fixed_skills_context = "\n\n".join(
            f"## {skill['name']} v{skill['version']}\n{skill['content']}"
            for skill in active_skills
        ) or "(no enabled Skills in the baseline snapshot)"
        # Preflight every baseline/candidate input before the first provider call.
        # This prevents partial execution when a later fixture would exceed budget.
        total_input_chars = 0
        for fixture in experiment["fixtures"]:
            for instructions in (baseline_content, candidate_content):
                preflight_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are participating in an isolated HIE evaluation probe. Follow the supplied "
                            "declarative instructions as guidance only. Do not call tools, perform external "
                            "actions, claim to have changed system state, or reveal private reasoning. "
                            "Answer only the test prompt.\\n\\n"
                            f"Profile: /{baseline['slug']} v{baseline['version']}\\n"
                            f"Instructions under test:\\n{instructions}\\n\\n"
                            f"Enabled Skills held constant across variants:\\n{fixed_skills_context}"
                        ),
                    },
                    {"role": "user", "content": fixture["prompt"]},
                ]
                input_chars = sum(len(item["content"]) for item in preflight_messages)
                if input_chars > MAX_INPUT_CHARS_PER_CALL:
                    raise HieExperimentError(f"Input budget exceeded before provider call for {fixture['id']}")
                total_input_chars += input_chars
        if total_input_chars > MAX_TOTAL_INPUT_CHARS:
            raise HieExperimentError("Aggregate input budget exceeded before first provider call")
        outputs = []
        evidence_chars = 0
        provider_kind = model.provider.casefold()
        if provider_kind not in {"ollama", "remote_inference"}:
            raise HieExperimentError("HIE requires a provider with enforced output-token and request-timeout controls")
        revision = (model.configuration or {}).get("revision") or model.model_name
        provider_identity = {
            "provider": str(model.provider),
            "model": str(model.model_name),
            "revision": str(revision),
        }
        runtime_budget = HIEExecutionBudget(
            max_provider_calls=MAX_FIXTURES * 2,
            max_tool_calls=1,
            max_retries=1,
            max_input_chars_per_call=MAX_INPUT_CHARS_PER_CALL,
            max_output_chars_per_call=MAX_OUTPUT_CHARS,
            wall_seconds=PROVIDER_TIMEOUT_SECONDS * 2,
        )
        for fixture in experiment["fixtures"]:
            case_result = {"fixture_id": fixture["id"]}
            captured: dict[str, dict[str, Any]] = {}
            with tempfile.TemporaryDirectory(prefix="mosaic-hie-source-") as source_dir:
                fixture_source = Path(source_dir)
                (fixture_source / "fixture.md").write_text(fixture["prompt"], encoding="utf-8")

                def run_variant(variant: str, instructions: str, workspace_root: Path) -> dict[str, Any]:
                    nonlocal total_input_chars, evidence_chars
                    fixture_text = (workspace_root / "fixture.md").read_text(encoding="utf-8")
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are participating in an isolated HIE evaluation probe. Follow the supplied "
                                "declarative instructions as guidance only. Do not call tools, perform external "
                                "actions, claim to have changed system state, or reveal private reasoning. "
                                "Answer only the test prompt.\\n\\n"
                                f"Profile: /{baseline['slug']} v{baseline['version']}\\n"
                                f"Instructions under test:\\n{instructions}\\n\\n"
                                f"Enabled Skills held constant across variants:\\n{fixed_skills_context}"
                            ),
                        },
                        {"role": "user", "content": fixture_text},
                    ]
                    input_chars = sum(len(item["content"]) for item in messages)
                    if input_chars > MAX_INPUT_CHARS_PER_CALL:
                        raise HieExperimentError(f"Input budget exceeded before provider call for {fixture['id']}")
                    configuration = dict(model.configuration or {})
                    if provider_kind == "ollama":
                        configuration["num_predict"] = min(
                            MAX_OUTPUT_TOKENS,
                            int(configuration.get("num_predict", MAX_OUTPUT_TOKENS))
                            if int(configuration.get("num_predict", MAX_OUTPUT_TOKENS)) > 0
                            else MAX_OUTPUT_TOKENS,
                        )
                    else:
                        configuration["max_output_tokens"] = min(
                            MAX_OUTPUT_TOKENS,
                            int(configuration.get("max_output_tokens", MAX_OUTPUT_TOKENS))
                            if int(configuration.get("max_output_tokens", MAX_OUTPUT_TOKENS)) > 0
                            else MAX_OUTPUT_TOKENS,
                        )
                    configuration["request_timeout_seconds"] = min(
                        float(configuration.get("request_timeout_seconds", PROVIDER_TIMEOUT_SECONDS)),
                        PROVIDER_TIMEOUT_SECONDS,
                    )
                    bounded_configuration = runtime_budget.before_provider_call(messages, configuration)
                    started = time.monotonic()
                    output = provider.generate(
                        messages=messages,
                        model_name=model.model_name,
                        configuration=bounded_configuration,
                    )
                    duration_ms = max(0, int((time.monotonic() - started) * 1000))
                    runtime_budget.after_provider_call(output)
                    if not isinstance(output, str) or not output.strip():
                        raise HieExperimentError(f"{variant} returned an empty output for {fixture['id']}")
                    evidence_chars += len(output)
                    if evidence_chars > MAX_FIXTURES * 2 * MAX_OUTPUT_CHARS:
                        raise HieExperimentError("Aggregate output evidence budget exceeded")
                    captured[variant] = {"output": output, "duration_ms": duration_ms}
                    return {"provider_identity": provider_identity, "output": output}

                baseline_runner_factory = lambda root: (lambda: run_variant("baseline", baseline_content, root))
                probe_runner_factory = lambda root: (lambda proposed: run_variant("candidate", proposed["content"], root))
                try:
                    record = run_disposable_fixture_experiment(
                        fixture_source,
                        baseline_runner_factory=baseline_runner_factory,
                        probe_runner_factory=probe_runner_factory,
                        task_id=experiment["task_id"],
                        baseline_snapshot=baseline,
                        candidate=candidate,
                        provider_identity=provider_identity,
                        verifier=lambda output: _evaluate(output, fixture)["passed"],
                        budgets=HIEBudgets(
                            provider_calls=2,
                            tool_calls=1,
                            retries=1,
                            input_chars_per_call=MAX_INPUT_CHARS_PER_CALL,
                            output_chars_per_call=MAX_OUTPUT_CHARS,
                            wall_seconds=PROVIDER_TIMEOUT_SECONDS * 2,
                            artifact_bytes=MAX_ARTIFACT_BYTES // MAX_FIXTURES,
                        ),
                    )
                except (HIERuntimeLimitExceeded, ValueError) as exc:
                    raise HieExperimentError(str(exc)) from exc
            if set(captured) != {"baseline", "candidate"}:
                raise HieExperimentError(f"Fixture {fixture['id']} did not produce both persisted probe outputs")
            case_result["baseline"] = {
                "output_preview": captured["baseline"]["output"][:MAX_OUTPUT_PREVIEW_CHARS],
                "output_chars": len(captured["baseline"]["output"]),
                "evaluation": _evaluate(captured["baseline"]["output"], fixture),
                "duration_ms": captured["baseline"]["duration_ms"],
                "output_sha256": hashlib.sha256(captured["baseline"]["output"].encode("utf-8")).hexdigest(),
            }
            case_result["candidate"] = {
                "output_preview": captured["candidate"]["output"][:MAX_OUTPUT_PREVIEW_CHARS],
                "output_chars": len(captured["candidate"]["output"]),
                "evaluation": _evaluate(captured["candidate"]["output"], fixture),
                "duration_ms": captured["candidate"]["duration_ms"],
                "output_sha256": hashlib.sha256(captured["candidate"]["output"].encode("utf-8")).hexdigest(),
            }
            case_result["orchestrator_outcome"] = record["outcome"]
            case_result["experiment_record_sha256"] = record["record_sha256"]
            case_result["artifact_evidence"] = {
                role: {
                    key: value[key]
                    for key in ("artifact_id", "sha256", "size_bytes", "metadata_bytes", "budget_bytes")
                    if key in value
                }
                for role, value in record.get("evidence", {}).items()
            }
            outputs.append(case_result)
            _emit(experiment, "hie.fixture_evaluated", f"Fixture {fixture['id']} completed for baseline and candidate.", "completed", {
                "fixture_id": fixture["id"],
                "baseline_passed": case_result["baseline"]["evaluation"]["passed"],
                "candidate_passed": case_result["candidate"]["evaluation"]["passed"],
                "baseline_output_sha256": case_result["baseline"]["output_sha256"],
                "candidate_output_sha256": case_result["candidate"]["output_sha256"],
                "experiment_record_sha256": record["record_sha256"],
            })
        baseline_passes = sum(1 for item in outputs if item["baseline"]["evaluation"]["passed"])
        candidate_passes = sum(1 for item in outputs if item["candidate"]["evaluation"]["passed"])
        results = {
            "fixture_count": len(outputs),
            "provider_calls": runtime_budget.provider_calls,
            "total_input_chars": total_input_chars,
            "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
            "provider_request_timeout_seconds": PROVIDER_TIMEOUT_SECONDS,
            "max_wall_seconds": PROVIDER_TIMEOUT_SECONDS * 2,
            "evidence_chars": evidence_chars,
            "artifact_budget_bytes": MAX_ARTIFACT_BYTES,
            "evidence_storage": "Core Artifact repository; SQLite stores bounded previews and hashes",
            "duration_ms": max(0, int((time.monotonic() - total_started) * 1000)),
            "execution_mode": "isolated_prompt_probe_no_tools",
            "baseline_passed": baseline_passes,
            "candidate_passed": candidate_passes,
            "baseline_pass_rate": baseline_passes / len(outputs),
            "candidate_pass_rate": candidate_passes / len(outputs),
            "delta_pass_rate": (candidate_passes - baseline_passes) / len(outputs),
            "assessment": (
                "candidate_better" if candidate_passes > baseline_passes
                else "candidate_regressed" if candidate_passes < baseline_passes
                else "inconclusive"
            ),
            "automatic_promotion": False,
            "evidence": outputs,
        }
        encoded_results = json.dumps(results, ensure_ascii=False)
        if len(encoded_results) > MAX_PERSISTED_EVIDENCE_CHARS:
            raise HieExperimentError("Serialized result exceeds the persistence budget")
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE hie_experiments SET status = 'completed', results = ?, updated_at = ? WHERE id = ? AND status = 'running'",
                (encoded_results, _now(), experiment_id),
            )
            if cursor.rowcount != 1:
                raise HieExperimentError("Experiment state changed before result persistence")
            task_row = connection.execute(
                "SELECT id, conversation_id, project_id, status, plan, result FROM tasks WHERE id = ?",
                (experiment["task_id"],),
            ).fetchone()
            if task_row is None or task_row["status"] != "executing":
                raise HieExperimentError("Experiment Task state changed before result finalization")
            task_result = {"hie_experiment_id": experiment_id, "assessment": results["assessment"], "results": results}
            task_cursor = connection.execute(
                "UPDATE tasks SET status = 'completed', result = ?, updated_at = ? WHERE id = ? AND status = 'executing'",
                (json.dumps(task_result, ensure_ascii=False), _now(), experiment["task_id"]),
            )
            if task_cursor.rowcount != 1:
                raise HieExperimentError("Experiment Task changed concurrently before result finalization")
            create_task_event(
                task_id=experiment["task_id"], conversation_id=task_row["conversation_id"],
                project_id=task_row["project_id"], component="task", event_name="task.status_changed",
                message="Task status changed from executing to completed", status="completed",
                metadata={"previous_status": "executing", "status": "completed"}, connection=connection,
            )
            _emit(experiment, "hie.experiment_completed", "Baseline/candidate probes and deterministic fixture checks completed; no candidate was promoted.", "completed", {
                "assessment": results["assessment"],
                "baseline_pass_rate": results["baseline_pass_rate"],
                "candidate_pass_rate": results["candidate_pass_rate"],
                "candidate_sha256": candidate["sha256"],
                "automatic_promotion": False,
            }, connection=connection)
            connection.commit()
    except Exception as exc:
        safe_error = f"{type(exc).__name__}: {str(exc)}"[:500]
        with get_connection() as connection:
            connection.execute(
                "UPDATE hie_experiments SET status = 'failed', results = ?, updated_at = ? WHERE id = ? AND status = 'running'",
                (json.dumps({"error": safe_error, "automatic_promotion": False}), _now(), experiment_id),
            )
            connection.commit()
        experiment = get_experiment(experiment_id)
        task = get_task(experiment["task_id"])
        if task is not None and task.status in {"pending", "executing"}:
            try:
                if task.status == "pending":
                    update_task(task.id, status="failed", result={"hie_experiment_id": experiment_id, "error": safe_error})
                else:
                    update_task(task.id, status="failed", result={"hie_experiment_id": experiment_id, "error": safe_error})
            except ValueError:
                pass
        _emit(experiment, "hie.experiment_failed", "HIE experiment failed; active profile was not modified.", "failed", {
            "error_type": type(exc).__name__,
            "candidate_sha256": experiment["candidate"]["sha256"],
            "automatic_promotion": False,
        })


def reject_experiment(experiment_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM hie_experiments WHERE id = ?", (experiment_id,)).fetchone()
        if row is None:
            raise HieExperimentError("Experiment not found")
        if row["status"] not in {"draft", "completed", "failed"}:
            raise HieExperimentError(f"Experiment cannot be rejected from status {row['status']}")
        cursor = connection.execute(
            "UPDATE hie_experiments SET status = 'rejected', updated_at = ? WHERE id = ? AND status = ?",
            (_now(), experiment_id, row["status"]),
        )
        if cursor.rowcount != 1:
            raise HieExperimentError("Experiment state changed; refresh and try again")
        experiment = _row_to_experiment(
            connection.execute("SELECT * FROM hie_experiments WHERE id = ?", (experiment_id,)).fetchone()
        )
        _emit(experiment, "hie.experiment_rejected", "Candidate rejected by explicit user action; active profile was not modified.", "rejected", {
            "candidate_sha256": experiment["candidate"]["sha256"],
            "automatic_promotion": False,
        }, connection=connection)
        connection.commit()
    return experiment


def recover_interrupted_experiments() -> dict[str, list[int]]:
    """Recover interrupted HIE experiments atomically without replaying provider calls."""
    recovered_queued: list[int] = []
    recovered_running: list[int] = []
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute(
            "SELECT * FROM hie_experiments WHERE status IN ('queued', 'running') ORDER BY id"
        ).fetchall()
        for row in rows:
            experiment = _row_to_experiment(row)
            previous = experiment["status"]
            existing_results = experiment.get("results") or {}
            recovery = {
                **existing_results,
                "error_type": "InterruptedByRestart",
                "recovery_status": "interrupted_before_execution" if previous == "queued" else "result_unknown_after_restart",
                "previous_status": previous,
                "provider_outcome": "not_started" if previous == "queued" else "unknown",
                "automatic_retry": False,
                "requires_user_review": True,
                "automatic_promotion": False,
                "preserved_partial_evidence": bool(existing_results.get("evidence")),
            }
            cursor = connection.execute(
                "UPDATE hie_experiments SET status = 'failed', results = ?, updated_at = ? WHERE id = ? AND status = ?",
                (json.dumps(recovery, ensure_ascii=False), _now(), row["id"], previous),
            )
            if cursor.rowcount != 1:
                continue
            task_row = connection.execute(
                "SELECT id, conversation_id, project_id, status, result FROM tasks WHERE id = ?",
                (experiment["task_id"],),
            ).fetchone()
            if task_row is not None and task_row["status"] in {"pending", "planning", "executing", "validating"}:
                try:
                    task_result = json.loads(task_row["result"]) if task_row["result"] else {}
                except (TypeError, json.JSONDecodeError):
                    task_result = {}
                if not isinstance(task_result, dict):
                    task_result = {}
                task_result.update({
                    "hie_experiment_id": experiment["id"],
                    "recovery_status": "interrupted_by_restart",
                    "automatic_retry": False,
                    "preserved_partial_evidence": recovery["preserved_partial_evidence"],
                })
                task_cursor = connection.execute(
                    "UPDATE tasks SET status = 'failed', result = ?, updated_at = ? WHERE id = ? AND status = ?",
                    (json.dumps(task_result, ensure_ascii=False), _now(), experiment["task_id"], task_row["status"]),
                )
                if task_cursor.rowcount != 1:
                    raise HieExperimentError("Experiment Task changed during startup recovery")
                create_task_event(
                    task_id=experiment["task_id"],
                    conversation_id=task_row["conversation_id"],
                    project_id=task_row["project_id"],
                    component="task",
                    event_name="task.status_changed",
                    message=f"Task status changed from {task_row['status']} to failed during HIE recovery",
                    status="failed",
                    level="warning",
                    metadata={"previous_status": task_row["status"], "status": "failed", "recovery": True},
                    connection=connection,
                )
            previous_event_metadata = {
                "previous_status": previous,
                "provider_outcome": "not_started" if previous == "queued" else "unknown",
                "automatic_retry": False,
                "automatic_promotion": False,
                "preserved_partial_evidence": recovery["preserved_partial_evidence"],
            }
            _emit(
                experiment,
                "hie.experiment_interrupted_by_restart",
                "HIE experiment was interrupted by a Core restart; provider calls were not replayed.",
                "failed",
                previous_event_metadata,
                connection=connection,
            )
            (recovered_queued if previous == "queued" else recovered_running).append(row["id"])
        connection.commit()
    return {"recovered_queued": recovered_queued, "recovered_running": recovered_running}
