import pytest

from app.db.database import init_db
from app.models.memory_repository import create_memory, get_memory, list_memories


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def test_memory_creation_and_retrieval() -> None:
    memory = create_memory(
        type="user_preference",
        key="editor",
        value="VS Code",
        source="user",
        confidence=0.9,
    )

    stored = get_memory(memory.id)

    assert stored == memory


def test_memory_can_be_project_scoped() -> None:
    memory = create_memory(
        type="project_state",
        key="status",
        value="Memory implementation started",
        source="conversation",
        project_id=1,
    )

    assert list_memories(1) == [memory]
    assert list_memories(2) == []


@pytest.mark.parametrize("memory_type", [
    "user_fact",
    "user_preference",
    "user_claim",
    "project_state",
    "instruction",
])
def test_official_memory_types_are_allowed(memory_type: str) -> None:
    memory = create_memory(
        type=memory_type,
        key="key",
        value="value",
        source="user",
    )

    assert memory.type == memory_type


def test_invalid_memory_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid memory type"):
        create_memory("invalid", "key", "value", "user")


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_invalid_confidence_is_rejected(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        create_memory("user_fact", "key", "value", "user", confidence=confidence)
