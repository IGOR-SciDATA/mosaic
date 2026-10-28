import hashlib
from types import SimpleNamespace

import pytest

from app.services import hie_orchestrator as hie
from app.services.hie_candidate import build_candidate, canonical_json


def _snapshot():
    profile = {
        "slug": "hie-event-reviewer",
        "name": "HIE Event Reviewer",
        "description": "Event failure fixture",
        "instructions": "Use a deterministic marker.",
        "version": 1,
        "skills": [],
    }
    profile["sha256"] = hashlib.sha256(
        canonical_json(profile).encode("utf-8")
    ).hexdigest()
    return profile


def _setup(monkeypatch, failing_event):
    task = SimpleNamespace(id=91, conversation_id=9, project_id=5, status="executing")
    events = []

    def create_event(**kwargs):
        if kwargs["event_name"] == failing_event:
            raise OSError("synthetic event store failure")
        events.append(kwargs)

    monkeypatch.setattr(hie, "get_task", lambda _: task)
    monkeypatch.setattr(hie, "create_task_event", create_event)
    return events


def _run(snapshot, candidate, baseline, probe, **kwargs):
    return hie.run_candidate_experiment(
        91, snapshot, candidate,
        provider_identity={
            "provider": "test-double", "model": "deterministic", "revision": "r1"
        },
        baseline_runner=baseline,
        probe_runner=probe,
        verifier=lambda output: "PASS" in output,
        isolated_fixture=True,
        **kwargs,
    )


def _result(output):
    return {
        "provider_identity": {
            "provider": "test-double", "model": "deterministic", "revision": "r1"
        },
        "output": output,
    }


def test_abort_event_store_failure_does_not_mask_runner_failure(monkeypatch):
    events = _setup(monkeypatch, "hie.experiment.aborted")
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Use a deterministic marker.")

    with pytest.raises(hie.HIEExperimentError, match="aborted safely") as exc:
        _run(
            snapshot, candidate,
            lambda: _result("FAIL"),
            lambda _: (_ for _ in ()).throw(RuntimeError("runner broke")),
        )

    assert isinstance(exc.value.__cause__, RuntimeError)
    assert any(event["event_name"] == "hie.probe.started" for event in events)
    assert not any(event["event_name"] == "hie.experiment.completed" for event in events)


def test_cancellation_event_store_failure_preserves_cancellation(monkeypatch):
    _setup(monkeypatch, "hie.experiment.cancelled")
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Use a deterministic marker.")
    checks = iter([False, False, True])

    with pytest.raises(hie.HIEExperimentCancelled):
        _run(
            snapshot, candidate,
            lambda: _result("PASS"),
            lambda _: _result("PASS"),
            cancelled=lambda: next(checks, True),
        )


def test_start_event_store_failure_fails_closed_before_running_callbacks(monkeypatch):
    _setup(monkeypatch, "hie.experiment.started")
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Use a deterministic marker.")
    calls = []

    with pytest.raises(OSError, match="event store failure"):
        _run(
            snapshot, candidate,
            lambda: (calls.append("baseline") or _result("PASS")),
            lambda _: (calls.append("probe") or _result("PASS")),
        )

    assert calls == []
