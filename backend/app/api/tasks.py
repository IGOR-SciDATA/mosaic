import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.task_event_repository import list_task_events
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
