import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection, init_db
from app.main import app
from app.api.tasks import _inherit_conversation_hie_mode
from app.models.conversation_repository import create_conversation
from app.models.repository import create_model
from app.models.project_repository import create_project
from app.services.agent_library import create_project_agent
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "hie.db")
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _conversation():
    model = create_model("HIE Test", "ollama", "qwen3:3b")
    project = create_project("HIE Project", "/tmp/hie-project")
    create_project_agent(project.id, {
        "slug": "qa-agent",
        "name": "QA Agent",
        "description": "Test profile",
        "instructions": "Answer concisely.",
        "skills": [],
    })
    return create_conversation("HIE scope", model.id, project_id=project.id)


def test_conversation_hie_is_disabled_by_default_and_persisted(client):
    conversation = _conversation()
    status = client.get(f"/hie/status?conversation_id={conversation.id}")
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert status.json()["default_enabled"] is False
    assert status.json()["experiment_execution_available"] is True

    enabled = client.put("/hie/status", json={
        "conversation_id": conversation.id, "enabled": True,
    })
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True

    reread = client.get(f"/hie/status?conversation_id={conversation.id}")
    assert reread.json()["enabled"] is True
    assert reread.json()["unavailable_capabilities"] == []
    supported = set(reread.json()["supported_capabilities"])
    assert {"persisted_opt_in", "isolated_baseline_candidate_probes", "version_bound_approval", "versioned_promotion", "rollback"} <= supported
    assert supported.isdisjoint(set(reread.json()["unavailable_capabilities"]))


def test_conversation_opt_in_is_inherited_by_new_task(client):
    conversation = _conversation()
    enabled = client.put("/hie/status", json={
        "conversation_id": conversation.id, "enabled": True,
    })
    assert enabled.status_code == 200
    task = create_task(
        type="generic", mode="agent", conversation_id=conversation.id,
        plan={"goal": "Inherited HIE mode"},
    )

    _inherit_conversation_hie_mode(task)

    status = client.get(f"/hie/status?task_id={task.id}")
    assert status.status_code == 200
    assert status.json()["enabled"] is True
    events = list_task_events(task.id)
    assert events[-1].event_name == "hie.mode_inherited"
    assert events[-1].metadata["source"] == "conversation"



def test_task_hie_activation_is_linked_to_task_events(client):
    conversation = _conversation()
    task = create_task(
        type="generic", mode="agent", conversation_id=conversation.id,
        plan={"goal": "Test HIE link"},
    )
    response = client.put("/hie/status", json={"task_id": task.id, "enabled": True})
    assert response.status_code == 200
    assert response.json()["scope"] == "task"
    assert response.json()["enabled"] is True

    events = list_task_events(task.id)
    assert events[-1].component == "hie"
    assert events[-1].event_name == "hie.mode_enabled"
    assert events[-1].metadata["experiment_execution_available"] is True


@pytest.mark.parametrize("payload", [
    {"enabled": True},
    {"conversation_id": 1, "task_id": 1, "enabled": True},
    {"conversation_id": 1, "enabled": True, "extra": "forbidden"},
])
def test_hie_update_rejects_ambiguous_or_extra_scope(payload, client):
    response = client.put("/hie/status", json=payload)
    assert response.status_code == 422


def test_hie_status_rejects_missing_scope(client):
    response = client.get("/hie/status")
    assert response.status_code == 422


def test_experiment_capability_is_unavailable_without_project_profile(client):
    model = create_model("No Project HIE Test", "ollama", "qwen3:3b")
    conversation = create_conversation("No project", model.id)
    status = client.get(f"/hie/status?conversation_id={conversation.id}")
    assert status.status_code == 200
    assert status.json()["available"] is True
    assert status.json()["experiment_execution_available"] is False
    unavailable = set(status.json()["unavailable_capabilities"])
    assert "project_scoped_agent_profile_required" in unavailable
    assert {"isolated_baseline_candidate_probes", "version_bound_approval", "versioned_promotion", "rollback"} <= unavailable
    assert set(status.json()["supported_capabilities"]).isdisjoint(unavailable)


def test_task_without_project_keeps_normal_scope_and_hie_experiment_unavailable(client):
    model = create_model("Standalone Task Model", "ollama", "qwen3:3b")
    conversation = create_conversation("Standalone Task conversation", model.id)
    task = create_task(type="generic", mode="agent", conversation_id=conversation.id, plan={"goal": "standalone"})
    status = client.get(f"/hie/status?task_id={task.id}")
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert status.json()["experiment_execution_available"] is False
    assert "project_scoped_agent_profile_required" in status.json()["unavailable_capabilities"]


def test_explicit_task_opt_out_overrides_conversation_opt_in(client):
    conversation = _conversation()
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    task = create_task(type="generic", mode="agent", conversation_id=conversation.id, plan={"goal": "explicit opt-out"})
    assert client.put("/hie/status", json={"task_id": task.id, "enabled": False}).status_code == 200

    _inherit_conversation_hie_mode(task)

    status = client.get(f"/hie/status?task_id={task.id}")
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    with get_connection() as connection:
        row = connection.execute("SELECT enabled FROM hie_sessions WHERE task_id = ?", (task.id,)).fetchone()
    assert row["enabled"] == 0


def test_experiment_capability_is_unavailable_for_provider_without_enforced_budget_controls(client):
    model = create_model("Unsupported HIE Provider", "openai", "gpt-test")
    project = create_project("Unsupported HIE Project", "/tmp/unsupported-hie-project")
    create_project_agent(project.id, {
        "slug": "qa-agent",
        "name": "QA Agent",
        "description": "Test profile",
        "instructions": "Answer concisely.",
        "skills": [],
    })
    conversation = create_conversation("Unsupported provider", model.id, project_id=project.id)
    status = client.get(f"/hie/status?conversation_id={conversation.id}")
    assert status.status_code == 200
    assert status.json()["experiment_execution_available"] is False
    assert "provider_budget_controls_required" in status.json()["unavailable_capabilities"]
    assert set(status.json()["supported_capabilities"]).isdisjoint(status.json()["unavailable_capabilities"])
