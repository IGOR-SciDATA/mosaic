import pytest

from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.repository import create_model
from app.models.task_repository import create_task, get_task
from app.services import harness
from app.services.harness import parse_agent_decision, run_task_agent


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def _task():
    model = create_model("Harness test", "ollama", "harness:test")
    conversation = create_conversation("Harness test", model.id)
    return create_task(type="generic", mode="agent", conversation_id=conversation.id)


def test_parse_agent_final_decision():
    assert parse_agent_decision('{"type":"final","content":"Done"}') == {
        "type": "final",
        "content": "Done",
    }


def test_parse_agent_tool_call_decision():
    assert parse_agent_decision(
        '{"type":"tool_call","tool":"calculator","arguments":{"expression":"2+2"}}'
    ) == {
        "type": "tool_call",
        "tool": "calculator",
        "arguments": {"expression": "2+2"},
    }


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"type":"final","content":42}',
        '{"type":"tool_call","tool":"calculator","arguments":[]}',
        '{"type":"unknown"}',
    ],
)
def test_parse_agent_rejects_invalid_decisions(raw):
    with pytest.raises(ValueError):
        parse_agent_decision(raw)


def test_provider_backed_harness_runs_agent_to_completion(monkeypatch):
    task = _task()

    class FakeProvider:
        def __init__(self):
            self.calls = []

        def generate(self, messages, model_name, configuration):
            self.calls.append((messages, model_name, configuration))
            return '{"type":"final","content":"Concluído pelo harness"}'

    provider = FakeProvider()
    monkeypatch.setattr(harness, "_get_provider", lambda provider_name: provider)

    result = run_task_agent(task.id)

    assert result == {
        "status": "completed",
        "output": "Concluído pelo harness",
        "iterations": 1,
    }
    assert get_task(task.id).status == "completed"
    assert len(provider.calls) == 1
    assert provider.calls[0][1] == "harness:test"
    assert any("componente de decisão" in m["content"] for m in provider.calls[0][0])


def test_provider_backed_harness_executes_tool_then_requests_final(monkeypatch):
    task = _task()

    class FakeProvider:
        def __init__(self):
            self.responses = iter([
                '{"type":"tool_call","tool":"calculator","arguments":{"expression":"6*7"}}',
                '{"type":"final","content":"42"}',
            ])
            self.calls = 0

        def generate(self, messages, model_name, configuration):
            self.calls += 1
            return next(self.responses)

    provider = FakeProvider()
    monkeypatch.setattr(harness, "_get_provider", lambda provider_name: provider)

    result = run_task_agent(task.id)

    assert result["status"] == "completed"
    assert result["output"] == "42"
    assert result["iterations"] == 2
    assert provider.calls == 2
