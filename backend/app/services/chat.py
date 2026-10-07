from collections.abc import Iterable

from app.context.manager import build_context
from app.models.conversation_repository import get_conversation
from app.models.message import Message
from app.models.message_repository import create_message
from app.models.repository import get_model
from app.providers.ollama import OllamaProvider


def _get_provider(provider_name: str):
    if provider_name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unsupported model provider: {provider_name}")


def chat(conversation_id: int, content: str) -> Message:
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")

    model = get_model(conversation.model_id)
    if model is None:
        raise ValueError("Model not found")

    create_message(conversation_id, "user", content)
    messages = build_context(conversation_id)

    provider = _get_provider(model.provider)
    response = provider.generate(
        messages=messages,
        model_name=model.model_name,
        configuration=model.configuration,
    )

    return create_message(conversation_id, "assistant", response)


def stream_chat(conversation_id: int, content: str) -> Iterable[str]:
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")

    model = get_model(conversation.model_id)
    if model is None:
        raise ValueError("Model not found")

    create_message(conversation_id, "user", content)
    messages = build_context(conversation_id)
    provider = _get_provider(model.provider)

    chunks: list[str] = []
    for chunk in provider.stream(
        messages=messages,
        model_name=model.model_name,
        configuration=model.configuration,
    ):
        chunks.append(chunk)
        yield chunk

    response = "".join(chunks).strip()
    if not response:
        raise RuntimeError("O modelo não retornou conteúdo na resposta.")
    create_message(conversation_id, "assistant", response)
