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


def _create_ready_experiment(client):
    from app.services import hie_experiments

    project, conversation = _scope()
    enabled = client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True})
    assert enabled.status_code == 200
    experiment = hie_experiments.create_experiment(
        conversation_id=conversation.id,
        task_id=None,
        profile_slug="qa-agent",
        candidate_content="Answer with clear detail.",
        fixtures=[{"prompt": "Explain.", "expected_contains": ["detail"]}],
    )
    return project, experiment


def test_queue_event_failure_rolls_back_queued_state(client, monkeypatch):
    from app.services import hie_experiments

    _, experiment = _create_ready_experiment(client)
    original_emit = hie_experiments._emit

    def fail_queue_event(experiment, event_name, message, status, metadata=None, connection=None):
        if event_name == "hie.experiment_queued":
            raise OSError("queue event persistence failed")
        return original_emit(experiment, event_name, message, status, metadata, connection)

    monkeypatch.setattr(hie_experiments, "_emit", fail_queue_event)
    with pytest.raises(OSError, match="queue event persistence failed"):
        hie_experiments.queue_experiment(experiment["id"])

    stored = hie_experiments.get_experiment(experiment["id"])
    assert stored["status"] == "draft"


def test_rejection_event_failure_rolls_back_rejection_state(client, monkeypatch):
    from app.services import hie_experiments

    _, experiment = _create_ready_experiment(client)
    original_emit = hie_experiments._emit

    def fail_rejection_event(experiment, event_name, message, status, metadata=None, connection=None):
        if event_name == "hie.experiment_rejected":
            raise OSError("rejection event persistence failed")
        return original_emit(experiment, event_name, message, status, metadata, connection)

    monkeypatch.setattr(hie_experiments, "_emit", fail_rejection_event)
    with pytest.raises(OSError, match="rejection event persistence failed"):
        hie_experiments.reject_experiment(experiment["id"])

    stored = hie_experiments.get_experiment(experiment["id"])
    assert stored["status"] == "draft"


def test_creation_event_failure_rolls_back_experiment_and_marks_task_failed(client, monkeypatch):
    from app.services import hie_experiments

    _, conversation = _scope()
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    original_emit = hie_experiments._emit

    def fail_created_event(experiment, event_name, message, status, metadata=None, connection=None):
        if event_name == "hie.experiment_created":
            raise OSError("creation event persistence failed")
        return original_emit(experiment, event_name, message, status, metadata, connection)

    monkeypatch.setattr(hie_experiments, "_emit", fail_created_event)
    with pytest.raises(hie_experiments.HieExperimentError, match="could not be persisted safely"):
        hie_experiments.create_experiment(
            conversation_id=conversation.id,
            task_id=None,
            profile_slug="qa-agent",
            candidate_content="Answer with clear detail.",
            fixtures=[{"prompt": "Explain.", "expected_contains": ["detail"]}],
        )

    with get_connection() as connection:
        rows = connection.execute("SELECT id FROM hie_experiments").fetchall()
    assert rows == []


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
    assert experiment["candidate_origin"] == "user_supplied"
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
    assert result["results"]["provider_calls"] == 2
    assert result["results"]["duration_ms"] >= 0
    assert result["results"]["execution_mode"] == "isolated_prompt_probe_no_tools"
    assert result["results"]["automatic_promotion"] is False
    assert result["results"]["evidence"][0]["baseline"]["output_preview"] == "baseline result"
    assert result["results"]["evidence"][0]["candidate"]["output_preview"] == "approved result"
    assert result["results"]["evidence"][0]["artifact_evidence"]["baseline_output"]["artifact_id"]
    assert result["results"]["evidence"][0]["artifact_evidence"]["candidate_output"]["sha256"]
    assert "path" not in result["results"]["evidence"][0]["artifact_evidence"]["candidate_output"]
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


