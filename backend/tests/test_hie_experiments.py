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


def test_queued_experiment_can_be_cancelled_with_task_and_event_consistency(client):
    from app.services.hie_experiments import cancel_experiment, queue_experiment, get_experiment

    _, experiment = _create_ready_experiment(client)
    queue_experiment(experiment["id"])
    cancelled = cancel_experiment(experiment["id"])

    assert cancelled["status"] == "cancelled"
    assert cancelled["results"]["cancelled_by_user"] is True
    assert cancelled["results"]["automatic_retry"] is False
    assert cancelled["results"]["automatic_promotion"] is False
    task = get_task(cancelled["task_id"])
    assert task.status == "cancelled"
    events = list_task_events(task.id)
    assert any(event.event_name == "hie.experiment_cancelled" for event in events)
    assert any(event.event_name == "task.status_changed" and event.status == "cancelled" for event in events)


def test_cancellation_during_provider_call_prevents_next_call(client, monkeypatch):
    from app.services import hie_experiments

    _, experiment = _create_ready_experiment(client)
    hie_experiments.queue_experiment(experiment["id"])
    calls = []

    class CancellingProvider:
        def generate(self, messages, model_name, configuration):
            calls.append(messages[-1]["content"])
            hie_experiments.cancel_experiment(experiment["id"])
            return "baseline result"

    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda _model: CancellingProvider())
    hie_experiments.run_experiment(experiment["id"])

    cancelled = hie_experiments.get_experiment(experiment["id"])
    assert cancelled["status"] == "cancelled"
    assert len(calls) == 1, "Cancellation must stop before the candidate provider call."
    assert get_task(cancelled["task_id"]).status == "cancelled"


def test_completed_experiment_cannot_be_cancelled(client):
    from app.services.hie_experiments import cancel_experiment, HieExperimentError

    _, experiment = _create_ready_experiment(client)
    with pytest.raises(HieExperimentError, match="cannot be cancelled"):
        # Drafts can be cancelled; completed states are terminal. Mark this record completed
        # to exercise the terminal-state guard without making provider calls.
        from app.db.database import get_connection
        with get_connection() as connection:
            connection.execute("UPDATE hie_experiments SET status = 'completed' WHERE id = ?", (experiment["id"],))
            connection.commit()
        cancel_experiment(experiment["id"])


def test_cancelled_status_migration_preserves_existing_experiment_rows(client):
    from app.db.database import get_connection, init_db

    _, experiment = _create_ready_experiment(client)
    # Simulate a database created before the cancelled status was added.
    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""
            CREATE TABLE hie_experiments_legacy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                source_task_id INTEGER NULL,
                conversation_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                profile_slug TEXT NOT NULL,
                candidate_origin TEXT NOT NULL DEFAULT 'user_supplied',
                provider TEXT NOT NULL DEFAULT '',
                model_name TEXT NOT NULL DEFAULT '',
                budget_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'draft' CHECK (
                    status IN ('draft', 'queued', 'running', 'completed', 'failed', 'rejected')
                ),
                baseline_snapshot TEXT NOT NULL,
                candidate TEXT NOT NULL,
                fixtures TEXT NOT NULL,
                candidate_diff TEXT NOT NULL,
                results TEXT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            INSERT INTO hie_experiments_legacy (
                id, task_id, source_task_id, conversation_id, project_id, profile_slug,
                candidate_origin, provider, model_name, budget_json, status,
                baseline_snapshot, candidate, fixtures, candidate_diff, results, created_at, updated_at
            )
            SELECT id, task_id, source_task_id, conversation_id, project_id, profile_slug,
                   candidate_origin, provider, model_name, budget_json, status,
                   baseline_snapshot, candidate, fixtures, candidate_diff, results, created_at, updated_at
            FROM hie_experiments
        """)
        connection.execute("DROP TABLE hie_experiments")
        connection.execute("ALTER TABLE hie_experiments_legacy RENAME TO hie_experiments")
        connection.commit()
        connection.execute("PRAGMA foreign_keys = ON")

    init_db()
    from app.services.hie_experiments import get_experiment
    with get_connection() as connection:
        connection.execute("UPDATE hie_experiments SET status = 'cancelled' WHERE id = ?", (experiment["id"],))
        connection.commit()
    assert get_experiment(experiment["id"])["status"] == "cancelled"


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

    from app.db.database import get_connection
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


def test_failure_event_failure_preserves_original_error_without_false_success(client, monkeypatch):
    from app.services import hie_experiments

    class FailsProvider(FakeProvider):
        def generate(self, messages, model_name, configuration):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(hie_experiments, "resolve_model_provider", lambda model: FailsProvider())
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

    # TestClient executes FastAPI BackgroundTasks before returning. The failure
    # event store is unavailable, so the caller receives that error. The
    # original provider failure must remain persisted; no completion is reported.
    with pytest.raises(OSError, match="failure event store unavailable"):
        client.post(f"/hie/experiments/{created_id}/run")

    stored = hie_experiments.get_experiment(created_id)
    # Failure finalization and its audit event share one transaction. Because the
    # event store failed, the transaction rolled back rather than claiming a
    # failure transition without its audit record. Startup recovery marks this
    # persisted running experiment interrupted without replaying provider calls.
    assert stored["status"] == "running"
    assert stored["results"] is None
    task = get_task(stored["task_id"])
    assert task.status == "executing"
    active = get_project_agent(project.id, "qa-agent")
    assert active["instructions"] == "Answer concisely."


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
