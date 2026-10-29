import hashlib
from types import SimpleNamespace

import pytest

from app.services import hie_orchestrator as hie
from app.services.hie_candidate import build_candidate, canonical_json


def _snapshot():
    profile = {
        "slug": "backend-reviewer",
        "name": "Backend Reviewer",
        "description": "Reviews backend changes",
        "instructions": "Check contracts and security.",
        "version": 3,
        "skills": [
            {"name": "API review", "content": "Check schemas.", "enabled": True, "version": 2, "sha256": ""}
        ],
    }

    def digest(value):
        return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

    skill = profile["skills"][0]
    skill["sha256"] = digest({key: skill[key] for key in ("name", "content", "enabled", "version")})
    profile["sha256"] = digest({
        key: profile[key] for key in (
            "slug", "name", "description", "instructions", "version", "skills"
        )
    })
    return profile


def _setup(monkeypatch, status="executing"):
    task = SimpleNamespace(id=42, conversation_id=7, project_id=3, status=status)
    events = []
    monkeypatch.setattr(hie, "get_task", lambda task_id: task if task_id == 42 else None)
    monkeypatch.setattr(hie, "create_task_event", lambda **kwargs: events.append(kwargs))
    # Orchestrator unit tests isolate comparison logic from Core Artifact storage.
    monkeypatch.setattr(hie, "persist_output_evidence", lambda *args, **kwargs: {"baseline": {}, "candidate": {}})
    monkeypatch.setattr(hie, "persist_record_evidence", lambda *args, **kwargs: None)
    return task, events


def _result(output, identity=None):
    return {
        "provider_identity": identity or {"provider": "ollama", "model": "qwen:3b", "revision": "sha256:abc"},
        "output": output,
    }


def test_sequential_experiment_records_result_and_never_promotes(monkeypatch):
    _, events = _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Check contracts, security, and edge cases.")
    calls = []
    identity = {"provider": "ollama", "model": "qwen:3b", "revision": "sha256:abc"}

    record = hie.run_candidate_experiment(
        42, snapshot, candidate,
        provider_identity=identity,
        baseline_runner=lambda: (calls.append("baseline") or _result("missing title")),
        probe_runner=lambda proposed: (calls.append(proposed["sha256"]) or _result("title present")),
        verifier=lambda output: "title present" in output,
        isolated_fixture=True,
    )

    assert calls == ["baseline", candidate["sha256"]]
    assert record["outcome"] == "candidate_passed_baseline_failed"
    assert record["promotion"] == "not_performed"
    assert record["usage"]["provider_calls"] == 2
    assert record["usage"]["tool_calls"] == 0
    assert record["usage"]["retries"] == 0
    assert any(event["event_name"] == "hie.experiment.completed" for event in events)
    assert all(event["component"] == "hie" for event in events)


def test_requires_explicit_disposable_fixture(monkeypatch):
    _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    with pytest.raises(hie.HIEExperimentError, match="isolated disposable fixture"):
        hie.run_candidate_experiment(
            42, snapshot, candidate,
            provider_identity={"provider": "ollama", "model": "qwen:3b", "revision": "abc"},
            baseline_runner=lambda: _result("ok"),
            probe_runner=lambda _: _result("ok"),
            verifier=lambda _: True,
        )


def test_aborts_when_provider_identity_cannot_be_proven_equal(monkeypatch):
    _, events = _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    with pytest.raises(hie.HIEExperimentError, match="identity mismatch"):
        hie.run_candidate_experiment(
            42, snapshot, candidate,
            provider_identity={"provider": "ollama", "model": "qwen:3b", "revision": "abc"},
            baseline_runner=lambda: _result("ok"),
            probe_runner=lambda _: _result(
                "ok", {"provider": "openai", "model": "other", "revision": "xyz"}
            ),
            verifier=lambda _: True,
            isolated_fixture=True,
        )
    assert any(event["event_name"] == "hie.experiment.aborted" for event in events)


def test_cancellation_between_stages_prevents_probe(monkeypatch):
    _, events = _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    calls = []
    checks = iter([False, False, True])
    with pytest.raises(hie.HIEExperimentCancelled):
        hie.run_candidate_experiment(
            42, snapshot, candidate,
            provider_identity={"provider": "ollama", "model": "qwen:3b", "revision": "sha256:abc"},
            baseline_runner=lambda: (calls.append("baseline") or _result("ok")),
            probe_runner=lambda _: (calls.append("probe") or _result("ok")),
            verifier=lambda _: True,
            isolated_fixture=True,
            cancelled=lambda: next(checks, True),
        )
    assert calls == ["baseline"]
    assert any(event["event_name"] == "hie.experiment.cancelled" for event in events)


def test_rejects_terminal_task_and_budget_above_hard_ceiling(monkeypatch):
    _setup(monkeypatch, status="completed")
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    with pytest.raises(hie.HIEExperimentError, match="terminal Task"):
        hie.run_candidate_experiment(
            42, snapshot, candidate,
            provider_identity={"provider": "ollama", "model": "qwen:3b", "revision": "abc"},
            baseline_runner=lambda: _result("ok"),
            probe_runner=lambda _: _result("ok"),
            verifier=lambda _: True,
            isolated_fixture=True,
        )
    with pytest.raises(ValueError, match="exceeds allowed ceiling"):
        hie.HIEBudgets(provider_calls=5).validate()


def test_rejects_missing_provider_revision_and_non_boolean_verifier(monkeypatch):
    _setup(monkeypatch)
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    with pytest.raises(hie.HIEExperimentError, match="provider, model, and revision"):
        hie.run_candidate_experiment(
            42, snapshot, candidate,
            provider_identity={"provider": "ollama", "model": "qwen:3b"},
            baseline_runner=lambda: _result("ok"),
            probe_runner=lambda _: _result("ok"),
            verifier=lambda _: True,
            isolated_fixture=True,
        )

    with pytest.raises(hie.HIEExperimentError, match="Verifier must return a boolean"):
        hie.run_candidate_experiment(
            42, snapshot, candidate,
            provider_identity={"provider": "ollama", "model": "qwen:3b", "revision": "sha256:abc"},
            baseline_runner=lambda: _result("ok"),
            probe_runner=lambda _: _result("ok"),
            verifier=lambda _: "yes",
            isolated_fixture=True,
        )



def test_discrete_budgets_reject_fractional_values():
    with pytest.raises(ValueError, match="must be an integer"):
        hie.HIEBudgets(provider_calls=1.5).validate()
    with pytest.raises(ValueError, match="must be an integer"):
        hie.HIEBudgets(artifact_bytes=12.5).validate()


def test_wall_clock_budget_accepts_fractional_seconds():
    hie.HIEBudgets(wall_seconds=1.5).validate()
