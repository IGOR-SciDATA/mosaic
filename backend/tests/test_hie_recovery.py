import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection, init_db
from app.main import app
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.services.agent_library import create_project_agent
from app.services.hie_experiments import create_experiment, recover_interrupted_experiments


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "hie-recovery.db")
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_experiment(client):
    model = create_model("HIE Recovery Test", "ollama", "qwen3:3b")
    project = create_project("HIE Recovery Project", "/tmp/hie-recovery-project")
    create_project_agent(project.id, {
        "slug": "qa-agent",
        "name": "QA Agent",
        "description": "Recovery test profile",
        "instructions": "Answer concisely.",
        "skills": [],
    })
    conversation = create_conversation("HIE recovery", model.id, project_id=project.id)
    assert client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True}).status_code == 200
    return create_experiment(
        conversation_id=conversation.id,
        task_id=None,
        profile_slug="qa-agent",
        candidate_content="Answer with explicit detail.",
        fixtures=[{"prompt": "Explain.", "expected_contains": ["detail"]}],
    )


@pytest.mark.parametrize(
    ("previous_status", "expected_outcome"),
    [("queued", "not_started"), ("running", "unknown")],
)
def test_startup_recovery_marks_interrupted_experiment_without_replay(client, previous_status, expected_outcome):
    experiment = _create_experiment(client)
    with get_connection() as connection:
        connection.execute("UPDATE hie_experiments SET status = ? WHERE id = ?", (previous_status, experiment["id"]))
        connection.commit()

    recovered = recover_interrupted_experiments()
    assert experiment["id"] in recovered["recovered_queued" if previous_status == "queued" else "recovered_running"]
    result = client.get(f"/hie/experiments/{experiment['id']}").json()
    assert result["status"] == "failed"
    assert result["results"]["provider_outcome"] == expected_outcome
    assert result["results"]["automatic_retry"] is False
    assert result["results"]["automatic_promotion"] is False

    second = recover_interrupted_experiments()
    assert experiment["id"] not in second["recovered_queued"]
    assert experiment["id"] not in second["recovered_running"]


def test_concurrent_recovery_claims_interrupted_experiment_once(client):
    experiment = _create_experiment(client)
    with get_connection() as connection:
        connection.execute("UPDATE hie_experiments SET status = 'queued' WHERE id = ?", (experiment["id"],))
        connection.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: recover_interrupted_experiments(), range(2)))

    claimed = sum(len(item["recovered_queued"]) + len(item["recovered_running"]) for item in results)
    assert claimed == 1
    with get_connection() as connection:
        row = connection.execute("SELECT status, results FROM hie_experiments WHERE id = ?", (experiment["id"],)).fetchone()
    assert row["status"] == "failed"
    assert json.loads(row["results"])["automatic_retry"] is False
