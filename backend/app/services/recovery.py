"""Deterministic startup recovery for persisted Tasks interrupted by a process restart."""

from typing import Any

from app.models.action_repository import list_actions, update_action
from app.models.task_event_repository import create_task_event
from app.models.task_repository import list_tasks, update_task
from app.models.tool_call_repository import list_tool_calls, update_tool_call
from app.models.tool_result_repository import create_tool_result, list_tool_results


_INTERRUPTED_STATUSES = {"planning", "executing", "validating"}


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
                    # A concurrent state transition is authoritative.
                    continue
                recovered_tool_call_ids.append(call.id)
                if not list_tool_results(call.id):
                    create_tool_result(
                        call.id,
                        "failed",
                        error="Execution interrupted by Mosaic Core restart; automatic retry suppressed.",
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
                # Do not overwrite a newer authoritative action state.
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
