import hashlib

from app.services import hie_orchestrator as hie
from app.services.hie_candidate import build_candidate, canonical_json
from app.services.hie_fixture_adapter import run_disposable_fixture_experiment


def _snapshot():
    profile = {
        "slug": "integration-reviewer",
        "name": "Integration Reviewer",
        "description": "Fixture adapter integration test",
        "instructions": "Check for required marker.",
        "version": 1,
        "skills": [],
    }
    payload = {key: profile[key] for key in (
        "slug", "name", "description", "instructions", "version", "skills"
    )}
    profile["sha256"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return profile


def test_real_orchestrator_compares_independent_fixtures_without_promoting(
    tmp_path, monkeypatch
):
    source = tmp_path / "fixture"
    source.mkdir()
    original = source / "brief.md"
    original.write_text("baseline has no marker\n", encoding="utf-8")

    task = type(
        "TaskStub", (),
        {"id": 42, "conversation_id": 7, "project_id": 3, "status": "executing"},
    )()
    events = []
    monkeypatch.setattr(hie, "get_task", lambda task_id: task if task_id == 42 else None)
    monkeypatch.setattr(hie, "create_task_event", lambda **kwargs: events.append(kwargs))
    # This integration test covers disposable-fixture isolation and comparison flow.
    monkeypatch.setattr(hie, "persist_output_evidence", lambda *args, **kwargs: {"baseline": {}, "candidate": {}})
    monkeypatch.setattr(hie, "persist_record_evidence", lambda *args, **kwargs: None)

    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Required marker: MOSAIC-HIE-CANDIDATE")
    roots = {}

    def baseline_factory(root):
        roots["baseline"] = root

        def run_baseline():
            return {
                "provider_identity": {
                    "provider": "test-double", "model": "deterministic", "revision": "v1"
                },
                "output": (root / "brief.md").read_text(encoding="utf-8"),
            }

        return run_baseline

    def probe_factory(root):
        roots["candidate"] = root

        def run_candidate(proposal):
            # This mutates only the candidate's temporary copy.
            (root / "brief.md").write_text(proposal["content"], encoding="utf-8")
            return {
                "provider_identity": {
                    "provider": "test-double", "model": "deterministic", "revision": "v1"
                },
                "output": (root / "brief.md").read_text(encoding="utf-8"),
            }

        return run_candidate

    record = run_disposable_fixture_experiment(
        source,
        baseline_runner_factory=baseline_factory,
        probe_runner_factory=probe_factory,
        task_id=42,
        baseline_snapshot=snapshot,
        candidate=candidate,
        provider_identity={
            "provider": "test-double", "model": "deterministic", "revision": "v1"
        },
        verifier=lambda output: "MOSAIC-HIE-CANDIDATE" in output,
    )

    assert record["outcome"] == "candidate_passed_baseline_failed"
    assert record["promotion"] == "not_performed"
    assert record["usage"]["provider_calls"] == 2
    assert roots["baseline"] != roots["candidate"]
    assert not roots["baseline"].exists()
    assert not roots["candidate"].exists()
    assert original.read_text(encoding="utf-8") == "baseline has no marker\n"
    assert [event["event_name"] for event in events] == [
        "hie.experiment.started",
        "hie.baseline.started",
        "hie.baseline.completed",
        "hie.probe.started",
        "hie.probe.completed",
        "hie.experiment.completed",
    ]
