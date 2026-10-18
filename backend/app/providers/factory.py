"""Explicit ModelProvider registry.

Provider identity is selected by the persisted Model.provider field. Unknown providers
fail closed; this registry never silently falls back to Ollama or another model.
"""

from collections.abc import Callable
from typing import Any

from app.providers.base import ModelProvider
from app.providers.ollama import OllamaProvider

ProviderFactory = Callable[[dict[str, Any]], ModelProvider]


def _create_ollama(_configuration: dict[str, Any]) -> ModelProvider:
    # Keep provider endpoint configuration out of generic model settings until a
    # dedicated, validated connection-settings contract is approved.
    return OllamaProvider()


_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "ollama": _create_ollama,
}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a provider implementation for application startup/tests.

    Registration is explicit; the model database cannot import arbitrary code.
    """
    normalized = name.strip().lower() if isinstance(name, str) else ""
    if not normalized:
        raise ValueError("Provider name must be a non-empty string")
    if not callable(factory):
        raise ValueError("Provider factory must be callable")
    _PROVIDER_FACTORIES[normalized] = factory


def create_provider(provider_name: str, configuration: dict[str, Any] | None = None) -> ModelProvider:
    """Resolve a concrete provider by its persisted identifier, without fallback."""
    normalized = provider_name.strip().lower() if isinstance(provider_name, str) else ""
    if not normalized:
        raise ValueError("Model provider must be a non-empty string")
    factory = _PROVIDER_FACTORIES.get(normalized)
    if factory is None:
        raise ValueError(f"Unsupported model provider: {normalized}")
    return factory(configuration or {})


def resolve_model_provider(model: Any) -> ModelProvider:
    """Validate the selected model and return its explicitly configured provider."""
    if model is None:
        raise ValueError("Model not found")
    if not getattr(model, "enabled", False):
        raise ValueError("Selected model is disabled")
    provider_name = getattr(model, "provider", None)
    configuration = getattr(model, "configuration", {})
    if not isinstance(configuration, dict):
        raise ValueError("Selected model configuration must be an object")
    return create_provider(provider_name, configuration)
