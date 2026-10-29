from pathlib import Path

import pytest

from app.services import hie_fixture_adapter as adapter


def test_uses_independent_disposable_copies_and_preserves_source(tmp_path, monkeypatch):
    source = tmp_path / "fixture"
    source.mkdir()
    original = source / "brief.md"
    original.write_text("baseline text\n", encoding="utf-8")
    seen = {}
    temporary_roots = {}

    def baseline_factory(root):
        seen["baseline_root"] = root
        temporary_roots["baseline"] = root
        return lambda: {"stage": "baseline"}

    def probe_factory(root):
        seen["candidate_root"] = root
        temporary_roots["candidate"] = root
        return lambda candidate: {"stage": "candidate", "sha256": candidate["sha256"]}

    def fake_orchestrator(**kwargs):
        seen["kwargs"] = kwargs
        assert kwargs["isolated_fixture"] is True
        assert kwargs["baseline_runner"]()["stage"] == "baseline"
        assert kwargs["probe_runner"]({"sha256": "abc"})["stage"] == "candidate"
        return {"promotion": "not_performed"}

    monkeypatch.setattr(adapter, "run_candidate_experiment", fake_orchestrator)

    result = adapter.run_disposable_fixture_experiment(
        source,
        baseline_runner_factory=baseline_factory,
        probe_runner_factory=probe_factory,
        task_id=42,
        baseline_snapshot={"fixture": "snapshot"},
        candidate={"sha256": "abc"},
        provider_identity={"provider": "test", "model": "fake", "revision": "v1"},
        verifier=lambda _: True,
    )

    assert result == {"promotion": "not_performed"}
    assert seen["baseline_root"] != seen["candidate_root"]
    assert not temporary_roots["baseline"].exists()
    assert not temporary_roots["candidate"].exists()
    assert original.read_text(encoding="utf-8") == "baseline text\n"


def test_adapter_controls_isolation_flag(tmp_path):
    source = tmp_path / "fixture"
    source.mkdir()

    with pytest.raises(ValueError, match="controlled by this adapter"):
        adapter.run_disposable_fixture_experiment(
            source,
            baseline_runner_factory=lambda root: lambda: {},
            probe_runner_factory=lambda root: lambda candidate: {},
            isolated_fixture=False,
        )


def test_disposable_copies_are_cleaned_when_orchestrator_fails(tmp_path, monkeypatch):
    source = tmp_path / "fixture"
    source.mkdir()
    (source / "brief.txt").write_text("original", encoding="utf-8")
    roots = []

    def factory(root):
        roots.append(root)
        return lambda *args: {"provider_identity": {}, "output": ""}

    monkeypatch.setattr(
        adapter,
        "run_candidate_experiment",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("expected test failure")),
    )

    with pytest.raises(RuntimeError, match="expected test failure"):
        adapter.run_disposable_fixture_experiment(
            source,
            baseline_runner_factory=factory,
            probe_runner_factory=factory,
            task_id=42,
            baseline_snapshot={},
            candidate={},
            provider_identity={},
            verifier=lambda _: True,
        )

    assert len(roots) == 2
    assert all(not root.exists() for root in roots)
    assert (source / "brief.txt").read_text(encoding="utf-8") == "original"
