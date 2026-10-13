from collections.abc import Callable
from typing import Any

from app.context.manager import build_context
from app.models.task_repository import get_task, update_task
from app.models.tool_call_repository import create_tool_call
from app.models.tool_result import ToolResult
from app.services.tools import approve_tool_call, execute_tool_call, resolve_tool_policy

DEFAULT_ITERATION_LIMIT = 5
TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}


def _tool_context(tool_call_id: int, result: ToolResult) -> dict[str, str]:
    if result.status == "completed":
        content = f"ToolResult {tool_call_id}: {result.data}"
    else:
        content = f"ToolResult {tool_call_id} failed: {result.error}"
    return {"role": "tool", "content": content}


def _task_status(task_id: int) -> str:
    task = get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    return task.status


def _cancelled_result(task_id: int, iterations: int) -> dict[str, Any]:
    # Cancellation may arrive while the model/provider callback is running.
    # Never attempt to overwrite the cancelled state with failed/completed.
    if _task_status(task_id) != "cancelled":
        update_task(task_id, status="cancelled")
    return {"status": "cancelled", "iterations": iterations}


def run_agent(
    task_id: int,
    decide: Callable[[list[dict[str, str]]], dict[str, Any]],
    *,
    iteration_limit: int = DEFAULT_ITERATION_LIMIT,
) -> dict[str, Any]:
    if iteration_limit <= 0:
        raise ValueError("iteration_limit must be greater than zero")
    task = get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.mode != "agent":
        raise ValueError("Task must use agent mode")
    if task.conversation_id is None:
        raise ValueError("Agent task requires a conversation")

    # Do not revive a task that has already reached a terminal state, or silently
    # restart a task paused for a human approval decision.
    if task.status == "cancelled":
        return {"status": "cancelled", "iterations": 0}
    if task.status in {"completed", "failed"}:
        return {"status": task.status, "iterations": 0}
    if task.status == "awaiting_approval":
        return {
            "status": "awaiting_approval",
            "tool_call_id": (task.result or {}).get("tool_call_id"),
            "iterations": (task.result or {}).get("iterations", 0),
        }
    if task.status not in {"pending", "executing"}:
        raise ValueError(f"Task is not executable: {task.status}")

    context = build_context(task.conversation_id)
    if task.status == "pending":
        update_task(task_id, status="executing")

    for iteration in range(1, iteration_limit + 1):
        current = get_task(task_id)
        if current is None:
            raise ValueError("Task not found")
        if current.status == "cancelled":
            return {"status": "cancelled", "iterations": iteration - 1}
        if current.status != "executing":
            if current.status == "awaiting_approval":
                return {
                    "status": "awaiting_approval",
                    "tool_call_id": (current.result or {}).get("tool_call_id"),
                    "iterations": (current.result or {}).get("iterations", iteration - 1),
                }
            raise ValueError(f"Task is not executable: {current.status}")

        try:
            decision = decide(context)
        except Exception as exc:
            if _task_status(task_id) == "cancelled":
                return _cancelled_result(task_id, iteration)
            error = f"{type(exc).__name__}: {exc}"
            update_task(task_id, status="failed", result={"error": error, "iterations": iteration})
            return {"status": "failed", "error": error, "iterations": iteration}

        current = get_task(task_id)
        if current is None:
            raise ValueError("Task not found")
        if current.status == "cancelled":
            return {"status": "cancelled", "iterations": iteration}
        if current.status != "executing":
            if current.status == "awaiting_approval":
                return {
                    "status": "awaiting_approval",
                    "tool_call_id": (current.result or {}).get("tool_call_id"),
                    "iterations": (current.result or {}).get("iterations", iteration),
                }
            raise ValueError(f"Task is not executable: {current.status}")

        decision_type = decision.get("type")
        if decision_type == "final":
            result = {"output": decision.get("content", ""), "iterations": iteration}
            # Re-check immediately before the terminal transition.
            if _task_status(task_id) == "cancelled":
                return _cancelled_result(task_id, iteration)
            update_task(task_id, status="completed", result=result)
            return {"status": "completed", **result}
        if decision_type != "tool_call":
            error = f"Invalid agent decision type: {decision_type}"
            update_task(task_id, status="failed", result={"error": error, "iterations": iteration})
            return {"status": "failed", "error": error, "iterations": iteration}

        tool_name = decision.get("tool")
        arguments = decision.get("arguments", {})
        if not isinstance(tool_name, str) or not tool_name:
            error = "Agent tool_call requires tool"
            update_task(task_id, status="failed", result={"error": error, "iterations": iteration})
            return {"status": "failed", "error": error, "iterations": iteration}

        try:
            policy = resolve_tool_policy(tool_name, arguments)
        except Exception as exc:
            error = f"Tool request rejected: {type(exc).__name__}: {exc}"
            update_task(task_id, status="failed", result={"error": error, "iterations": iteration})
            return {"status": "failed", "error": error, "iterations": iteration}

        # Cancellation can happen after the model decision but before creating an
        # executable side effect. Check before persisting the proposed ToolCall.
        if _task_status(task_id) == "cancelled":
            return _cancelled_result(task_id, iteration)

        call = create_tool_call(task.conversation_id, tool_name, arguments, task_id=task_id)
        try:
            if policy["approval_required"]:
                update_task(
                    task_id,
                    status="awaiting_approval",
                    result={"tool_call_id": call.id, "iterations": iteration},
                )
                return {"status": "awaiting_approval", "tool_call_id": call.id, "iterations": iteration}
            approved = approve_tool_call(call)
            tool_result = execute_tool_call(approved)
        except Exception as exc:
            if _task_status(task_id) == "cancelled":
                return _cancelled_result(task_id, iteration)
            # A tool failure is an observation, not necessarily a fatal agent error.
            context.append({"role": "tool", "content": f"ToolCall {call.id} failed: {type(exc).__name__}: {exc}"})
            continue

        if _task_status(task_id) == "cancelled":
            return _cancelled_result(task_id, iteration)
        context.append(_tool_context(call.id, tool_result))

    result = {"error": "Agent iteration limit reached", "iterations": iteration_limit}
    if _task_status(task_id) == "cancelled":
        return _cancelled_result(task_id, iteration_limit)
    update_task(task_id, status="failed", result=result)
    return {"status": "failed", **result}
