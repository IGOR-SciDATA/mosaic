from app.models.memory import Memory
from app.models.memory_repository import create_memory, list_memories


def remember(
    type: str,
    key: str,
    value: str,
    source: str,
    project_id: int | None = None,
    confidence: float | None = None,
) -> Memory:
    return create_memory(
        type=type,
        key=key,
        value=value,
        source=source,
        project_id=project_id,
        confidence=confidence,
    )


def get_project_memories(project_id: int | None) -> list[Memory]:
    if project_id is None:
        return []
    return list_memories(project_id)
