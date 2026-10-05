from app.memory.manager import get_project_memories
from app.models.conversation_repository import get_conversation
from app.models.message_repository import list_messages


def build_context(conversation_id: int) -> list[dict[str, str]]:
    """Build deterministic MVP context from project memory and conversation history."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")

    context: list[dict[str, str]] = []

    memories = get_project_memories(conversation.project_id)
    if memories:
        memory_lines = [
            f"- [{memory.type}] {memory.key}: {memory.value}"
            for memory in memories
        ]
        context.append({
            "role": "system",
            "content": "Mosaic memory:\n" + "\n".join(memory_lines),
        })

    context.extend(
        {"role": message.role, "content": message.content}
        for message in list_messages(conversation_id)
        if message.role in {"system", "user", "assistant"}
    )

    return context
