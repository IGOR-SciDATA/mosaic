"""Persisted HIE opt-in and isolated declarative-instruction experiments.

Promotion and rollback intentionally remain unavailable until their version-bound
approval and restoration contracts are implemented.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.database import get_connection
from app.models.conversation_repository import get_conversation
from app.models.task_event_repository import create_task_event
from app.models.task_repository import get_task
from app.models.project_repository import get_project
from app.services.agent_library import list_project_agents
from app.services.hie_experiments import (
    HieExperimentError, create_experiment, get_experiment, list_experiments,
    queue_experiment, reject_experiment, run_experiment,
)

router = APIRouter(prefix="/hie", tags=["hie"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_scope(conversation_id: int | None, task_id: int | None) -> tuple[str, int]:
    if (conversation_id is None) == (task_id is None):
        raise HTTPException(status_code=422, detail="Provide exactly one of conversation_id or task_id")
    if task_id is not None:
        task = get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return "task", task_id
    if get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return "conversation", conversation_id


def _read_session(scope: str, scope_id: int) -> bool:
    column = "task_id" if scope == "task" else "conversation_id"
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT enabled FROM hie_sessions WHERE {column} = ?", (scope_id,)
        ).fetchone()
    return bool(row["enabled"]) if row else False


def _experiment_scope_available(scope: str, scope_id: int) -> bool:
    if scope == "task":
        task = get_task(scope_id)
        if task is None:
            return False
        conversation = get_conversation(task.conversation_id) if task.conversation_id is not None else None
        project_id = (conversation.project_id if conversation else None) or task.project_id
    else:
        conversation = get_conversation(scope_id)
        project_id = conversation.project_id if conversation else None
    if project_id is None or get_project(project_id) is None:
        return False
    try:
        return bool(list_project_agents(project_id))
    except ValueError:
        return False


def _payload(scope: str, scope_id: int, enabled: bool) -> dict:
    experiment_available = _experiment_scope_available(scope, scope_id)
    supported = ["persisted_opt_in"]
    unavailable = [
        "project_scoped_agent_profile_required",
        "isolated_baseline_candidate_probes",
        "deterministic_fixture_evaluation",
        "candidate_diff",
        "candidate_hash",
        "explicit_rejection",
        "versioned_promotion",
        "rollback",
    ]
    if experiment_available:
        supported.extend([
            "candidate_validation",
            "persisted_experiment_lifecycle",
            "isolated_baseline_candidate_probes",
            "deterministic_fixture_evaluation",
            "candidate_diff",
            "candidate_hash",
            "explicit_rejection",
        ])
        unavailable = ["versioned_promotion", "rollback"]
    message = (
        "Modo experimental habilitado. Experimentos isolados com baseline/candidato estão disponíveis; "
        "promoção e rollback ainda não estão disponíveis."
        if enabled and experiment_available else
        "HIE está habilitado, mas é necessário um projeto com pelo menos um perfil de agente para criar experimentos."
        if enabled else
        "HIE está desativado neste escopo. A ativação não executa nem promove candidatos."
    )
    return {
        "available": True,
        "scope": scope,
        "scope_id": scope_id,
        "enabled": enabled,
        "default_enabled": False,
        "experiment_execution_available": experiment_available,
        "supported_capabilities": supported,
        "unavailable_capabilities": unavailable,
        "message": message,
    }

class HieModeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: int | None = None
    task_id: int | None = None
    enabled: bool

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.conversation_id is None) == (self.task_id is None):
            raise ValueError("Provide exactly one of conversation_id or task_id")
        return self


@router.get("/status")
def get_hie_status(
    conversation_id: int | None = Query(default=None),
    task_id: int | None = Query(default=None),
) -> dict:
    scope, scope_id = _resolve_scope(conversation_id, task_id)
    return _payload(scope, scope_id, _read_session(scope, scope_id))


@router.put("/status")
def set_hie_status(payload: HieModeUpdate) -> dict:
    scope, scope_id = _resolve_scope(payload.conversation_id, payload.task_id)
    column = "task_id" if scope == "task" else "conversation_id"
    now = _now()
    with get_connection() as connection:
        connection.execute(
            f"""
            INSERT INTO hie_sessions ({column}, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT({column}) DO UPDATE SET
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (scope_id, int(payload.enabled), now, now),
        )
        connection.commit()

    experiment_available = _experiment_scope_available(scope, scope_id)
    if scope == "task":
        task = get_task(scope_id)
        if task is not None:
            create_task_event(
                task_id=task.id,
                conversation_id=task.conversation_id,
                project_id=task.project_id,
                component="hie",
                event_name="hie.mode_enabled" if payload.enabled else "hie.mode_disabled",
                message=(
                    "HIE experimental mode enabled for this Task scope."
                    if payload.enabled else
                    "HIE experimental mode disabled for this Task scope."
                ),
                status="enabled" if payload.enabled else "disabled",
                metadata={
                    "scope": "task",
                    "scope_id": scope_id,
                    "experiment_execution_available": experiment_available,
                },
            )
    return _payload(scope, scope_id, payload.enabled)


class HieFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=2000)
    expected_contains: list[str] = Field(default_factory=list, max_length=10)
    expected_not_contains: list[str] = Field(default_factory=list, max_length=10)


class HieExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: int | None = None
    task_id: int | None = None
    profile_slug: str = Field(min_length=1, max_length=80)
    candidate_content: str = Field(min_length=1, max_length=12000)
    fixtures: list[HieFixture] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.conversation_id is None) == (self.task_id is None):
            raise ValueError("Provide exactly one of conversation_id or task_id")
        return self


@router.post("/experiments", status_code=201)
def create_hie_experiment(payload: HieExperimentCreate) -> dict:
    try:
        return create_experiment(
            conversation_id=payload.conversation_id,
            task_id=payload.task_id,
            profile_slug=payload.profile_slug,
            candidate_content=payload.candidate_content,
            fixtures=[fixture.model_dump() for fixture in payload.fixtures],
        )
    except HieExperimentError as exc:
        message = str(exc)
        status = 404 if message.endswith("not found") or message == "Agent profile not found in this project" else 409 if "enabled" in message or "already" in message else 422
        raise HTTPException(status_code=status, detail=message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/experiments")
def list_hie_experiments(
    conversation_id: int | None = Query(default=None),
    task_id: int | None = Query(default=None),
) -> list[dict]:
    try:
        return list_experiments(task_id=task_id, conversation_id=conversation_id)
    except HieExperimentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/experiments/{experiment_id}")
def get_hie_experiment(experiment_id: int) -> dict:
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


@router.post("/experiments/{experiment_id}/run", status_code=202)
def run_hie_experiment(experiment_id: int, background_tasks: BackgroundTasks) -> dict:
    try:
        experiment = queue_experiment(experiment_id)
    except HieExperimentError as exc:
        message = str(exc)
        status = 404 if message == "Experiment not found" else 409
        raise HTTPException(status_code=status, detail=message) from exc
    background_tasks.add_task(run_experiment, experiment_id)
    return experiment


@router.post("/experiments/{experiment_id}/reject")
def reject_hie_experiment(experiment_id: int) -> dict:
    try:
        return reject_experiment(experiment_id)
    except HieExperimentError as exc:
        message = str(exc)
        status = 404 if message == "Experiment not found" else 409
        raise HTTPException(status_code=status, detail=message) from exc
