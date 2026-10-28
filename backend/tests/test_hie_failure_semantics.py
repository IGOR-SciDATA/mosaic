import hashlib
from types import SimpleNamespace

import pytest

from app.services import hie_orchestrator as hie
from app.services.hie_candidate import build_candidate, canonical_json


def _snapshot():
    profile = {
        "slug": "hie-failure-reviewer",
        "name": "HIE Failure Reviewer",
        "description": "Failure semantics fixture",
        "instructions": "Check for a stable marker.",
        "version": 1,
        "skills": [],
    }
    profile["sha256"] = hashlib.sha256(
        canonical_json(profile).encode("utf-8")
    ).hexdigest()
    return profile


def _setup(monkeypatch, status="executing"):
    task = SimpleNamespace(id=77, conversation_id=8, project_id=4, status=status)
    events = []
    monkeypatch.setattr(hie, "get_task", lambda task_id: task if task_id == 77 else None)
    monkeypatch.setattr(hie, "create_task_event", lambda **kwargs: events.append(kwargs))
    return events


def _result(output):
    return {
        "provider_identity": {
            "provider": "test-double", "model": "deterministic", "revision": "r1"
        },
        "output": output,
    }


def _run(events, snapshot, candidate, baseline, probe, verifier=lambda text: "PASS" in text, **kwargs):
    return hie.run_candidate_experiment(
        77, snapshot, candidate,
        provider_identity={
            "provider": "test-double", "model": "deterministic", "revision": "r1"
        },
        baseline_runner=baseline,
        probe_runner=probe,
        verifier=verifier,
        isolated_fixture=True,
        **kwargs,
    )


def test_probe_exception_aborts_and_never_promotes(monkeypatch):
    events = _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Check for a stable marker.")
    calls = []

    def probe(_):
        calls.append("probe")
        raise RuntimeError("synthetic probe failure")

    with pytest.raises(hie.HIEExperimentError, match="aborted safely"):
        _run(
            events, snapshot, candidate,
            lambda: (calls.append("baseline") or _result("FAIL")),
            probe,
        )

    names = [event["event_name"] for event in events]
    assert calls == ["baseline", "probe"]
    assert names[-1] == "hie.experiment.aborted"
    aborted = events[-1]
    assert aborted["metadata"]["error_type"] == "RuntimeError"
    assert aborted["metadata"]["provider_calls"] == 2
    assert all(event["component"] == "hie" for event in events)
    assert not any(event["event_name"] == "hie.experiment.completed" for event in events)


def test_tie_is_recorded_without_promotion(monkeypatch):
    events = _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Check for a stable marker.")

    record = _run(
        events, snapshot, candidate,
        lambda: _result("PASS baseline"),
        lambda _: _result("PASS candidate"),
    )

    assert record["outcome"] == "tie"
    assert record["promotion"] == "not_performed"
    assert events[-1]["event_name"] == "hie.experiment.completed"


def test_candidate_regression_is_recorded_without_promotion(monkeypatch):
    events = _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Check for a stable marker.")

    record = _run(
        events, snapshot, candidate,
        lambda: _result("PASS baseline"),
        lambda _: _result("FAIL candidate"),
    )

    assert record["outcome"] == "regression"
    assert record["promotion"] == "not_performed"
    assert events[-1]["event_name"] == "hie.experiment.completed"


def test_output_budget_exceeded_aborts_before_verification(monkeypatch):
    events = _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Check for a stable marker.")
    verifier_calls = []

    with pytest.raises(hie.HIEBudgetExceeded, match="output exceeds"):
        _run(
            events, snapshot, candidate,
            lambda: _result("X" * 20),
            lambda _: _result("PASS"),
            verifier=lambda output: (verifier_calls.append(output) or True),
            budgets=hie.HIEBudgets(output_chars_per_call=10),
        )

    assert verifier_calls == []
    assert events[-1]["event_name"] == "hie.experiment.aborted"
    assert events[-1]["metadata"]["provider_calls"] == 1
