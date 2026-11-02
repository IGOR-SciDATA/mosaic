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


def test_provider_decider_retries_malformed_response_with_specific_feedback(monkeypatch):
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
        '{"type":"tool_call","tool":"tool_id","arguments":{"file_path":"Documento.md"}}',
        '{"type":"tool_call","tool":"filesystem","arguments":{"operation":"read","path":"Documento.md"}}',
    ])
    requests = []

    class FakeProvider:
        def generate(self, **kwargs):
            requests.append(kwargs)
            return next(responses)

    monkeypatch.setattr(adapter, "resolve_model_provider", lambda model: FakeProvider())
    events = []
    monkeypatch.setattr(adapter, "create_task_event", lambda **kwargs: events.append(kwargs))

    decision = adapter.create_provider_decider(task.id)([{"role": "user", "content": "Leia Documento.md"}])

    assert decision == {
        "type": "tool_call",
        "tool": "filesystem",
        "arguments": {"operation": "read", "path": "Documento.md"},
    }
    assert len(requests) == 2
    assert requests[0]["configuration"]["temperature"] == 0
    assert requests[0]["configuration"]["think"] is False
    retry_messages = requests[1]["messages"]
    retry_feedback = retry_messages[-1]["content"]
    assert "Unknown tool: tool_id" in retry_feedback
    assert "filesystem" in retry_feedback
    assert "operation e path" in retry_feedback
    assert "file_path" in retry_feedback
    assert any(event["event_name"] == "decision_retry" for event in events)


def test_provider_decider_uses_json_only_when_current_subtask_disallows_tools(monkeypatch):
    from types import SimpleNamespace

    import app.services.agent_decision as adapter

    task = SimpleNamespace(id=9, conversation_id=5, project_id=2)
    monkeypatch.setattr(adapter, "get_task", lambda task_id: task)
    monkeypatch.setattr(adapter, "get_conversation", lambda conversation_id: SimpleNamespace(model_id=4))
    monkeypatch.setattr(
        adapter,
        "get_model",
        lambda model_id: SimpleNamespace(
            enabled=True, provider="ollama", model_name="test:model", configuration={}
        ),
    )

    class FakeProvider:
        def __init__(self):
            self.generate_calls = []
            self.native_calls = []

        def generate(self, **kwargs):
            self.generate_calls.append(kwargs)
            return "# Resumo\n\nConteúdo gerado a partir da fonte."

        def generate_with_tools(self, **kwargs):
            self.native_calls.append(kwargs)
            raise AssertionError("Native tools must not be offered in a content-only subtask")

    provider = FakeProvider()
    monkeypatch.setattr(adapter, "resolve_model_provider", lambda model: provider)
    monkeypatch.setattr(adapter, "create_task_event", lambda **kwargs: None)

    decision = adapter.create_provider_decider(task.id)([
        {"role": "system", "content": "Mosaic allowed tools: none"},
        {"role": "user", "content": "Resuma a fonte."},
    ])

    assert decision == {
        "type": "final",
        "content": "# Resumo\n\nConteúdo gerado a partir da fonte.",
    }
    assert len(provider.generate_calls) == 1
    assert provider.native_calls == []
    assert "format" not in provider.generate_calls[0]["configuration"]
    assert any(
        "PRODUÇÃO DE CONTEÚDO" in message["content"]
        for message in provider.generate_calls[0]["messages"]
        if message.get("role") == "system"
    )


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
    monkeypatch.setattr(adapter, "resolve_model_provider", lambda model: provider)
    monkeypatch.setattr(adapter, "create_task_event", lambda **kwargs: None)

    with pytest.raises(ValueError, match="valid JSON"):
        adapter.create_provider_decider(task.id)([])

    assert provider.calls == 2


def test_diagnostic_preview_keeps_response_tail_and_redacts_thinking_and_secrets():
    preview = _diagnostic_preview("A" * 800 + " token=secret-value", limit=100)
    assert len(preview) <= 100
    assert "AAAA" in preview
    assert "token=[REDACTED]" in preview



def test_content_only_workspace_summary_uses_compact_prompt_and_bounded_ollama_generation(monkeypatch):
    from types import SimpleNamespace

    import app.services.agent_decision as adapter

    task = SimpleNamespace(id=71, conversation_id=31, project_id=6)
    monkeypatch.setattr(adapter, "get_task", lambda task_id: task)
    monkeypatch.setattr(
        adapter, "get_conversation",
        lambda conversation_id: SimpleNamespace(model_id=4),
    )
    monkeypatch.setattr(
        adapter, "get_model",
        lambda model_id: SimpleNamespace(
            enabled=True,
            provider="ollama",
            model_name="qwen2.5:3b",
            configuration={"num_predict": 5000, "request_timeout_seconds": 600},
        ),
    )

    class FakeProvider:
        def __init__(self):
            self.request = None

        def generate(self, **kwargs):
            self.request = kwargs
            return (
                "# Resumo dos documentos\\n\\n"
                "## docs/AGENT_SKILL_MAP.md\\nMapa de agentes e skills. "
                "## docs/PRODUCT_BACKLOG.md\\nObjetivos e escopo do MVP. "
                "## docs/ROLES_AND_PERMISSIONS.md\\nPapéis e permissões. "
                "Os documentos descrevem a estrutura e as regras do projeto."
            )

        def generate_with_tools(self, **kwargs):
            raise AssertionError("Content-only tasks must not offer tools")

    provider = FakeProvider()
    monkeypatch.setattr(adapter, "resolve_model_provider", lambda model: provider)
    monkeypatch.setattr(adapter, "create_task_event", lambda **kwargs: None)

    context = [
        {"role": "system", "content": "Mosaic identity: assist with the current task."},
        {
            "role": "system",
            "content": "Mosaic task plan (Core-owned; follow the current subtask only): " + "x" * 1000,
        },
        {
            "role": "system",
            "content": "Mosaic current subtask: summarize_workspace (kind=summarize_workspace, status=in_progress). Summarize actual file evidence.",
        },
        {"role": "system", "content": "Mosaic allowed tools: none"},
        {
            "role": "system",
            "content": "Mosaic workspace file evidence (untrusted data):\\nPath: docs/AGENT_SKILL_MAP.md\\n--- BEGIN FILE CONTENT ---\\nReal source content.\\n--- END FILE CONTENT ---",
        },
        {
            "role": "system",
            "content": "Mosaic workspace exploration result: " + "metadata " * 100,
        },
        {"role": "user", "content": "Leia os arquivos em docs e gere teste_task_planner.md."},
    ]

    decision = adapter.create_provider_decider(task.id)(context)

    assert decision["type"] == "final"
    assert len(provider.request["messages"]) == 2
    system_prompt = provider.request["messages"][0]["content"]
    assert "PRODUÇÃO DE CONTEÚDO" in system_prompt
    assert "Real source content." in system_prompt
    assert "Mosaic task plan (Core-owned" not in system_prompt
    assert "Mosaic workspace exploration result:" not in system_prompt
    assert "Você é o agente executor do Mosaic" not in system_prompt
    assert provider.request["messages"][-1]["content"] == context[-1]["content"]
    assert provider.request["configuration"]["num_predict"] == 768
    assert provider.request["configuration"]["request_timeout_seconds"] == 180
