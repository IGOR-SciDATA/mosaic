from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import hie_integration as integration


def test_markdown_fixture_adapter_uses_selected_provider_and_separate_copies(monkeypatch, tmp_path: Path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "input.md").write_text("# Source\nKeep the facts.", encoding="utf-8")

    task = SimpleNamespace(id=7, status="executing", conversation_id=11)
    conversation = SimpleNamespace(model_id=13)
    model = SimpleNamespace(
        enabled=True,
        provider="ollama",
        model_name="test-model",
        configuration={},
    )
    monkeypatch.setattr(integration, "get_task", lambda _task_id: task)
    monkeypatch.setattr(integration, "get_conversation", lambda _conversation_id: conversation)
    monkeypatch.setattr(integration, "get_model", lambda _model_id: model)
    monkeypatch.setattr(integration, "validate_candidate", lambda *args, **kwargs: None)

    class FakeProvider:
        def __init__(self):
            self.calls = []

        def generate(self, *, messages, model_name, configuration):
            self.calls.append((messages, model_name, configuration))
            return "# Result\nRequired heading."

    provider = FakeProvider()
    monkeypatch.setattr(integration, "resolve_model_provider", lambda _model: provider)

    observed = {}

    def fake_orchestrator(task_id, baseline, candidate, **kwargs):
        observed["task_id"] = task_id
        observed["baseline"] = baseline
        observed["candidate"] = candidate
        observed["kwargs"] = kwargs
        observed["baseline_output"] = kwargs["baseline_runner"]()["output"]
        observed["candidate_output"] = kwargs["probe_runner"](candidate)["output"]
        return {"outcome": "tie", "promotion": "not_performed"}

    monkeypatch.setattr(integration, "run_candidate_experiment", fake_orchestrator)
    baseline = {"slug": "reviewer", "version": 1, "sha256": "a" * 64, "instructions": "Be precise."}
    candidate = {"content": "Always include a required heading."}

    result = integration.run_markdown_fixture_experiment(
        7,
        baseline,
        candidate,
        fixture_source=fixture,
        objective="Return a Markdown result with a heading.",
        verifier=lambda output: output.startswith("# Result"),
    )

    assert result["promotion"] == "not_performed"
    assert observed["task_id"] == 7
    assert observed["kwargs"]["isolated_fixture"] is True
    assert observed["kwargs"]["provider_identity"] == {
        "provider": "ollama",
        "model": "test-model",
        "revision": "test-model",
    }
    assert len(provider.calls) == 2
    assert all(call[1] == "test-model" for call in provider.calls)
    assert provider.calls[0][0][1]["content"] != provider.calls[1][0][1]["content"]
    assert observed["baseline_output"] == observed["candidate_output"]


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_markdown_fixture_adapter_rejects_terminal_task(monkeypatch, status):
    monkeypatch.setattr(
        integration,
        "get_task",
        lambda _task_id: SimpleNamespace(id=7, status=status, conversation_id=11),
    )
    with pytest.raises(ValueError, match="terminal Task"):
        integration.run_markdown_fixture_experiment(
            7,
            {},
            {},
            fixture_source="unused",
            objective="Objective",
            verifier=lambda _output: True,
        )


def test_markdown_fixture_adapter_requires_one_markdown_file(monkeypatch, tmp_path: Path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "one.md").write_text("one", encoding="utf-8")
    (fixture / "two.md").write_text("two", encoding="utf-8")

    task = SimpleNamespace(id=7, status="executing", conversation_id=11)
    monkeypatch.setattr(integration, "get_task", lambda _task_id: task)
    monkeypatch.setattr(integration, "get_conversation", lambda _id: SimpleNamespace(model_id=13))
    monkeypatch.setattr(
        integration,
        "get_model",
        lambda _id: SimpleNamespace(enabled=True, provider="ollama", model_name="test-model", configuration={}),
    )
    monkeypatch.setattr(integration, "resolve_model_provider", lambda _model: object())
    monkeypatch.setattr(integration, "validate_candidate", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        integration,
        "run_candidate_experiment",
        lambda task_id, baseline, candidate, **kwargs: kwargs["baseline_runner"](),
    )

    with pytest.raises(ValueError, match="exactly one"):
        integration.run_markdown_fixture_experiment(
            7,
            {"instructions": "Be precise."},
            {"content": "Include headings."},
            fixture_source=fixture,
            objective="Produce Markdown.",
            verifier=lambda _output: True,
        )
