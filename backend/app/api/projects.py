from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.project import Project
from app.models.project_repository import (
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from app.services.project import create_project_with_workspace


class ProjectCreate(BaseModel):
    name: str
    workspace: str
    description: str | None = None
    metadata: dict[str, Any] = {}
    state: dict[str, Any] = {}


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    metadata: dict[str, Any] | None = None
    state: dict[str, Any] | None = None


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project)
def create_project_endpoint(payload: ProjectCreate) -> Project:
    try:
        return create_project_with_workspace(**payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[Project])
def list_projects_endpoint() -> list[Project]:
    return list_projects()


@router.get("/{project_id}", response_model=Project)
def get_project_endpoint(project_id: int) -> Project:
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=Project)
def update_project_endpoint(project_id: int, payload: ProjectUpdate) -> Project:
    try:
        project = update_project(project_id, **payload.model_dump(exclude_unset=True))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project_endpoint(project_id: int) -> dict[str, bool]:
    if not delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}
