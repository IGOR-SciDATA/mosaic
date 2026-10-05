from datetime import datetime, timezone

from app.db.database import get_connection
from app.models.memory import Memory


ALLOWED_TYPES = {
    "user_fact",
    "user_preference",
    "user_claim",
    "project_state",
    "instruction",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_memory(
    type: str,
    key: str,
    value: str,
    source: str,
    project_id: int | None = None,
    confidence: float | None = None,
) -> Memory:
    if type not in ALLOWED_TYPES:
        raise ValueError(f"Invalid memory type: {type}")
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("Memory confidence must be between 0.0 and 1.0")

    created_at = _utc_now()
    updated_at = created_at

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO memories (
                project_id, type, key, value, source, confidence, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, type, key, value, source, confidence, created_at, updated_at),
        )
        connection.commit()

    return Memory(
        id=cursor.lastrowid,
        project_id=project_id,
        type=type,
        key=key,
        value=value,
        source=source,
        confidence=confidence,
        created_at=created_at,
        updated_at=updated_at,
    )


def get_memory(memory_id: int) -> Memory | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, project_id, type, key, value, source, confidence, created_at, updated_at
            FROM memories
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_memory(row)


def list_memories(project_id: int | None = None) -> list[Memory]:
    with get_connection() as connection:
        if project_id is None:
            rows = connection.execute(
                """
                SELECT id, project_id, type, key, value, source, confidence, created_at, updated_at
                FROM memories
                ORDER BY id ASC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, project_id, type, key, value, source, confidence, created_at, updated_at
                FROM memories
                WHERE project_id = ?
                ORDER BY id ASC
                """,
                (project_id,),
            ).fetchall()

    return [_row_to_memory(row) for row in rows]


def _row_to_memory(row) -> Memory:
    return Memory(
        id=row["id"],
        project_id=row["project_id"],
        type=row["type"],
        key=row["key"],
        value=row["value"],
        source=row["source"],
        confidence=row["confidence"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
