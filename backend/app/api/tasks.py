from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.models.task import Task
from app.models.task_repository import (
    create_task,
    delete_task,
    get_task,
    list_tasks,
    update_task,
)
from app.models.tool_call_repository import get_tool_call, update_tool_call
from app.models.tool_result_repository import create_tool_result
from app.services.tools import approve_tool_call, execute_tool_call, resolve_tool_policy
from app.services.harness import run_task_agent


class TaskCreate(BaseModel):
    type: str
    mode: str
    conversation_id: int | None = None
    project_id: int | None = None
    status: str = "pending"
    plan: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: int | None = None
    project_id: int | None = None
    type: str | None = None
    mode: str | None = None
    plan: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=Task)
def create_task_endpoint(payload: TaskCreate) -> Task:
    try:
        return create_task(**payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[Task])
def list_tasks_endpoint() -> list[Task]:
    return list_tasks()


@router.get("/{task_id}", response_model=Task)
def get_task_endpoint(task_id: int) -> Task:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/run")
def run_task_agent_endpoint(task_id: int) -> dict[str, Any]:
    try:
        return run_task_agent(task_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message in {"Task not found", "Conversation not found", "Model not found"} else 409
        raise HTTPException(status_code=status_code, detail=message) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.patch("/{task_id}", response_model=Task)
def update_task_endpoint(task_id: int, payload: TaskUpdate) -> Task:
    try:
        task = update_task(task_id, **payload.model_dump(exclude_unset=True))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
def delete_task_endpoint(task_id: int) -> dict[str, bool]:
    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}



@router.post("/{task_id}/cancel", response_model=Task)
def cancel_task_endpoint(task_id: int) -> Task:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        cancelled = update_task(task_id, status="cancelled")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if cancelled is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return cancelled



def _pending_approval(task_id: int, tool_call_id: int):
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Task is not awaiting approval")
    if (task.result or {}).get("tool_call_id") != tool_call_id:
        raise HTTPException(status_code=409, detail="ToolCall is not the pending approval for this task")
    call = get_tool_call(tool_call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="ToolCall not found")
    if call.task_id != task_id or call.conversation_id != task.conversation_id:
        raise HTTPException(status_code=409, detail="ToolCall does not belong to this task")
    if call.status != "pending":
        raise HTTPException(status_code=409, detail=f"ToolCall is not pending: {call.status}")
    return task, call


@router.post("/{task_id}/tool-calls/{tool_call_id}/approve", response_model=Task)
def approve_task_tool_call_endpoint(task_id: int, tool_call_id: int) -> Task:
    task, call = _pending_approval(task_id, tool_call_id)
    try:
        policy = resolve_tool_policy(call.tool_name, call.arguments)
        if not policy["approval_required"]:
            raise HTTPException(status_code=409, detail="This ToolCall does not require human approval")
        approved = approve_tool_call(call)
        tool_result = execute_tool_call(approved)
        current = get_task(task_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if current.status == "cancelled":
            return current
        resumed = update_task(
            task_id,
            status="executing",
            result={
                "resumed_tool_call_id": tool_call_id,
                "tool_result_id": tool_result.id,
                "tool_result_status": tool_result.status,
                "iterations": (task.result or {}).get("iterations", 0),
            },
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if resumed is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return resumed


@router.post("/{task_id}/tool-calls/{tool_call_id}/reject", response_model=Task)
def reject_task_tool_call_endpoint(task_id: int, tool_call_id: int) -> Task:
    task, call = _pending_approval(task_id, tool_call_id)
    try:
        policy = resolve_tool_policy(call.tool_name, call.arguments)
        if not policy["approval_required"]:
            raise HTTPException(status_code=409, detail="This ToolCall does not require human approval")
        rejected = update_tool_call(tool_call_id, status="rejected")
        if rejected is None:
            raise HTTPException(status_code=404, detail="ToolCall not found")
        tool_result = create_tool_result(
            tool_call_id,
            "failed",
            error="ToolCall rejected by user; tool was not executed.",
        )
        resumed = update_task(
            task_id,
            status="executing",
            result={
                "resumed_tool_call_id": tool_call_id,
                "tool_result_id": tool_result.id,
                "tool_result_status": tool_result.status,
                "rejected": True,
                "iterations": (task.result or {}).get("iterations", 0),
            },
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if resumed is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return resumed
