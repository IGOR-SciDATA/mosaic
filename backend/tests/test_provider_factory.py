from types import SimpleNamespace

import pytest

from app.providers.factory import create_provider, resolve_model_provider


def test_registered_ollama_provider_is_selected_explicitly():
    provider = create_provider("ollama")
    from app.providers.ollama import OllamaProvider

    assert isinstance(provider, OllamaProvider)


def test_registered_openai_provider_is_selected_explicitly():
    from app.providers.openai import OpenAIProvider

    assert isinstance(create_provider("openai"), OpenAIProvider)


def test_unknown_provider_fails_without_silent_ollama_fallback():
    with pytest.raises(ValueError, match="Unsupported model provider: unknown-provider"):
        create_provider("unknown-provider")


def test_selected_model_provider_is_resolved_from_persisted_model(monkeypatch):
    import app.providers.factory as factory

    sentinel = object()
    monkeypatch.setitem(factory._PROVIDER_FACTORIES, "test-provider", lambda configuration: sentinel)
    model = SimpleNamespace(
        enabled=True,
        provider="test-provider",
        configuration={"temperature": 0.2},
    )

    assert resolve_model_provider(model) is sentinel


def test_disabled_model_is_rejected_before_provider_resolution():
    model = SimpleNamespace(
        enabled=False,
        provider="ollama",
        configuration={},
    )

    with pytest.raises(ValueError, match="Selected model is disabled"):
        resolve_model_provider(model)


def test_invalid_model_configuration_is_rejected():
    model = SimpleNamespace(
        enabled=True,
        provider="ollama",
        configuration=["not", "an", "object"],
    )

    with pytest.raises(ValueError, match="configuration must be an object"):
        resolve_model_provider(model)
