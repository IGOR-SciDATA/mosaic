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
from app.models.tool_call_repository import get_tool_call, list_tool_calls
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
    conversation = create_conversation("PDF lifecycle", model.id, project_id=project.id)
    decisions = []

    def deterministic_decider(task_id):
        def decide(_context):
            decisions.append(task_id)
            return {
                "type": "final",
                "content": "# E2E Report\n\nThis report completed through the persisted API workflow.",
            }
        return decide

    def deterministic_worker(task_id):
        run_agent(task_id, deterministic_decider(task_id))

    monkeypatch.setattr("app.services.task_coordinator.create_provider_decider", deterministic_decider)
    monkeypatch.setattr("app.api.tasks._run_provider_agent", deterministic_worker)
    monkeypatch.setattr(
        "app.api.tasks.generate_coordinator_plan",
        lambda _conversation_id, goal: {
            "goal": goal,
            "subtasks": [{
                "id": "report",
                "goal": goal,
                "profile": "documentation",
                "depends_on": [],
                "inputs": [],
                "allowed_tools": ["artifact"],
                "acceptance_criteria": [{"type": "non_empty"}],
            }],
        },
    )
    with TestClient(app) as client:
        yield {
            "client": client,
            "workspace": workspace,
            "project": project,
            "conversation": conversation,
            "decisions": decisions,
        }


def _start_confirmed_task(environment, goal):
    client = environment["client"]
    conversation = environment["conversation"]
    started = client.post(
        "/tasks/start",
        json={"conversation_id": conversation.id, "goal": goal, "type": "report"},
    )
    assert started.status_code == 202, started.text
    parent_id = started.json()["id"]
    assert started.json()["status"] == "awaiting_approval"
    assert started.json()["plan"]["plan_confirmed"] is False
    assert not [call for call in list_tool_calls(conversation.id) if call.task_id == parent_id]

    confirmed = client.post(
        f"/tasks/{parent_id}/confirm",
        json={"plan_version": started.json()["plan"]["plan_version"]},
    )
    assert confirmed.status_code == 202, confirmed.text
    parent = client.get(f"/tasks/{parent_id}").json()
    assert parent["status"] == "awaiting_approval"
    child_id = parent["plan"]["coordinator"]["children"]["report"]
    return parent_id, child_id


def test_http_task_approval_artifact_and_event_replay_end_to_end(e2e_environment):
    client = e2e_environment["client"]
    conversation = e2e_environment["conversation"]
    decisions = e2e_environment["decisions"]
    parent_id, child_id = _start_confirmed_task(
        e2e_environment, "Create a PDF report named Report.pdf"
    )

    calls = [
        call for call in list_tool_calls(conversation.id)
        if call.task_id == child_id and call.tool_name == "artifact"
    ]
    assert len(calls) == 1
    assert calls[0].status == "pending"

    approval = client.post(
        f"/tasks/{child_id}/tool-calls/{calls[0].id}/decision",
        json={"decision": "approve"},
    )
    assert approval.status_code == 202

    completed_parent = client.get(f"/tasks/{parent_id}").json()
    completed = client.get(f"/tasks/{child_id}").json()
    assert completed_parent["status"] == "completed"
    assert completed["status"] == "completed"
    assert completed["result"]["artifact"]["path"] == "Report.pdf"
    assert completed["result"]["artifact"]["verification_event_recorded"] is True
    assert decisions == [child_id], "Approved artifact completion must not call the model again."

    artifacts = client.get(f"/tasks/{child_id}/artifacts")
    assert artifacts.status_code == 200
    assert len(artifacts.json()["items"]) == 1
    item = artifacts.json()["items"][0]
    assert item["type"] == "pdf"
    assert item["current_verification"] == "valid"
    assert item["metadata"]["sha256"] == completed["result"]["artifact"]["sha256"]
    assert (e2e_environment["workspace"] / "Report.pdf").is_file()
    assert len(list_artifacts(child_id)) == 1

    events = client.get(f"/tasks/{child_id}/events")
    assert events.status_code == 200
    event_names = [event["event_name"] for event in events.json()]
    assert "tool.result_recorded" in event_names
    assert "artifact.verified" in event_names


def test_http_rejection_keeps_artifact_uncreated_and_task_failed(e2e_environment):
    client = e2e_environment["client"]
    conversation = e2e_environment["conversation"]
    workspace = e2e_environment["workspace"]
    parent_id, child_id = _start_confirmed_task(
        e2e_environment, "Create a PDF report named Rejected.pdf"
    )
    call = next(
        call for call in list_tool_calls(conversation.id)
        if call.task_id == child_id and call.tool_name == "artifact"
    )

    rejected = client.post(
        f"/tasks/{child_id}/tool-calls/{call.id}/decision",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 202
    assert client.get(f"/tasks/{child_id}").json()["status"] == "failed"
    assert client.get(f"/tasks/{parent_id}").json()["status"] == "failed"
    assert get_task(child_id).result["error"].startswith("A operação solicitada foi recusada")
    assert not (workspace / "Rejected.pdf").exists()
    assert client.get(f"/tasks/{child_id}/artifacts").json()["items"] == []
    assert any(event.event_name == "tool.rejected" for event in list_task_events(child_id))


def test_http_cancel_preserves_authority_and_cancels_pending_approval(e2e_environment):
    client = e2e_environment["client"]
    conversation = e2e_environment["conversation"]
    workspace = e2e_environment["workspace"]
    parent_id, child_id = _start_confirmed_task(
        e2e_environment, "Create a PDF report named Cancelled.pdf"
    )
    call = next(
        call for call in list_tool_calls(conversation.id)
        if call.task_id == child_id and call.tool_name == "artifact"
    )

    cancelled = client.post(f"/tasks/{parent_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/tasks/{parent_id}").json()["status"] == "cancelled"
    assert client.get(f"/tasks/{child_id}").json()["status"] == "cancelled"
    assert get_tool_call(call.id).status == "cancelled"
    assert not (workspace / "Cancelled.pdf").exists()
    assert client.get(f"/tasks/{child_id}/artifacts").json()["items"] == []
    assert any(event.event_name == "tool.cancelled" for event in list_task_events(child_id))
