import hashlib
from types import SimpleNamespace

from app.services import hie_orchestrator as hie
from app.services.hie_candidate import build_candidate, canonical_json


def _snapshot():
    profile = {
        "slug": "hie-record-reviewer",
        "name": "HIE Record Reviewer",
        "description": "Sealed record fixture",
        "instructions": "Require the marker.",
        "version": 3,
        "skills": [],
    }
    profile["sha256"] = hashlib.sha256(
        canonical_json(profile).encode("utf-8")
    ).hexdigest()
    return profile


def test_experiment_record_binds_snapshot_and_has_verifiable_digest(monkeypatch):
    task = SimpleNamespace(id=123, conversation_id=12, project_id=6, status="executing")
    events = []
    monkeypatch.setattr(hie, "get_task", lambda _: task)
    monkeypatch.setattr(hie, "create_task_event", lambda **kwargs: events.append(kwargs))
    # Keep this integrity test focused on the sealed record; storage has dedicated tests.
    monkeypatch.setattr(hie, "persist_output_evidence", lambda *args, **kwargs: {"baseline": {}, "candidate": {}})
    monkeypatch.setattr(hie, "persist_record_evidence", lambda *args, **kwargs: None)

    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Require the marker.")

    def result(output):
        return {
            "provider_identity": {
                "provider": "test-double",
                "model": "deterministic",
                "revision": "r1",
            },
            "output": output,
        }

    record = hie.run_candidate_experiment(
        123,
        snapshot,
        candidate,
        provider_identity={
            "provider": "test-double",
            "model": "deterministic",
            "revision": "r1",
        },
        baseline_runner=lambda: result("marker missing"),
        probe_runner=lambda _: result("marker present"),
        verifier=lambda output: "marker present" in output,
        isolated_fixture=True,
    )

    assert record["baseline_profile"] == {
        "slug": snapshot["slug"],
        "version": snapshot["version"],
        "sha256": snapshot["sha256"],
    }
    digest = record["record_sha256"]
    unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
    expected = hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    assert digest == expected
    assert record["candidate_sha256"] == candidate["sha256"]
    assert record["promotion"] == "not_performed"
    completed = next(event for event in events if event["event_name"] == "hie.experiment.completed")
    assert completed["metadata"]["record_sha256"] == digest
