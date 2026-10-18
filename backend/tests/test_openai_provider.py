import io
import json
from unittest.mock import patch

import pytest

from app.providers.openai import OpenAIProvider


def test_payload_uses_responses_api_and_does_not_forward_local_only_settings():
    payload = OpenAIProvider._payload(
        [{"role": "system", "content": "rules"}, {"role": "user", "content": "hello"}],
        "gpt-4.1-mini",
        {"temperature": 0.2, "top_k": 40, "num_predict": 700, "request_timeout_seconds": 20},
        stream=False,
    )
    assert payload == {
        "model": "gpt-4.1-mini",
        "input": [{"role": "system", "content": "rules"}, {"role": "user", "content": "hello"}],
        "stream": False,
        "store": False,
        "max_output_tokens": 700,
    }


def test_missing_api_key_fails_clearly_without_network(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        OpenAIProvider().generate([], "gpt-4.1-mini", {})


def test_generate_reads_output_text_from_responses_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = OpenAIProvider()
    provider._post = lambda payload, configuration: {"output_text": "Olá do OpenAI"}
    assert provider.generate([{"role": "user", "content": "Oi"}], "gpt-4.1-mini", {}) == "Olá do OpenAI"


def test_generate_extracts_text_from_output_items():
    response = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Olá"}]}]}
    assert OpenAIProvider._response_text(response) == "Olá"


def test_stream_emits_only_output_text_deltas(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    body = b'data: {"type":"response.created"}\n\ndata: {"type":"response.output_text.delta","delta":"Ola "}\n\ndata: {"type":"response.output_text.delta","delta":"mundo"}\n\ndata: {"type":"response.completed"}\n\n'
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def __iter__(self): return iter(body.splitlines(keepends=True))
    with patch("app.providers.openai.request.urlopen", return_value=FakeResponse()):
        assert "".join(OpenAIProvider().stream([{"role": "user", "content": "Oi"}], "gpt-4.1-mini", {})) == "Ola mundo"


def test_tool_schema_is_converted_to_responses_api_format():
    converted = OpenAIProvider._response_tool({
        "type": "function",
        "function": {"name": "filesystem", "description": "Read files", "parameters": {"type": "object"}},
    })
    assert converted == {
        "type": "function",
        "name": "filesystem",
        "description": "Read files",
        "parameters": {"type": "object"},
        "strict": False,
    }


def test_generate_with_tools_returns_one_native_tool_decision(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = OpenAIProvider()
    provider._post = lambda payload, configuration: {
        "output": [{"type": "function_call", "name": "filesystem", "arguments": '{"operation":"read","path":"a.md"}'}]
    }
    result = provider.generate_with_tools(
        [{"role": "user", "content": "Leia a.md"}],
        "gpt-4.1-mini",
        {},
        [{"type": "function", "function": {"name": "filesystem", "parameters": {"type": "object"}}}],
    )
    assert result == {"type": "tool_call", "tool": "filesystem", "arguments": {"operation": "read", "path": "a.md"}}


def test_timeout_is_bounded():
    with pytest.raises(ValueError, match="between 1 and 600"):
        OpenAIProvider._timeout({"request_timeout_seconds": 0})


def test_http_error_never_includes_response_body_or_secret():
    exc = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
        "https://api.openai.com/v1/responses", 401, "unauthorized", {}, io.BytesIO(b"secret-key-body")
    )
    assert "authentication failed" in str(OpenAIProvider._http_error(exc)).lower()
    assert "secret-key-body" not in str(OpenAIProvider._http_error(exc))


def test_model_configuration_rejects_secret_fields():
    from app.api.models import _reject_secret_configuration

    with pytest.raises(ValueError, match="must not contain secret fields"):
        _reject_secret_configuration({"nested": {"openai_api_key": "should-not-be-stored"}})


def test_model_configuration_allows_non_secret_settings():
    from app.api.models import _reject_secret_configuration

    _reject_secret_configuration({"temperature": 0.2, "num_predict": 500})


def test_openai_status_reports_configuration_without_exposing_key(monkeypatch):
    from app.api.models import model_provider_status

    monkeypatch.setenv("OPENAI_API_KEY", "very-secret-value")
    result = model_provider_status("openai")
    assert result == {"provider": "openai", "online": True, "configured": True, "running_models": []}
    assert "very-secret-value" not in repr(result)


def test_openai_status_reports_missing_key(monkeypatch):
    from app.api.models import model_provider_status

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert model_provider_status("openai")["configured"] is False
