from app.models.message_repository import list_messages


def build_context(conversation_id: int) -> list[dict[str, str]]:
    """Build the deterministic MVP context from the conversation history."""
    return [
        {"role": message.role, "content": message.content}
        for message in list_messages(conversation_id)
        if message.role in {"system", "user", "assistant"}
    ]
