import pytest

from app.context.manager import build_context
from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.message_repository import create_message
from app.models.repository import create_model


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def test_context_builds_deterministic_conversation_history() -> None:
    model = create_model("Qwen 3B", "ollama", "qwen3:3b")
    conversation = create_conversation("Context test", model.id)

    create_message(conversation.id, "system", "Voce e o Mosaic.")
    create_message(conversation.id, "user", "Primeira")
    create_message(conversation.id, "assistant", "Resposta")
    create_message(conversation.id, "tool", "resultado interno")
    create_message(conversation.id, "user", "Segunda")

    assert build_context(conversation.id) == [
        {"role": "system", "content": "Voce e o Mosaic."},
        {"role": "user", "content": "Primeira"},
        {"role": "assistant", "content": "Resposta"},
        {"role": "user", "content": "Segunda"},
    ]
