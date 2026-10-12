import re

from app.models.memory import Memory
from app.models.memory_repository import create_memory, list_memories


_SAVE_PREFIX = re.compile(
    r"^\\s*(?:mosaic[,! ]+)?(?:por favor[, ]+)?"
    r"(?:salve|salva|guarde|guarda|lembre(?:-se)?|registre)"
    r"(?:\\s+(?:essa|esta|a|isso|que))?\\s*[, :]*",
    re.IGNORECASE,
)


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


def save_explicit_memory(
    content: str,
    project_id: int | None = None,
) -> Memory | None:
    """Persist an explicit natural-language memory request without involving the model."""
    match = _SAVE_PREFIX.match(content)
    if not match:
        return None

    value = content[match.end():].strip(" \\t:,.!?")
    value = re.sub(r"^(?:que|o seguinte|a seguinte informação)\\s+", "", value, flags=re.IGNORECASE)
    if not value:
        return None

    normalized = value.casefold()
    if any(term in normalized for term in ("gosto de", "gosto muito de", "prefiro ", "não gosto de", "nao gosto de", "minha preferência", "minha preferencia")):
        memory_type = "user_preference"
        key = "preferencia"
    elif any(term in normalized for term in ("minha opinião", "minha opiniao", "eu acho", "na minha visão", "na minha visao", "acredito que", "minha hipótese", "minha hipotese")):
        memory_type = "user_claim"
        key = "opiniao"
    elif any(term in normalized for term in ("sempre responda", "sempre faça", "sempre faca", "lembre-se de", "lembre de", "quero que você", "quero que voce")):
        memory_type = "instruction"
        key = "instrucao"
    else:
        # A user-provided statement is a claim until independently verified.
        memory_type = "user_claim"
        key = "alegacao"

    return remember(
        type=memory_type,
        key=key,
        value=value,
        source="user",
        project_id=project_id,
    )


def get_project_memories(project_id: int | None) -> list[Memory]:
    if project_id is None:
        return []
    return list_memories(project_id)


def get_global_memories() -> list[Memory]:
    # list_memories(None) returns all records; keep only memories not tied to a project.
    return [memory for memory in list_memories() if memory.project_id is None]