def _create_ready_experiment(client):
    from app.services import hie_experiments
    from app.models.conversation_repository import create_conversation
    from app.models.project_repository import create_project
    from app.models.repository import create_model
    from app.services.agent_library import create_project_agent

    model = create_model("HIE Event Failure Model", "ollama", "qwen3:3b")
    project = create_project("HIE Event Failure Project", "/tmp/hie-event-failure-project")
    create_project_agent(project.id, {
        "slug": "qa-agent",
        "name": "QA Agent",
        "description": "Event failure fixture",
        "instructions": "Answer concisely.",
        "skills": [],
    })
    conversation = create_conversation("HIE Event Failure", model.id, project_id=project.id)
    client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True})
    experiment = hie_experiments.create_experiment(
        conversation_id=conversation.id, task_id=None, profile_slug="qa-agent",
        candidate_content="Answer with clear detail.",
        fixtures=[{"prompt": "Explain.", "expected_contains": ["detail"]}],
    )
    return project, experiment


def test_queue_event_failure_rolls_back_queued_state(client, monkeypatch):
    from app.services import hie_experiments

    _, experiment = _create_ready_experiment(client)
    original_emit = hie_experiments._emit

    def fail_queue_event(experiment, event_name, message, status, metadata=None, connection=None):
        if event_name == "hie.experiment_queued":
            raise OSError("queue event persistence failed")
        return original_emit(experiment, event_name, message, status, metadata, connection)

    monkeypatch.setattr(hie_experiments, "_emit", fail_queue_event)
    with pytest.raises(OSError, match="queue event persistence failed"):
        hie_experiments.queue_experiment(experiment["id"])

    stored = hie_experiments.get_experiment(experiment["id"])
    assert stored["status"] == "draft"


def test_rejection_event_failure_rolls_back_rejection_state(client, monkeypatch):
    from app.services import hie_experiments

    _, experiment = _create_ready_experiment(client)
    original_emit = hie_experiments._emit

    def fail_rejection_event(experiment, event_name, message, status, metadata=None, connection=None):
        if event_name == "hie.experiment_rejected":
            raise OSError("rejection event persistence failed")
        return original_emit(experiment, event_name, message, status, metadata, connection)

    monkeypatch.setattr(hie_experiments, "_emit", fail_rejection_event)
    with pytest.raises(OSError, match="rejection event persistence failed"):
        hie_experiments.reject_experiment(experiment["id"])

    stored = hie_experiments.get_experiment(experiment["id"])
    assert stored["status"] == "draft"


def test_input_budget_blocks_provider_call_before_generation(client, monkeypatch):
    from app.services import hie_experiments

    calls = []
    class RecordingProvider(FakeProvider):
        def generate(self, messages, model_name, configuration):
            calls.append((messages, configuration))
            return super().generate(messages, model_name, configuration)

    provider = RecordingProvider()
    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: provider)
    monkeypatch.setattr(hie_experiments, "MAX_INPUT_CHARS_PER_CALL", 1)
    project, conversation = _scope()
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    created = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "profile_slug": "qa-agent",
        "candidate_content": "Always include the word approved.",
        "fixtures": [{"prompt": "Return the test response.", "expected_contains": ["approved"]}],
    })
    assert created.status_code == 201
    run = client.post(f"/hie/experiments/{created.json()['id']}/run")
    assert run.status_code == 202
    failed = client.get(f"/hie/experiments/{created.json()['id']}").json()
    assert failed["status"] == "failed"
    assert "Input budget exceeded before provider call" in failed["results"]["error"]
    assert calls == []


def test_provider_receives_output_token_and_timeout_caps(client, monkeypatch):
    from app.services import hie_experiments

    configurations = []
    class RecordingProvider(FakeProvider):
        def generate(self, messages, model_name, configuration):
            configurations.append(dict(configuration))
            return super().generate(messages, model_name, configuration)

    provider = RecordingProvider()
    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: provider)
    project, conversation = _scope()
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    created = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "profile_slug": "qa-agent",
        "candidate_content": "Always include the word approved.",
        "fixtures": [{"prompt": "Return the test response.", "expected_contains": ["approved"]}],
    })
    assert created.status_code == 201
    run = client.post(f"/hie/experiments/{created.json()['id']}/run")
    assert run.status_code == 202
    finished = client.get(f"/hie/experiments/{created.json()['id']}").json()
    assert finished["status"] == "completed"
    assert len(configurations) == 2
    assert all(config["num_predict"] <= hie_experiments.MAX_OUTPUT_TOKENS for config in configurations)
    assert all(config["request_timeout_seconds"] <= hie_experiments.PROVIDER_TIMEOUT_SECONDS for config in configurations)


