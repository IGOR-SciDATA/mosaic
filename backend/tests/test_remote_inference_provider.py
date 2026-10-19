import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from app.providers.remote_inference import RemoteInferenceProvider


def test_remote_provider_requires_token(monkeypatch):
    monkeypatch.delenv("MOSAIC_REMOTE_INFERENCE_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="credentials are not configured"):
        RemoteInferenceProvider(base_url="http://localhost:8090", token="")


def test_remote_provider_rejects_public_http_endpoint():
    with pytest.raises(ValueError, match="must use HTTPS"):
        RemoteInferenceProvider(base_url="http://example.com:8090", token="test-token")


def test_remote_provider_rejects_credentials_embedded_in_url():
    with pytest.raises(ValueError, match="URL is invalid"):
        RemoteInferenceProvider(base_url="https://user:pass@example.com", token="test-token")


def test_remote_provider_generate_uses_existing_contract(monkeypatch):
    provider = RemoteInferenceProvider(base_url="http://localhost:8090", token="test-token")
    seen = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"model":"qwen2.5:3b","output_text":"hello"}'

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = req.headers
        seen["payload"] = json.loads(req.data)
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("app.providers.remote_inference.request.urlopen", fake_urlopen)
    result = provider.generate(
        [{"role": "user", "content": "hello"}],
        "qwen2.5:3b",
        {"request_timeout_seconds": 12, "temperature": 0.2},
    )
    assert result == "hello"
    assert seen["url"] == "http://localhost:8090/v1/inference"
    assert seen["payload"]["messages"] == [{"role": "user", "content": "hello"}]
    assert seen["payload"]["temperature"] == 0.2
    assert seen["timeout"] == 12


def test_remote_provider_sanitizes_http_errors(monkeypatch):
    provider = RemoteInferenceProvider(base_url="http://localhost:8090", token="secret-token")

    def fake_urlopen(*args, **kwargs):
        raise HTTPError("http://localhost:8090", 401, "bad", {}, None)

    monkeypatch.setattr("app.providers.remote_inference.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="authentication failed") as exc:
        provider.generate([{"role": "user", "content": "hi"}], "model", {})
    assert "secret-token" not in str(exc.value)


def test_remote_provider_rejects_unknown_message_roles():
    provider = RemoteInferenceProvider(base_url="http://localhost:8090", token="test-token")
    with pytest.raises(ValueError, match="At least one text message"):
        provider.generate([{"role": "tool", "content": "do something"}], "model", {})
