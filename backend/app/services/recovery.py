"""Deterministic startup recovery for persisted Tasks and HIE experiments."""

import json
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection
from app.models.action_repository import list_actions, update_action
from app.models.task_event_repository import create_task_event, _redact
from app.models.task_repository import get_task, list_tasks, update_task
from app.models.tool_call_repository import list_tool_calls, update_tool_call
from app.models.tool_result_repository import create_tool_result, list_tool_results


_INTERRUPTED_STATUSES = {"planning", "executing", "validating"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_hie_recovery_event(connection, experiment: dict[str, Any], message: str) -> None:
    metadata = _redact({
        "experiment_id": experiment["id"],
        "error_type": "InterruptedByRestart",
        "previous_status": experiment["status"],
        "automatic_retry": False,
        "resume_requires_user": True,
        "preserved_partial_evidence": True,
    })
    encoded = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    connection.execute(
        """INSERT INTO task_events (
            task_id, conversation_id, project_id, tool_call_id, action_id,
            timestamp, level, component, event_name, message, duration_ms, status, metadata
        ) VALUES (?, ?, ?, NULL, NULL, ?, 'warning', 'recovery',
                  'hie.experiment_interrupted_by_restart', ?, NULL, 'failed', ?)""",
        (
            experiment["task_id"], experiment["conversation_id"], experiment["project_id"],
            _now(), message[:500], encoded,
        ),
    )


def recover_interrupted_hie_experiments() -> dict[str, Any]:
    """Fail closed on experiments interrupted by restart; preserve evidence and never replay."""
    recovered: list[int] = []
    recovered_tasks: list[int] = []
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute(
            "SELECT * FROM hie_experiments WHERE status IN ('queued', 'running') ORDER BY id"
        ).fetchall()
        for row in rows:
            experiment = dict(row)
            try:
                previous_results = json.loads(experiment["results"]) if experiment["results"] else {}
            except (TypeError, json.JSONDecodeError):
                previous_results = {}
            if not isinstance(previous_results, dict):
                previous_results = {"previous_results_preview": str(previous_results)[:500]}
            results = {
                **previous_results,
                "error": "HIE experiment interrupted by Mosaic Core restart; retry requires an explicit user action.",
                "error_type": "InterruptedByRestart",
                "assessment_scope": "submitted_deterministic_fixtures_only",
                "automatic_promotion": False,
                "automatic_retry": False,
                "recovery_requires_user": True,
            }
            cursor = connection.execute(
                """UPDATE hie_experiments SET status = 'failed', results = ?, updated_at = ?
                   WHERE id = ? AND status IN ('queued', 'running')""",
                (json.dumps(results, ensure_ascii=False), _now(), experiment["id"]),
            )
            if cursor.rowcount != 1:
                continue
            _insert_hie_recovery_event(
                connection,
                experiment,
                "HIE experiment was interrupted by restart; partial fixture evidence was kept and no automatic replay occurred.",
            )
            # Recover the dedicated Task in the same transaction so both lifecycles
            # remain consistent; generic Task recovery will skip its failed state.
            task_row = connection.execute(
                "SELECT id, status, result FROM tasks WHERE id = ?", (experiment["task_id"],)
            ).fetchone()
            if task_row and task_row["status"] in {"pending", "planning", "executing", "validating"}:
                try:
                    task_result = json.loads(task_row["result"]) if task_row["result"] else {}
                except (TypeError, json.JSONDecodeError):
                    task_result = {}
                if not isinstance(task_result, dict):
                    task_result = {}
                task_result.update({
                    "hie_experiment_id": experiment["id"],
                    "recovery": {
                        "status": "interrupted_by_restart",
                        "automatic_retry": False,
                        "resume_requires_user": True,
                    },
                })
                connection.execute(
                    "UPDATE tasks SET status = 'failed', result = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(task_result, ensure_ascii=False), _now(), experiment["task_id"]),
                )
                recovered_tasks.append(experiment["task_id"])
            recovered.append(experiment["id"])
        connection.commit()

    return {
        "recovered_experiments": recovered,
        "recovered_tasks": recovered_tasks,
        "automatic_retry": False,
    }

def recover_interrupted_tasks() -> dict[str, Any]:
    """Mark nonterminal work interrupted by a prior process as failed and reviewable.

    Pending approvals are intentionally preserved. Recovery never replays a tool,
    approves an action, or retries a model request automatically.
    """
    recovered_task_ids: list[int] = []
    recovered_tool_call_ids: list[int] = []
    recovered_action_ids: list[int] = []

    for task in list_tasks():
        if task.status not in _INTERRUPTED_STATUSES:
            continue

        if task.conversation_id is not None:
            for call in list_tool_calls(task.conversation_id):
                if call.task_id != task.id or call.status != "executing":
                    continue
                try:
                    update_tool_call(call.id, status="failed")
                except ValueError:
                    continue
                recovered_tool_call_ids.append(call.id)
                if not list_tool_results(call.id):
                    result = create_tool_result(
                        call.id,
                        "failed",
                        error="Execution interrupted by Mosaic Core restart; automatic retry suppressed.",
                    )
                    create_task_event(
                        task_id=task.id,
                        conversation_id=task.conversation_id,
                        project_id=task.project_id,
                        tool_call_id=call.id,
                        component="recovery",
                        event_name="tool.result_recorded",
                        message="Interrupted ToolCall recorded as a failed ToolResult; automatic replay suppressed.",
                        status="failed",
                        level="warning",
                        metadata={
                            "tool_result_id": result.id,
                            "error_type": "InterruptedByRestart",
                            "automatic_retry": False,
                        },
                    )

        for action in list_actions(task.id):
            if action.status != "executing":
                continue
            try:
                update_action(
                    action.id,
                    status="failed",
                    result={
                        "error_type": "InterruptedByRestart",
                        "automatic_retry": False,
                        "requires_user_review": True,
                    },
                )
                recovered_action_ids.append(action.id)
            except ValueError:
                continue

        result = dict(task.result or {})
        result["recovery"] = {
            "status": "interrupted_by_restart",
            "recoverable": True,
            "resume_requires_user": True,
            "automatic_retry": False,
            "previous_status": task.status,
        }
        try:
            updated = update_task(task.id, status="failed", result=result)
        except ValueError:
            continue
        if updated is None:
            continue

        create_task_event(
            task_id=task.id,
            conversation_id=task.conversation_id,
            project_id=task.project_id,
            component="recovery",
            event_name="task.interrupted_by_restart",
            message="Task was interrupted by a Mosaic Core restart; no automatic replay was performed.",
            status="failed",
            level="warning",
            metadata={
                "previous_status": task.status,
                "recoverable": True,
                "resume_requires_user": True,
                "automatic_retry": False,
            },
        )
        recovered_task_ids.append(task.id)

    return {
        "recovered_tasks": recovered_task_ids,
        "recovered_tool_calls": recovered_tool_call_ids,
        "recovered_actions": recovered_action_ids,
        "pending_approvals_preserved": True,
    }