def test_excessive_provider_output_fails_without_truncating_and_persisting_it(client, monkeypatch):
    from app.services import hie_experiments

    class ExcessiveProvider(FakeProvider):
        def generate(self, messages, model_name, configuration):
            return "x" * (hie_experiments.MAX_OUTPUT_CHARS + 1)

    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: ExcessiveProvider())
    project, conversation = _scope()
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    created = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "profile_slug": "qa-agent",
        "candidate_content": "Always include the word approved.",
        "fixtures": [{"prompt": "Return the test response.", "expected_contains": ["approved"]}],
    })
    assert created.status_code == 201
    run = client.post(f"/hie/experiments/{created.json()['id']}/run")
    assert run.status_code == 202
    failed = client.get(f"/hie/experiments/{created.json()['id']}").json()
    assert failed["status"] == "failed"
    assert "output" in failed["results"]["error"].lower()
    assert "evidence" not in failed["results"]


def test_failure_event_failure_rolls_back_hie_and_task_status(client, monkeypatch):
    from app.services import hie_experiments

    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: FakeProvider())
    original_emit = hie_experiments._emit

    def fail_failure_event(experiment, event_name, message, status, metadata=None, connection=None):
        if event_name == "hie.experiment_failed":
            raise OSError("failure event store unavailable")
        return original_emit(experiment, event_name, message, status, metadata, connection)

    monkeypatch.setattr(hie_experiments, "_emit", fail_failure_event)
    project, conversation = _scope()
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    created = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "profile_slug": "qa-agent",
        "candidate_content": "Always include the word approved.",
        "fixtures": [{"prompt": "Return the test response.", "expected_contains": ["approved"]}],
    })
    assert created.status_code == 201
    created_id = created.json()["id"]

    # Force a provider error after the experiment has been created and queued.
    class FailsProvider(FakeProvider):
        def generate(self, messages, model_name, configuration):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: FailsProvider())
    # A failed audit write must roll back status and Task finalization, leaving a
    # recoverable running state rather than falsely declaring the failure audited.
    with pytest.raises(OSError, match="failure event store unavailable"):
        hie_experiments.queue_experiment(created_id)
        hie_experiments.run_experiment(created_id)

    stored = hie_experiments.get_experiment(created_id)
    assert stored["status"] == "queued"
    task = get_task(stored["task_id"])
    assert task.status == "pending"


def test_completion_event_failure_does_not_report_success(client, monkeypatch):
    from app.services import hie_experiments

    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: FakeProvider())
    original_emit = hie_experiments._emit
    def fail_completion_event(experiment, event_name, message, status, metadata=None, connection=None):
        if event_name == "hie.experiment_completed":
            raise RuntimeError("completion event store unavailable")
        return original_emit(experiment, event_name, message, status, metadata, connection)

    monkeypatch.setattr(hie_experiments, "_emit", fail_completion_event)
    project, conversation = _scope()
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    created = client.post("/hie/experiments", json={
        "conversation_id": conversation.id,
        "profile_slug": "qa-agent",
        "candidate_content": "Always include the word approved.",
        "fixtures": [{"prompt": "Return the test response.", "expected_contains": ["approved"]}],
    })
    assert created.status_code == 201
    assert client.post(f"/hie/experiments/{created.json()['id']}/run").status_code == 202
    failed = client.get(f"/hie/experiments/{created.json()['id']}").json()
    assert failed["status"] == "failed"
    assert failed["results"]["automatic_promotion"] is False
    task = get_task(failed["task_id"])
    assert task.status == "failed"
    active = get_project_agent(project.id, "qa-agent")
    assert active["instructions"] == "Answer concisely."
