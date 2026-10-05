import pytest

from app.context.manager import build_context
from app.db.database import get_connection, init_db
from app.memory.manager import remember
from app.models.conversation_repository import create_conversation
from app.models.message_repository import create_message
from app.models.repository import create_model


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def test_context_includes_project_state_memory_before_history() -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO projects (name, workspace, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (
                "Mosaic",
                "/tmp/mosaic",
                '{"phase":"project"}',
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()

    model = create_model("Qwen 3B", "ollama", "qwen3:3b")
    conversation = create_conversation("Context test", model.id, project_id=1)

    remember(
        type="project_state",
        key="status",
        value="Memory implementation started",
        source="conversation",
        project_id=1,
    )
    create_message(conversation.id, "user", "Onde paramos?")

    context = build_context(conversation.id)

    assert context[0] == {
        "role": "system",
        "content": "Mosaic project state:\\n{'phase': 'project'}",
    }
    assert context[1] == {
        "role": "system",
        "content": "Mosaic memory:\n- [project_state] status: Memory implementation started",
    }
    assert context[2] == {"role": "user", "content": "Onde paramos?"}
