import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection


@dataclass(frozen=True)
class Artifact:
    id: int
    task_id: int
    type: str
    path: str
    metadata: dict[str, Any]
    created_at: str


def _from_row(row: Any) -> Artifact:
    return Artifact(
        id=row["id"],
        task_id=row["task_id"],
        type=row["type"],
        path=row["path"],
        metadata=json.loads(row["metadata"] or "{}"),
        created_at=row["created_at"],
    )


def get_artifact(artifact_id: int) -> Artifact | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
    return _from_row(row) if row is not None else None


def get_artifact_by_task_path(task_id: int, path: str) -> Artifact | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM artifacts WHERE task_id = ? AND path = ? ORDER BY id DESC LIMIT 1",
            (task_id, path),
        ).fetchone()
    return _from_row(row) if row is not None else None


def list_artifacts(task_id: int) -> list[Artifact]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM artifacts WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
    return [_from_row(row) for row in rows]


def create_artifact(
    task_id: int,
    type: str,
    path: str,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> Artifact:
    if not type.strip() or not path.strip():
        raise ValueError("Artifact type and path are required")
    metadata = metadata or {}
    serialized = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT * FROM artifacts WHERE task_id = ? AND path = ? ORDER BY id DESC LIMIT 1",
            (task_id, path),
        ).fetchone()
        if existing is not None:
            current = json.loads(existing["metadata"] or "{}")
            if existing["type"] == type and current.get("sha256") == metadata.get("sha256"):
                return _from_row(existing)
            raise ValueError("An Artifact is already registered at this Task path")
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        cursor = connection.execute(
            """
            INSERT INTO artifacts (task_id, type, path, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, type, path, serialized, timestamp),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM artifacts WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    if row is None:
        raise RuntimeError("Artifact persistence could not be verified")
    return _from_row(row)
