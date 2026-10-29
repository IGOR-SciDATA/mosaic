import json

import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection, init_db
from app.main import app
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.services.agent_library import create_project_agent, get_project_agent
from app.services.hie_experiments import create_experiment


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "hie-lifecycle.db")
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _completed_experiment(client):
    model = create_model("HIE Lifecycle Test", "ollama", "qwen3:3b")
    project = create_project("HIE Lifecycle Project", "/tmp/hie-lifecycle-project")
    create_project_agent(project.id, {
        "slug": "qa-agent",
        "name": "QA Agent",
        "description": "Lifecycle test profile",
        "instructions": "Answer concisely.",
        "skills": [],
    })
    conversation = create_conversation("HIE lifecycle", model.id, project_id=project.id)
    enabled = client.put("/hie/status", json={"conversation_id": conversation.id, "enabled": True})
    assert enabled.status_code == 200
    experiment = create_experiment(
        conversation_id=conversation.id,
        task_id=None,
        profile_slug="qa-agent",
        candidate_content="Answer with careful, verifiable detail.",
        fixtures=[{"prompt": "Explain.", "expected_contains": ["detail"]}],
    )
    with get_connection() as connection:
        connection.execute(
            "UPDATE hie_experiments SET status='completed', results=? WHERE id=?",
            (json.dumps({"assessment": "candidate_better", "automatic_promotion": False}), experiment["id"]),
        )
        connection.commit()
    return project, experiment


def _approval_payload(experiment, profile):
    return {
        "candidate_sha256": experiment["candidate"]["sha256"],
        "active_version": profile["version"],
        "active_sha256": profile["sha256"],
    }


def test_promotion_requires_explicit_version_bound_approval_and_rollback_restores_content(client):
    project, experiment = _completed_experiment(client)
    profile = get_project_agent(project.id, "qa-agent")
    payload = _approval_payload(experiment, profile)

    no_approval = client.post(f"/hie/experiments/{experiment['id']}/promote", json=payload)
    assert no_approval.status_code == 409

    approved = client.post(f"/hie/experiments/{experiment['id']}/approve", json=payload)
    assert approved.status_code == 200
    promoted = client.post(f"/hie/experiments/{experiment['id']}/promote", json=payload)
    assert promoted.status_code == 200
    assert promoted.json()["profile"]["instructions"] == experiment["candidate"]["content"]
    assert promoted.json()["profile"]["version"] == profile["version"] + 1

    active = get_project_agent(project.id, "qa-agent")
    rollback = client.post(f"/hie/promotions/{promoted.json()['promotion_id']}/rollback", json={
        "expected_active_version": active["version"],
        "expected_active_sha256": active["sha256"],
    })
    assert rollback.status_code == 200
    assert rollback.json()["profile"]["instructions"] == profile["instructions"]
    assert rollback.json()["profile"]["version"] == active["version"] + 1


def test_approval_rejects_candidate_hash_or_active_profile_version_mismatch(client):
    project, experiment = _completed_experiment(client)
    profile = get_project_agent(project.id, "qa-agent")
    payload = _approval_payload(experiment, profile)

    wrong_candidate = dict(payload, candidate_sha256="0" * 64)
    response = client.post(f"/hie/experiments/{experiment['id']}/approve", json=wrong_candidate)
    assert response.status_code == 409

    # Mutate through the canonical agent library service, then verify the approval snapshot is stale.
    from app.services.agent_library import update_project_agent
    update_project_agent(project.id, "qa-agent", {"instructions": "Profile changed after experiment."})
    stale = client.post(f"/hie/experiments/{experiment['id']}/approve", json=payload)
    assert stale.status_code == 409


def test_rollback_refuses_to_overwrite_profile_changed_after_promotion(client):
    project, experiment = _completed_experiment(client)
    profile = get_project_agent(project.id, "qa-agent")
    payload = _approval_payload(experiment, profile)
    assert client.post(f"/hie/experiments/{experiment['id']}/approve", json=payload).status_code == 200
    promoted = client.post(f"/hie/experiments/{experiment['id']}/promote", json=payload)
    assert promoted.status_code == 200

    from app.services.agent_library import update_project_agent
    update_project_agent(project.id, "qa-agent", {"instructions": "Newer human edit."})
    active = get_project_agent(project.id, "qa-agent")
    response = client.post(f"/hie/promotions/{promoted.json()['promotion_id']}/rollback", json={
        "expected_active_version": active["version"],
        "expected_active_sha256": active["sha256"],
    })
    assert response.status_code == 409


def test_two_concurrent_promotions_cannot_apply_the_same_approval(client):
    from concurrent.futures import ThreadPoolExecutor
    from app.services.hie_lifecycle import HieLifecycleError, promote_candidate, approve_candidate

    project, experiment = _completed_experiment(client)
    profile = get_project_agent(project.id, "qa-agent")
    payload = _approval_payload(experiment, profile)
    approve_candidate(experiment["id"], **payload)

    def attempt():
        try:
            return promote_candidate(experiment["id"], **payload)
        except HieLifecycleError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(item is not None for item in outcomes) == 1
    active = get_project_agent(project.id, "qa-agent")
    assert active["version"] == profile["version"] + 1
    with get_connection() as connection:
        rows = connection.execute("SELECT id FROM hie_promotions WHERE experiment_id = ?", (experiment["id"],)).fetchall()
    assert len(rows) == 1


def test_concurrent_rollback_is_idempotently_rejected_after_first_commit(client):
    from concurrent.futures import ThreadPoolExecutor
    from app.services.hie_lifecycle import HieLifecycleError, approve_candidate, promote_candidate, rollback_promotion

    project, experiment = _completed_experiment(client)
    profile = get_project_agent(project.id, "qa-agent")
    payload = _approval_payload(experiment, profile)
    approve_candidate(experiment["id"], **payload)
    promoted = promote_candidate(experiment["id"], **payload)
    active = get_project_agent(project.id, "qa-agent")

    def attempt():
        try:
            return rollback_promotion(promoted["promotion_id"], expected_active_version=active["version"], expected_active_sha256=active["sha256"])
        except HieLifecycleError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(item is not None for item in outcomes) == 1
    restored = get_project_agent(project.id, "qa-agent")
    assert restored["instructions"] == profile["instructions"]
    assert restored["version"] == active["version"] + 1


def test_event_failure_rolls_back_profile_and_promotion_record(client, monkeypatch):
    from app.services import hie_lifecycle

    project, experiment = _completed_experiment(client)
    profile = get_project_agent(project.id, "qa-agent")
    payload = _approval_payload(experiment, profile)
    assert client.post(f"/hie/experiments/{experiment['id']}/approve", json=payload).status_code == 200

    def fail_event(*args, **kwargs):
        raise RuntimeError("simulated event persistence failure")

    monkeypatch.setattr(hie_lifecycle, "_event", fail_event)
    with pytest.raises(RuntimeError, match="simulated event persistence failure"):
        hie_lifecycle.promote_candidate(experiment["id"], **payload)

    active = get_project_agent(project.id, "qa-agent")
    assert active["version"] == profile["version"]
    assert active["instructions"] == profile["instructions"]
    with get_connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM hie_promotions WHERE experiment_id = ?", (experiment["id"],)).fetchone()[0]
    assert count == 0
