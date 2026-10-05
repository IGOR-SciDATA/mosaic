import json
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection
from app.models.tool_call import ToolCall

ALLOWED_STATUSES = {
    "pending",
    "approved",
    "executing",
    "completed",
    "failed",
    "rejected",
    "cancelled",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_status(status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid tool call status: {status}")


def create_tool_call(
    conversation_id: int,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    task_id: int | None = None,
    status: str = "pending",
) -> ToolCall:
    if not tool_name:
        raise ValueError("Tool name is required")
    _validate_status(status)
    tool_arguments = arguments or {}
    created_at = _utc_now()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tool_calls (
                conversation_id, task_id, tool_name, arguments,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                task_id,
                tool_name,
                json.dumps(tool_arguments),
                status,
                created_at,
                created_at,
            ),
        )
        connection.commit()

    return ToolCall(
        id=cursor.lastrowid,
        conversation_id=conversation_id,
        task_id=task_id,
        tool_name=tool_name,
        arguments=tool_arguments,
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


def get_tool_call(tool_call_id: int) -> ToolCall | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, conversation_id, task_id, tool_name, arguments,
                   status, created_at, updated_at
            FROM tool_calls
            WHERE id = ?
            """,
            (tool_call_id,),
        ).fetchone()

    return _row_to_tool_call(row) if row else None


def list_tool_calls(conversation_id: int) -> list[ToolCall]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, conversation_id, task_id, tool_name, arguments,
                   status, created_at, updated_at
            FROM tool_calls
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()

    return [_row_to_tool_call(row) for row in rows]


def update_tool_call(tool_call_id: int, *, status: str) -> ToolCall | None:
    _validate_status(status)
    current = get_tool_call(tool_call_id)
    if current is None:
        return None

    updated_at = _utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE tool_calls
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, updated_at, tool_call_id),
        )
        connection.commit()

    return get_tool_call(tool_call_id)


def _row_to_tool_call(row) -> ToolCall:
    return ToolCall(
        id=row["id"],
        conversation_id=row["conversation_id"],
        task_id=row["task_id"],
        tool_name=row["tool_name"],
        arguments=json.loads(row["arguments"]),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
