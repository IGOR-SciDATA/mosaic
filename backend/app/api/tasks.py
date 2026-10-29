import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.models.artifact_repository import list_artifacts
from app.models.conversation_repository import get_conversation
from app.models.message_repository import create_message, list_messages
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.task_event_repository import create_task_event, list_task_events
from app.models.action_repository import list_actions
from app.permissions import cancel_action
from app.services.agent import run_agent
from app.services.tools import approve_tool_call, execute_tool_call, resolve_tool_workspace
from app.models.tool_call_repository import get_tool_call, list_tool_calls, update_tool_call
from app.services.agent_decision import create_provider_decider
from app.services.task_coordinator import run_coordinated_task, validate_coordinator_plan
from app.services.agent_library import parse_agent_invocation
from app.db.database import get_connection
from app.models.task_repository import (
    create_task,
    delete_task,
    get_task,
    list_tasks,
    update_task,
)


class TaskCreate(BaseModel):
    type: str
    mode: str
    conversation_id: int | None = None
    project_id: int | None = None
    status: str = "pending"
    plan: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class TaskStart(BaseModel):
    conversation_id: int
    goal: str
    type: str = "generic"


class ToolDecision(BaseModel):
    decision: str


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: int | None = None
    project_id: int | None = None
    type: str | None = None
    mode: str | None = None
    plan: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _inherit_conversation_hie_mode(task: Task) -> None:
    """Inherit conversation opt-in into a Task only when it has no explicit Task setting."""
    if task.id is None or task.conversation_id is None:
        return
    with get_connection() as connection:
        task_setting = connection.execute(
            "SELECT enabled FROM hie_sessions WHERE task_id = ?", (task.id,)
        ).fetchone()
        conversation_setting = connection.execute(
            "SELECT enabled FROM hie_sessions WHERE conversation_id = ?", (task.conversation_id,)
        ).fetchone()
        if task_setting is not None or conversation_setting is None or not conversation_setting["enabled"]:
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        connection.execute(
            """INSERT INTO hie_sessions (task_id, enabled, created_at, updated_at)
               VALUES (?, 1, ?, ?)""",
            (task.id, now, now),
        )
        connection.commit()
    create_task_event(
        task_id=task.id,
        conversation_id=task.conversation_id,
        project_id=task.project_id,
        component="hie",
        event_name="hie.mode_inherited",
        message="Task inherited the conversation's explicit HIE experimental opt-in.",
        status="enabled",
        metadata={"scope": "task", "source": "conversation", "experiment_execution_available": False},
    )


@router.post("", response_model=Task)
def create_task_endpoint(payload: TaskCreate) -> Task:
    try:
        task = create_task(**payload.model_dump())
        return task
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[Task])
def list_tasks_endpoint() -> list[Task]:
    return list_tasks()


