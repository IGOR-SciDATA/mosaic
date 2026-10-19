import json
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection
from app.models.project import Project


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_project(
    name: str,
    workspace: str,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> Project:
    created_at = _utc_now()
    metadata_value = metadata or {}
    state_value = state or {}

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO projects (
                name, description, workspace, metadata, state, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                description,
                workspace,
                json.dumps(metadata_value),
                json.dumps(state_value),
                created_at,
                created_at,
            ),
        )
        connection.commit()

    return Project(
        id=cursor.lastrowid,
        name=name,
        description=description,
        workspace=workspace,
        metadata=metadata_value,
        state=state_value,
        created_at=created_at,
        updated_at=created_at,
    )


def get_project(project_id: int) -> Project | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, description, workspace, metadata, state, created_at, updated_at
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

    return _row_to_project(row) if row else None


def list_projects() -> list[Project]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, workspace, metadata, state, created_at, updated_at
            FROM projects
            ORDER BY id ASC
            """
        ).fetchall()

    return [_row_to_project(row) for row in rows]


def update_project(
    project_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    workspace: str | None = None,
    metadata: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> Project | None:
    current = get_project(project_id)
    if current is None:
        return None

    updated_at = _utc_now()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE projects
            SET name = ?, description = ?, workspace = ?, metadata = ?, state = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                current.name if name is None else name,
                current.description if description is None else description,
                current.workspace if workspace is None else workspace,
                json.dumps(current.metadata if metadata is None else metadata),
                json.dumps(current.state if state is None else state),
                updated_at,
                project_id,
            ),
        )
        connection.commit()

    return get_project(project_id)


def delete_project(project_id: int) -> bool:
    """Delete a project while preserving its conversations and memories as unassigned records."""
    with get_connection() as connection:
        project = connection.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if project is None:
            return False

        task_rows = connection.execute("SELECT id, status, conversation_id FROM tasks WHERE project_id = ?", (project_id,)).fetchall()
        if any(row["status"] not in {"completed", "failed", "cancelled"} for row in task_rows):
            raise ValueError("This project has active Tasks; cancel or finish them before deleting it")

        # A project-only Task cannot survive SET NULL because the schema requires
        # either a conversation or project owner. Remove only these terminal Tasks.
        orphan_task_ids = [row["id"] for row in task_rows if row["conversation_id"] is None]
        if orphan_task_ids:
            placeholders = ",".join("?" for _ in orphan_task_ids)
            connection.execute("DELETE FROM tasks WHERE id IN (" + placeholders + ")", orphan_task_ids)

        # Foreign keys set project_id to NULL for conversations, memories, remaining
        # Tasks, and task events; their persisted content is intentionally preserved.
        connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        connection.commit()
        return True

def _row_to_project(row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        workspace=row["workspace"],
        metadata=json.loads(row["metadata"]),
        state=json.loads(row["state"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
