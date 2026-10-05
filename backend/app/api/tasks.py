from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.task import Task
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
    conversation_id: int | None = None
    project_id: int | None = None
    type: str | None = None
    mode: str | None = None
    status: str | None = None
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