@router.get("/{task_id}/events", response_model=list[TaskEvent])
def list_task_events_endpoint(task_id: int, after_id: int = 0, limit: int = 100) -> list[TaskEvent]:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return list_task_events(task_id, after_id=after_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{task_id}/events/stream")
async def stream_task_events_endpoint(
    task_id: int, request: Request, after_id: int = 0,
) -> StreamingResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        try:
            after_id = max(after_id, int(last_event_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Last-Event-ID header")
    if after_id < 0:
        raise HTTPException(status_code=422, detail="after_id must be non-negative")

    async def generate():
        cursor = after_id
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if await request.is_disconnected():
                break
            events = list_task_events(task_id, after_id=cursor, limit=100)
            if events:
                for event in events:
                    payload = json.dumps({
                        "id": event.id, "task_id": event.task_id,
                        "conversation_id": event.conversation_id, "project_id": event.project_id,
                        "tool_call_id": event.tool_call_id, "action_id": event.action_id,
                        "timestamp": event.timestamp, "level": event.level,
                        "component": event.component, "event_name": event.event_name,
                        "message": event.message, "duration_ms": event.duration_ms,
                        "status": event.status, "metadata": event.metadata,
                    }, ensure_ascii=False)
                    yield f"id: {event.id}\nevent: task_event\ndata: {payload}\n\n"
                    cursor = event.id
            else:
                yield ": keep-alive\n\n"
                await asyncio.sleep(1)

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{task_id}", response_model=Task)
def get_task_endpoint(task_id: int) -> Task:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


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
    try:
        if not delete_task(task_id):
            raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"deleted": True}



def _resume_coordinator_for_child(task_id: int) -> None:
    child = get_task(task_id)
    if child is None or child.status not in {"completed", "failed", "cancelled"}:
        return
    child_plan = child.plan if isinstance(child.plan, dict) else {}
    parent_id = child_plan.get("coordinator_task_id")
    if not isinstance(parent_id, int):
        return
    parent = get_task(parent_id)
    if parent is None or parent.status in {"completed", "failed", "cancelled"}:
        return
    try:
        run_coordinated_task(parent_id)
    except Exception as exc:
        parent = get_task(parent_id)
        if parent is None:
            return
        if parent.status in {"pending", "planning", "executing", "awaiting_approval", "validating"}:
            try:
                parent = update_task(
                    parent_id,
                    status="failed",
                    result={"error_type": type(exc).__name__, "coordinator_resume_failed": True},
                )
            except ValueError:
                parent = get_task(parent_id) or parent
        try:
            create_task_event(
                task_id=parent_id,
                conversation_id=parent.conversation_id,
                project_id=parent.project_id,
                component="coordinator",
                event_name="coordinator.resume_failed",
                message="Coordinator could not resume after child Task completion.",
                status="failed",
                level="error",
                metadata={"child_task_id": task_id, "error_type": type(exc).__name__},
            )
        except Exception:
            return


@router.get("/{task_id}/artifacts")
def list_task_artifacts_endpoint(task_id: int) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    recent_events = list_task_events(task_id, after_id=0, limit=200)
    items = []
    for artifact in list_artifacts(task_id):
        expected_hash = artifact.metadata.get("sha256")
        tool_call_id = artifact.metadata.get("tool_call_id")
        tool_call = get_tool_call(tool_call_id) if isinstance(tool_call_id, int) else None
        current_hash = None
        reason = "workspace_unavailable"
        if tool_call is not None:
            try:
                root = resolve_tool_workspace(tool_call)
                candidate = (root / artifact.path).resolve(strict=True)
                candidate.relative_to(root)
                if candidate.is_file():
                    current_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
                    reason = "hash_mismatch" if current_hash != expected_hash else "valid"
                else:
                    reason = "missing"
            except (OSError, RuntimeError, ValueError):
                reason = "missing_or_outside_workspace"

        current_verification = "valid" if reason == "valid" else "invalidated"
        if current_verification == "invalidated":
            already_recorded = any(
                event.event_name == "artifact.evidence_invalidated"
                and event.metadata.get("artifact_id") == artifact.id
                and event.metadata.get("expected_sha256") == expected_hash
                and event.metadata.get("current_sha256") == current_hash
                and event.metadata.get("reason") == reason
                for event in recent_events
            )
            if not already_recorded:
                try:
                    create_task_event(
                        task_id=task_id,
                        conversation_id=task.conversation_id,
                        project_id=task.project_id,
                        tool_call_id=tool_call_id if isinstance(tool_call_id, int) else None,
                        component="verification",
                        event_name="artifact.evidence_invalidated",
                        message="Previously verified Artifact no longer matches its recorded bytes.",
                        status="invalidated",
                        level="warning",
                        metadata={
                            "artifact_id": artifact.id,
                            "path": artifact.path,
                            "expected_sha256": expected_hash,
                            "current_sha256": current_hash,
                            "reason": reason,
                        },
                    )
                except Exception:
                    pass
        items.append({
            "id": artifact.id,
            "task_id": artifact.task_id,
            "type": artifact.type,
            "path": artifact.path,
            "metadata": artifact.metadata,
            "created_at": artifact.created_at,
            "current_verification": current_verification,
            "current_sha256": current_hash,
        })
    return {"items": items}


@router.post("/{task_id}/coordinate", response_model=Task)
def coordinate_task_endpoint(task_id: int, background_tasks: BackgroundTasks) -> Task:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.mode != "agent" or task.conversation_id is None:
        raise HTTPException(status_code=422, detail="Coordinated Tasks require agent mode and a conversation")
    if task.status != "pending":
        raise HTTPException(status_code=409, detail="Only a pending Task can start coordination")
    try:
        validate_coordinator_plan(task.plan)
        planning = update_task(task_id, status="planning")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if planning is None:
        raise HTTPException(status_code=404, detail="Task not found")
    background_tasks.add_task(run_coordinated_task, task_id)
    return planning


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

    # A cancelled Task must not leave unstarted child work available for later execution.
    # In-flight work is deliberately not force-transitioned here: its executor owns the
    # outcome of an operation that may already have produced side effects.
    if cancelled.conversation_id is not None:
        for call in list_tool_calls(cancelled.conversation_id):
            if call.task_id == task_id and call.status in {"pending", "approved"}:
                try:
                    update_tool_call(call.id, status="cancelled")
                except ValueError:
                    # A concurrent executor/decision may have advanced the call already.
                    pass
    for action in list_actions(task_id):
        if action.status in {"pending", "approved"}:
            try:
                cancel_action(action)
            except ValueError:
                # Preserve the authoritative result of a concurrent state transition.
                pass

    plan = cancelled.plan if isinstance(cancelled.plan, dict) else {}
    coordinator = plan.get("coordinator") if isinstance(plan.get("coordinator"), dict) else {}
    child_ids = coordinator.get("children") if isinstance(coordinator.get("children"), dict) else {}
    for child_id in child_ids.values():
        if not isinstance(child_id, int):
            continue
        child = get_task(child_id)
        if child is not None and child.status not in {"completed", "failed", "cancelled"}:
            try:
                cancel_task_endpoint(child_id)
            except HTTPException:
                pass
    _resume_coordinator_for_child(task_id)
    return cancelled



def _execute_approved_call_and_resume(task_id: int, tool_call_id: int) -> None:
    """Execute a pre-approved persisted ToolCall and resume the same Task."""
    try:
        current = get_task(task_id)
        call = get_tool_call(tool_call_id)
        if call is None or call.task_id != task_id or call.status != "approved":
            raise ValueError("Approved ToolCall is no longer available")
        if current is None or current.status == "cancelled":
            update_tool_call(tool_call_id, status="cancelled")
            return
        execute_tool_call(call)
        current = get_task(task_id)
        if current is None or current.status == "cancelled":
            return
        if current.status != "executing":
            return
        _run_provider_agent(task_id)
    except Exception as exc:
        current = get_task(task_id)
        if current is not None and current.status == "executing":
            try:
                update_task(task_id, status="failed", result={
                    "error": f"{type(exc).__name__}: {exc}",
                    "tool_call_id": tool_call_id,
                })
            except ValueError:
                pass


def _run_provider_agent(task_id: int) -> None:
    """Execute the persisted Task in the in-process background worker."""
    try:
        run_agent(task_id, create_provider_decider(task_id))
    except Exception as exc:
        current = get_task(task_id)
        if current is not None and current.status in {"pending", "executing"}:
            try:
                update_task(task_id, status="failed", result={"error": f"{type(exc).__name__}: {exc}"})
            except ValueError:
                # A concurrent cancellation or terminal transition remains authoritative.
                pass
    _resume_coordinator_for_child(task_id)


@router.post("/start", response_model=Task, status_code=202)
def start_agent_task_endpoint(payload: TaskStart, background_tasks: BackgroundTasks) -> Task:
    """Persist the user's goal, create an agent Task, and start the provider-backed loop."""
    raw_goal = payload.goal.strip()
    if not raw_goal:
        raise HTTPException(status_code=422, detail="Task goal must not be empty")
    conversation = get_conversation(payload.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if payload.type not in {"code_project", "document", "analysis", "report", "generic"}:
        raise HTTPException(status_code=422, detail="Invalid task type")
    try:
        goal, agent_snapshot = parse_agent_invocation(conversation.project_id, raw_goal)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Persist the resolved goal as a normal conversation message and freeze the selected profile in Task.plan.
    create_message(conversation.id, "user", goal)
    try:
        task_plan = {"goal": goal}
        if agent_snapshot is not None:
            task_plan["agent_library_snapshot"] = agent_snapshot
        task = create_task(
            type=payload.type,
            mode="agent",
            conversation_id=conversation.id,
            project_id=conversation.project_id,
            plan=task_plan,
        )
        _inherit_conversation_hie_mode(task)
        claimed = update_task(task.id, status="executing")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if claimed is None:
        raise HTTPException(status_code=500, detail="Could not claim newly created Task")
    background_tasks.add_task(_run_provider_agent, task.id)
    return claimed


@router.post("/{task_id}/run", response_model=Task, status_code=202)
def run_task_endpoint(task_id: int, background_tasks: BackgroundTasks) -> Task:
    """Explicitly start an agent-mode Task; normal chat remains unchanged."""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.mode != "agent":
        raise HTTPException(status_code=409, detail="Task must use agent mode")
    conversation = get_conversation(task.conversation_id) if task.conversation_id is not None else None
    if conversation is None:
        raise HTTPException(status_code=400, detail="Agent Task requires a valid conversation")
    if task.status != "pending":
        raise HTTPException(status_code=409, detail=f"Task cannot start from status: {task.status}")
    plan = dict(task.plan or {})
    raw_goal = plan.get("goal")
    if isinstance(raw_goal, str) and raw_goal.strip().startswith("/") and "agent_library_snapshot" not in plan:
        scope_project_id = conversation.project_id if conversation.project_id is not None else task.project_id
        try:
            goal, agent_snapshot = parse_agent_invocation(scope_project_id, raw_goal)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        plan["goal"] = goal
        plan["agent_library_snapshot"] = agent_snapshot
        update_task(task_id, plan=plan)
        messages = list_messages(conversation.id)
        last_user = next((message for message in reversed(messages) if message.role == "user"), None)
        if last_user is None or last_user.content != goal:
            create_message(conversation.id, "user", goal)
    _inherit_conversation_hie_mode(task)
    try:
        claimed = update_task(task_id, status="executing")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if claimed is None:
        raise HTTPException(status_code=404, detail="Task not found")
    background_tasks.add_task(_run_provider_agent, task_id)
    return claimed


@router.post("/{task_id}/tool-calls/{tool_call_id}/decision", response_model=Task, status_code=202)
def decide_tool_call_endpoint(
    task_id: int,
    tool_call_id: int,
    payload: ToolDecision,
    background_tasks: BackgroundTasks,
) -> Task:
    """Approve/reject the pending call, then resume the same persisted agent Task."""
    if payload.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'reject'")
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Task is not awaiting approval")
    call = get_tool_call(tool_call_id)
    if call is None or call.task_id != task_id:
        raise HTTPException(status_code=404, detail="Pending ToolCall not found for this Task")
    if call.status != "pending":
        raise HTTPException(status_code=409, detail=f"ToolCall is no longer pending: {call.status}")
    if payload.decision == "reject":
        try:
            update_tool_call(tool_call_id, status="rejected")
            updated = update_task(task_id, status="failed", result={
                "error": "A operação solicitada foi recusada pelo usuário.",
                "tool_call_id": tool_call_id,
            })
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if updated is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return updated

    try:
        approve_tool_call(call)
        updated = update_task(task_id, status="executing", result={
            "last_tool_call_id": tool_call_id,
            "resuming": True,
        })
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
    background_tasks.add_task(_execute_approved_call_and_resume, task_id, tool_call_id)
    return updated
