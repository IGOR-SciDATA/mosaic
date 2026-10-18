import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.tasks import (
    ToolDecision,
    cancel_task_endpoint,
    decide_tool_call_endpoint,
    delete_task_endpoint,
)
from app.db.database import get_connection, init_db
from app.models.action_repository import create_action, get_action
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_repository import create_task, get_task, update_task
from app.models.tool_call_repository import create_tool_call, get_tool_call
from app.permissions import approve_action
from app.services.tools import approve_tool_call


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "task-cancellation.db")
    init_db()


def test_cancelling_task_cancels_unstarted_tool_calls_and_actions(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Cancellation", str(workspace))
    model = create_model("Test", "ollama", "test:model")
    conversation = create_conversation("Cancellation", model.id, project_id=project.id)
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
    )

    arguments = {"operation": "create", "path": "Output.md", "content": "# Output\\n"}
    pending_call = create_tool_call(
        conversation.id, "filesystem", arguments, task_id=task.id
    )
    approved_call = approve_tool_call(
        create_tool_call(conversation.id, "filesystem", arguments, task_id=task.id)
    )
    pending_action = create_action(task.id, "write_file")
    approved_action = approve_action(create_action(task.id, "write_file"))

    cancelled = cancel_task_endpoint(task.id)

    assert cancelled.status == "cancelled"
    assert get_task(task.id).status == "cancelled"
    assert get_tool_call(pending_call.id).status == "cancelled"
    assert get_tool_call(approved_call.id).status == "cancelled"
    assert get_action(pending_action.id).status == "cancelled"
    assert get_action(approved_action.id).status == "cancelled"

    with pytest.raises(HTTPException) as exc:
        decide_tool_call_endpoint(
            task.id,
            pending_call.id,
            ToolDecision(decision="approve"),
            BackgroundTasks(),
        )
    assert exc.value.status_code == 409
    with get_connection() as connection:
        result_count = connection.execute(
            "SELECT COUNT(*) AS count FROM tool_results WHERE tool_call_id IN (?, ?)",
            (pending_call.id, approved_call.id),
        ).fetchone()["count"]
    assert result_count == 0


def test_active_task_cannot_be_deleted_before_terminal_state(tmp_path):
    project = create_project("Delete guard", str(tmp_path / "workspace"))
    task = create_task(type="generic", mode="agent", project_id=project.id)
    update_task(task.id, status="executing")

    with pytest.raises(HTTPException) as exc:
        delete_task_endpoint(task.id)

    assert exc.value.status_code == 409
    assert get_task(task.id).status == "executing"
