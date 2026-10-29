import pytest
from fastapi.testclient import TestClient

from app.db.database import init_db
from app.main import app
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import get_task
from app.services.agent_library import create_project_agent, get_project_agent


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "hie-experiments.db")
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _scope():
    model = create_model("HIE Test", "ollama", "qwen3:3b")
    project = create_project("HIE Project", "/tmp/hie-project")
    create_project_agent(project.id, {
        "slug": "qa-agent",
        "name": "QA Agent",
        "description": "Test profile",
        "instructions": "Answer concisely.",
        "skills": [],
    })
    conversation = create_conversation("HIE experiment", model.id, project_id=project.id)
    return project, conversation


class FakeProvider:
    def generate(self, messages, model_name, configuration):
        instructions = messages[0]["content"].casefold()
        return "approved result" if "always include the word approved" in instructions else "baseline result"

    def stream(self, messages, model_name, configuration):
        yield self.generate(messages, model_name, configuration)


def test_experiment_runs_isolated_baseline_candidate_and_persists_evidence(client, monkeypatch):
    from app.services import hie_experiments

    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: FakeProvider())
    project, conversation = _scope()
    enabled = client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True})
    assert enabled.status_code == 200

    created = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "profile_slug": "qa-agent",
        "candidate_content": "Always include the word approved.",
        "fixtures": [{"prompt": "Return the test response.", "expected_contains": ["approved"]}],
    })
    assert created.status_code == 201, created.text
    experiment = created.json()
    assert experiment["status"] == "draft"
    assert experiment["candidate"]["sha256"]
    assert experiment["provider"] == "ollama"
    assert experiment["model_name"] == "qwen3:3b"
    assert experiment["budget"]["estimated_provider_calls"] == 2
    assert "candidate/profile-instructions" in experiment["candidate_diff"]

    run = client.post(f"/hie/experiments/{experiment['id']}/run")
    assert run.status_code == 202, run.text
    finished = client.get(f"/hie/experiments/{experiment['id']}")
    assert finished.status_code == 200
    result = finished.json()
    assert result["status"] == "completed"
    assert result["results"]["baseline_passed"] == 0
    assert result["results"]["candidate_passed"] == 1
    assert result["results"]["assessment"] == "candidate_better"
    assert result["results"]["automatic_promotion"] is False
    assert result["results"]["evidence"][0]["baseline"]["output"] == "baseline result"
    assert result["results"]["evidence"][0]["candidate"]["output"] == "approved result"
    active_profile = get_project_agent(project.id, "qa-agent")
    assert active_profile["instructions"] == "Answer concisely."
    assert active_profile["version"] == 1

    task = get_task(result["task_id"])
    assert task.status == "completed"
    events = list_task_events(task.id, limit=200)
    event_names = [event.event_name for event in events]
    assert "hie.experiment_created" in event_names
    assert "hie.experiment_started" in event_names
    assert "hie.fixture_evaluated" in event_names
    assert "hie.experiment_completed" in event_names


def test_experiment_requires_explicit_hie_opt_in(client):
    project, conversation = _scope()
    response = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "profile_slug": "qa-agent",
        "candidate_content": "New declarative instructions.",
        "fixtures": [{"prompt": "Check.", "expected_contains": ["yes"]}],
    })
    assert response.status_code == 409
    assert "explicitly enabled" in response.json()["detail"]


def test_experiment_rejects_unbounded_or_ambiguous_input(client):
    project, conversation = _scope()
    client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True})
    response = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "task_id": 1,
        "profile_slug": "qa-agent",
        "candidate_content": "Candidate.",
        "fixtures": [{"prompt": "Check.", "expected_contains": ["yes"]}],
    })
    assert response.status_code == 422
