"""Persisted, opt-in HIE mode for conversation and Task scopes.

This API intentionally exposes mode activation separately from experiment execution:
the current HIE implementation validates declarative candidates but does not yet
provide isolated baseline/candidate runs, evaluation, promotion, or rollback.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator

from app.db.database import get_connection
from app.models.conversation_repository import get_conversation
from app.models.task_event_repository import create_task_event
from app.models.task_repository import get_task

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


def _payload(scope: str, scope_id: int, enabled: bool) -> dict:
    return {
        "available": True,
        "scope": scope,
        "scope_id": scope_id,
        "enabled": enabled,
        "default_enabled": False,
        "experiment_execution_available": False,
        "supported_capabilities": ["persisted_opt_in", "candidate_validation"],
        "unavailable_capabilities": [
            "isolated_baseline_candidate_execution",
            "reproducible_evaluation",
            "promotion",
            "rollback",
        ],
        "message": (
            "Modo experimental habilitado para este escopo. A execução de experimentos "
            "baseline/candidato ainda não está disponível; nenhuma alteração foi aplicada."
            if enabled else
            "HIE está desativado neste escopo. A ativação não executa nem promove candidatos."
        ),
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
                    "experiment_execution_available": False,
                },
            )
    return _payload(scope, scope_id, payload.enabled)
