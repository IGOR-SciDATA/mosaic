import pytest

from app.db.database import init_db
from app.models.action_repository import create_action, get_action, update_action
from app.models.artifact_repository import list_artifacts
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task, get_task, update_task
from app.models.tool_call_repository import create_tool_call, get_tool_call, update_tool_call
from app.models.tool_result_repository import list_tool_results
from app.services.recovery import recover_interrupted_tasks
from app.tools.builtin import ArtifactTool


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "recovery.db")
    init_db()


def _context(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Recovery", str(workspace))
    model = create_model("Selected", "ollama", "selected:test")
    conversation = create_conversation("Recovery", model.id, project_id=project.id)
    return workspace, project, conversation


def test_startup_recovery_marks_orphaned_execution_failed_without_replaying_it(tmp_path):
    _workspace, project, conversation = _context(tmp_path)
    active = create_task(
        type="report", mode="agent", conversation_id=conversation.id,
        project_id=project.id, plan={"goal": "Create a report"},
    )
    update_task(active.id, status="executing")
    call = create_tool_call(
        conversation.id, "artifact",
        {"format": "markdown", "path": "Report.md", "content": "# Report"},
        task_id=active.id,
    )
    update_tool_call(call.id, status="approved")
    update_tool_call(call.id, status="executing")
    action = create_action(active.id, "write_file", "Report.md", {"path": "Report.md"})
    update_action(action.id, status="approved")
    update_action(action.id, status="executing")

    approval_waiting = create_task(
        type="report", mode="agent", conversation_id=conversation.id,
        project_id=project.id, plan={"goal": "Await explicit approval"},
    )
    update_task(approval_waiting.id, status="planning")
    update_task(approval_waiting.id, status="awaiting_approval")
    pending_call = create_tool_call(
        conversation.id, "artifact",
        {"format": "markdown", "path": "Approved.md", "content": "# Approved"},
        task_id=approval_waiting.id,
    )

    first = recover_interrupted_tasks()
    second = recover_interrupted_tasks()

    recovered = get_task(active.id)
    assert recovered.status == "failed"
    assert recovered.result["recovery"] == {
        "status": "interrupted_by_restart",
        "recoverable": True,
        "resume_requires_user": True,
        "automatic_retry": False,
        "previous_status": "executing",
    }
    assert get_tool_call(call.id).status == "failed"
    results = list_tool_results(call.id)
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "automatic retry suppressed" in results[0].error
    assert get_action(action.id).status == "failed"
    assert get_action(action.id).result["requires_user_review"] is True

    assert get_task(approval_waiting.id).status == "awaiting_approval"
    assert get_tool_call(pending_call.id).status == "pending"
    assert first["recovered_tasks"] == [active.id]
    assert first["recovered_tool_calls"] == [call.id]
    assert first["recovered_actions"] == [action.id]
    assert second["recovered_tasks"] == []
    events = list_task_events(active.id)
    assert sum(event.event_name == "task.interrupted_by_restart" for event in events) == 1
    assert sum(event.event_name == "tool.result_recorded" and event.tool_call_id == call.id for event in events) == 0


def test_artifact_tool_honors_cancellation_before_creating_any_file(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = ArtifactTool()
    result = tool.execute(
        {"format": "markdown", "path": "NeverCreated.md", "content": "# Cancelled"},
        workspace=workspace,
        cancel_check=lambda: True,
    )
    assert result["status"] == "cancelled"
    assert not (workspace / "NeverCreated.md").exists()
    assert list_artifacts(999) == []
