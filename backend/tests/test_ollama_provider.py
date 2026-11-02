import io
import json
from unittest.mock import patch

from app.providers.ollama import OllamaProvider


def _ollama_stream(*chunks):
    body = b"".join(
        (json.dumps(chunk, ensure_ascii=False) + "\n").encode("utf-8")
        for chunk in chunks
    )
    return io.BytesIO(body)


def _chunk(content="", *, done=False, thinking=None):
    message = {"role": "assistant", "content": content}
    if thinking is not None:
        message["thinking"] = thinking
    return {"message": message, "done": done}


def test_generate_with_tools_uses_native_ollama_tool_calls():
    provider = OllamaProvider()
    observed = {}
    assistant_message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "function": {
                "name": "filesystem",
                "arguments": {"operation": "read", "path": "Documento.md"},
            }
        }],
    }

    def fake_post(path, payload):
        observed["path"] = path
        observed["payload"] = payload
        return {"message": assistant_message}

    provider._post = fake_post
    tools = [{
        "type": "function",
        "function": {
            "name": "filesystem",
            "description": "Read workspace files",
            "parameters": {
                "type": "object",
                "required": ["operation", "path"],
                "properties": {
                    "operation": {"type": "string", "enum": ["read"]},
                    "path": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    }]

    result = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Leia Documento.md"}],
        model_name="qwen2.5:3b",
        configuration={"request_timeout_seconds": 45, "num_predict": 128, "format": "json"},
        tools=tools,
    )

    assert result["type"] == "tool_call"
    assert result["tool"] == "filesystem"
    assert result["arguments"] == {"operation": "read", "path": "Documento.md"}
    assert result["_native_message"] == assistant_message
    assert observed["path"] == "/api/chat"
    assert observed["payload"]["options"]["num_predict"] == -1
    assert "request_timeout_seconds" not in observed["payload"]["options"]
    assert observed["payload"]["tools"] == tools
    assert "format" not in observed["payload"]


def test_generate_extracts_qwen3_answer_after_thinking_marker():
    provider = OllamaProvider()
    provider._post = lambda path, payload, **kwargs: {
        "message": {
            "role": "assistant",
            "content": "Let me think through this carefully.\n</think>\nteste",
        }
    }

    result = provider.generate(
        messages=[{"role": "user", "content": "Responda teste"}],
        model_name="qwen3:4b",
        configuration={"think": False},
    )

    assert result == "teste"
    payload = provider._request_payload(
        [{"role": "user", "content": "Responda teste"}],
        "qwen3:4b",
        {"format": "json"},
        stream=False,
    )
    assert payload["format"] == "json"


def test_stream_suppresses_qwen3_inline_thinking_and_handles_split_marker():
    provider = OllamaProvider()
    response = _ollama_stream(
        _chunk("Reasoning that must not be shown."),
        _chunk("</thi"),
        _chunk("nk>\n"),
        _chunk("res"),
        _chunk("posta final"),
        _chunk(done=True),
    )

    with patch("app.providers.ollama.request.urlopen", return_value=response):
        result = list(
            provider.stream(
                messages=[{"role": "user", "content": "Responda"}],
                model_name="qwen3:4b",
                configuration={"think": False},
            )
        )

    assert "".join(result) == "resposta final"
    assert all("Reasoning" not in part and "</think>" not in part for part in result)


def test_stream_uses_content_when_ollama_separates_thinking_field():
    provider = OllamaProvider()
    response = _ollama_stream(
        _chunk("", thinking="Reasoning in a separate field"),
        _chunk("resposta "),
        _chunk("final"),
        _chunk(done=True),
    )

    with patch("app.providers.ollama.request.urlopen", return_value=response):
        result = list(
            provider.stream(
                messages=[{"role": "user", "content": "Responda"}],
                model_name="qwen3:4b",
                configuration={"think": True},
            )
        )

    assert result == ["resposta ", "final"]


def test_non_qwen3_models_keep_normal_streaming():
    provider = OllamaProvider()
    response = _ollama_stream(
        _chunk("Olá "),
        _chunk("mundo"),
        _chunk(done=True),
    )

    with patch("app.providers.ollama.request.urlopen", return_value=response):
        result = list(
            provider.stream(
                messages=[{"role": "user", "content": "Oi"}],
                model_name="llama3.2:3b",
                configuration={},
            )
        )

    assert result == ["Olá ", "mundo"]


def test_generate_keeps_normal_answer_without_marker():
    provider = OllamaProvider()
    provider._post = lambda path, payload, **kwargs: {
        "message": {"role": "assistant", "content": "  resposta normal  "}
    }

    result = provider.generate(
        messages=[{"role": "user", "content": "Oi"}],
        model_name="qwen3:4b",
        configuration={},
    )

    assert result == "resposta normal"



def test_generate_extracts_tagged_thinking_for_any_ollama_model():
    provider = OllamaProvider()
    provider._post = lambda path, payload, **kwargs: {
        "message": {
            "role": "assistant",
            "content": "<think>private reasoning</think>Resposta final.",
        }
    }

    result = provider.generate(
        messages=[{"role": "user", "content": "Responda"}],
        model_name="llama3.2:3b",
        configuration={},
    )

    assert result == "Resposta final."


def test_generate_does_not_expose_truncated_tagged_thinking():
    provider = OllamaProvider()
    provider._post = lambda path, payload, **kwargs: {
        "message": {
            "role": "assistant",
            "content": "<think>private reasoning without a closing marker",
        }
    }

    result = provider.generate(
        messages=[{"role": "user", "content": "Responda"}],
        model_name="llama3.2:3b",
        configuration={},
    )

    assert result == ""



def test_generate_does_not_pass_request_timeout_and_ignores_configured_output_cap():
    provider = OllamaProvider()
    observed = {}

    def fake_post(path, payload):
        observed["path"] = path
        observed["payload"] = payload
        return {"message": {"role": "assistant", "content": "ok"}}

    provider._post = fake_post
    result = provider.generate(
        messages=[{"role": "user", "content": "Responda"}],
        model_name="qwen2.5:3b",
        configuration={"request_timeout_seconds": 1, "num_predict": 64},
    )

    assert result == "ok"
    assert observed["path"] == "/api/chat"
    assert observed["payload"]["options"]["num_predict"] == -1


def test_post_opens_response_without_a_timeout_argument():
    provider = OllamaProvider()
    response = io.BytesIO(b'{"message":{"content":"ok"}}')

    with patch("app.providers.ollama.request.urlopen", return_value=response) as urlopen:
        assert provider._post("/api/chat", {"model": "test"}) == {"message": {"content": "ok"}}

    assert urlopen.call_count == 1
    assert len(urlopen.call_args.args) == 1

