import pytest
from fastapi.testclient import TestClient

from app.db.database import init_db
from app.main import app
from app.models.artifact_repository import list_artifacts
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import get_task
from app.models.tool_call_repository import list_tool_calls
from app.services.agent import run_agent


@pytest.fixture
def e2e_environment(monkeypatch, tmp_path):
    database_path = tmp_path / "mosaic-e2e.db"
    monkeypatch.setattr("app.db.database.DATABASE_PATH", database_path)
    init_db()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Mosaic E2E", str(workspace))
    model = create_model("Explicit model", "ollama", "explicit:test")
    conversation = create_conversation(
        "PDF lifecycle", model.id, project_id=project.id
    )
    decisions = []

    def deterministic_worker(task_id):
        task = get_task(task_id)
        if task is None or task.status not in {"pending", "executing"}:
            return
        def decide(_context):
            decisions.append(task_id)
            return {
                "type": "final",
                "content": "# E2E Report\n\nThis report completed through the persisted API workflow.",
            }
        run_agent(task_id, decide)

    monkeypatch.setattr("app.api.tasks._run_provider_agent", deterministic_worker)
    with TestClient(app) as client:
        yield {
            "client": client,
            "workspace": workspace,
            "project": project,
            "conversation": conversation,
            "decisions": decisions,
        }


def test_http_task_approval_artifact_and_event_replay_end_to_end(e2e_environment):
    client = e2e_environment["client"]
    conversation = e2e_environment["conversation"]
    decisions = e2e_environment["decisions"]

    started = client.post(
        "/tasks/start",
        json={
            "conversation_id": conversation.id,
            "goal": "Create a PDF report named Report.pdf",
            "type": "report",
        },
    )
    assert started.status_code == 202
    task_id = started.json()["id"]

    persisted = client.get(f"/tasks/{task_id}")
    assert persisted.status_code == 200
    assert persisted.json()["status"] == "awaiting_approval"

    calls = [
        call for call in list_tool_calls(conversation.id)
        if call.task_id == task_id and call.tool_name == "artifact"
    ]
    assert len(calls) == 1
    assert calls[0].status == "pending"

    approval = client.post(
        f"/tasks/{task_id}/tool-calls/{calls[0].id}/decision",
        json={"decision": "approve"},
    )
    assert approval.status_code == 202

    completed = client.get(f"/tasks/{task_id}")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["result"]["artifact"]["path"] == "Report.pdf"
    assert completed.json()["result"]["artifact"]["verification_event_recorded"] is True
    assert decisions == [task_id], "Approved artifact completion must not call the model again."

    artifacts = client.get(f"/tasks/{task_id}/artifacts")
    assert artifacts.status_code == 200
    assert len(artifacts.json()["items"]) == 1
    item = artifacts.json()["items"][0]
    assert item["type"] == "pdf"
    assert item["current_verification"] == "valid"
    assert item["metadata"]["sha256"] == completed.json()["result"]["artifact"]["sha256"]
    assert (e2e_environment["workspace"] / "Report.pdf").is_file()
    assert len(list_artifacts(task_id)) == 1

    events = client.get(f"/tasks/{task_id}/events")
    assert events.status_code == 200
    event_names = [event["event_name"] for event in events.json()]
    assert "tool.result_recorded" in event_names
    assert "artifact.verified" in event_names



def test_http_rejection_keeps_artifact_uncreated_and_task_failed(e2e_environment):
    client = e2e_environment["client"]
    conversation = e2e_environment["conversation"]
    workspace = e2e_environment["workspace"]

    started = client.post(
        "/tasks/start",
        json={
            "conversation_id": conversation.id,
            "goal": "Create a PDF report named Rejected.pdf",
            "type": "report",
        },
    )
    assert started.status_code == 202
    task_id = started.json()["id"]
    assert client.get(f"/tasks/{task_id}").json()["status"] == "awaiting_approval"
    call = next(
        call for call in list_tool_calls(conversation.id)
        if call.task_id == task_id and call.tool_name == "artifact"
    )

    rejected = client.post(
        f"/tasks/{task_id}/tool-calls/{call.id}/decision",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 202
    assert client.get(f"/tasks/{task_id}").json()["status"] == "failed"
    assert get_task(task_id).result["error"].startswith("A operação solicitada foi recusada")
    assert not (workspace / "Rejected.pdf").exists()
    assert client.get(f"/tasks/{task_id}/artifacts").json()["items"] == []
    assert any(
        event.event_name == "tool.rejected"
        for event in list_task_events(task_id)
    )


def test_http_cancel_preserves_authority_and_cancels_pending_approval(e2e_environment):
    client = e2e_environment["client"]
    conversation = e2e_environment["conversation"]
    workspace = e2e_environment["workspace"]

    started = client.post(
        "/tasks/start",
        json={
            "conversation_id": conversation.id,
            "goal": "Create a PDF report named Cancelled.pdf",
            "type": "report",
        },
    )
    assert started.status_code == 202
    task_id = started.json()["id"]
    assert client.get(f"/tasks/{task_id}").json()["status"] == "awaiting_approval"
    call = next(
        call for call in list_tool_calls(conversation.id)
        if call.task_id == task_id and call.tool_name == "artifact"
    )

    cancelled = client.post(f"/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/tasks/{task_id}").json()["status"] == "cancelled"
    assert get_tool_call(call.id).status == "cancelled"
    assert not (workspace / "Cancelled.pdf").exists()
    assert client.get(f"/tasks/{task_id}/artifacts").json()["items"] == []
    assert any(
        event.event_name == "tool.cancelled"
        for event in list_task_events(task_id)
    )
