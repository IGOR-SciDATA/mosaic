import pytest

from app.services.agent_decision import _diagnostic_preview, parse_agent_decision


def test_parse_final_decision():
    assert parse_agent_decision('{"type":"final","content":"Concluído."}') == {
        "type": "final", "content": "Concluído."
    }


def test_parse_json_fenced_final_decision():
    assert parse_agent_decision('```json\n{"type":"final","content":"OK"}\n```') == {
        "type": "final", "content": "OK"
    }


def test_reject_invalid_json_and_unknown_decision_fields():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_agent_decision("resposta sem JSON")
    with pytest.raises(ValueError, match="unsupported fields"):
        parse_agent_decision('{"type":"final","content":"OK","reasoning":"private"}')


def test_reject_empty_final_response():
    with pytest.raises(ValueError, match="non-empty"):
        parse_agent_decision('{"type":"final","content":"  "}')


def test_tool_call_requires_registered_tool_and_valid_schema():
    with pytest.raises(ValueError, match="Unknown tool"):
        parse_agent_decision('{"type":"tool_call","tool":"made_up","arguments":{}}')
    with pytest.raises(ValueError, match="Missing required"):
        parse_agent_decision('{"type":"tool_call","tool":"calculator","arguments":{}}')


def test_tool_call_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unsupported fields"):
        parse_agent_decision('{"type":"tool_call","tool":"calculator","arguments":{"expression":"1+1"},"extra":true}')


def test_provider_decider_retries_one_malformed_response_and_records_safe_events(monkeypatch):
    from types import SimpleNamespace

    import app.services.agent_decision as adapter

    task = SimpleNamespace(id=7, conversation_id=3, project_id=2)
    conversation = SimpleNamespace(model_id=4)
    model = SimpleNamespace(
        enabled=True, provider="ollama", model_name="test:model", configuration={}
    )
    monkeypatch.setattr(adapter, "get_task", lambda task_id: task)
    monkeypatch.setattr(adapter, "get_conversation", lambda conversation_id: conversation)
    monkeypatch.setattr(adapter, "get_model", lambda model_id: model)

    responses = iter([
        "I will do that now, here's the answer.",
        '{"type":"final","content":"Resumo criado."}',
    ])

    class FakeProvider:
        def generate(self, **kwargs):
            return next(responses)

    monkeypatch.setattr(adapter, "OllamaProvider", FakeProvider)
    events = []
    monkeypatch.setattr(
        adapter, "create_task_event",
        lambda **kwargs: events.append(kwargs),
    )

    decision = adapter.create_provider_decider(task.id)([{"role": "user", "content": "Resuma"}])

    assert decision == {"type": "final", "content": "Resumo criado."}
    assert [event["event_name"] for event in events].count("model_request_started") == 2
    invalid = next(event for event in events if event["event_name"] == "decision_invalid")
    assert invalid["metadata"]["response_preview"] == "I will do that now, here's the answer."
    assert any(event["event_name"] == "decision_retry" for event in events)
    parsed = next(event for event in events if event["event_name"] == "decision_parsed")
    assert parsed["metadata"]["output_preview"] == "Resumo criado."
    assert all("I will do that" not in str(event["metadata"]) for event in events)


def test_provider_decider_does_not_retry_more_than_once(monkeypatch):
    from types import SimpleNamespace

    import app.services.agent_decision as adapter

    task = SimpleNamespace(id=7, conversation_id=3, project_id=2)
    monkeypatch.setattr(adapter, "get_task", lambda task_id: task)
    monkeypatch.setattr(adapter, "get_conversation", lambda conversation_id: SimpleNamespace(model_id=4))
    monkeypatch.setattr(
        adapter, "get_model",
        lambda model_id: SimpleNamespace(enabled=True, provider="ollama", model_name="test:model", configuration={}),
    )

    class FakeProvider:
        calls = 0

        def generate(self, **kwargs):
            self.calls += 1
            return "not JSON"

    provider = FakeProvider()
    monkeypatch.setattr(adapter, "OllamaProvider", lambda: provider)
    monkeypatch.setattr(adapter, "create_task_event", lambda **kwargs: None)

    with pytest.raises(ValueError, match="valid JSON"):
        adapter.create_provider_decider(task.id)([])

    assert provider.calls == 2



def test_diagnostic_preview_keeps_response_tail_and_redacts_thinking_and_secrets():
    preview = _diagnostic_preview("A" * 800 + " tail=secret-value", limit=100)
    assert len(preview) <= 100
    assert "AAAA" in preview
    assert "tail=[REDACTED]" in preview
