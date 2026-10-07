import pytest
from fastapi.testclient import TestClient

from app.db.database import init_db
from app.main import app
from app.memory.manager import remember
from app.models.message_repository import list_messages
from app.models.project_repository import create_project
from app.models.repository import create_model


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _conversation(client: TestClient) -> int:
    model = create_model("Qwen 3B", "ollama", "qwen3:3b")
    response = client.post(
        "/conversations",
        json={"title": "Chat test", "model_id": model.id},
    )
    return response.json()["id"]


def test_chat_flow_persists_user_and_assistant_messages(client, monkeypatch) -> None:
    conversation_id = _conversation(client)

    def fake_generate(self, messages, model_name, configuration):
        assert messages == [{"role": "user", "content": "Olá"}]
        assert model_name == "qwen3:3b"
        return "Olá! Como posso ajudar?"

    monkeypatch.setattr("app.services.chat.OllamaProvider.generate", fake_generate)

    response = client.post(
        f"/conversations/{conversation_id}/chat",
        json={"content": "Olá"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "assistant"
    assert response.json()["content"] == "Olá! Como posso ajudar?"

    messages = list_messages(conversation_id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.content for message in messages] == [
        "Olá",
        "Olá! Como posso ajudar?",
    ]


def test_chat_flow_uses_previous_history(client, monkeypatch) -> None:
    conversation_id = _conversation(client)
    calls = []

    def fake_generate(self, messages, model_name, configuration):
        calls.append(messages)
        return "Resposta"

    monkeypatch.setattr("app.services.chat.OllamaProvider.generate", fake_generate)

    client.post(f"/conversations/{conversation_id}/chat", json={"content": "Primeira"})
    client.post(f"/conversations/{conversation_id}/chat", json={"content": "Segunda"})

    assert calls[1] == [
        {"role": "user", "content": "Primeira"},
        {"role": "assistant", "content": "Resposta"},
        {"role": "user", "content": "Segunda"},
    ]


def test_chat_stream_returns_sse_and_persists_response(client, monkeypatch) -> None:
    conversation_id = _conversation(client)

    def fake_stream(self, messages, model_name, configuration):
        yield "Olá "
        yield "em "
        yield "stream"

    monkeypatch.setattr("app.services.chat.OllamaProvider.stream", fake_stream)

    response = client.post(
        f"/conversations/{conversation_id}/chat/stream",
        json={"content": "Oi"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: "Olá "' in response.text
    assert 'data: "em "' in response.text
    assert 'data: "stream"' in response.text
    assert "data: [DONE]" in response.text

    messages = list_messages(conversation_id)
    assert [message.content for message in messages] == ["Oi", "Olá em stream"]


def test_chat_returns_404_for_unknown_conversation(client) -> None:
    response = client.post(
        "/conversations/999999/chat",
        json={"content": "Olá"},
    )

    assert response.status_code == 404


def test_chat_passes_project_state_and_memory_to_provider(client, monkeypatch) -> None:
    project = create_project(
        name="Guitar Livre",
        workspace="/tmp/guitar-livre",
        state={"phase": "development"},
    )
    model = create_model("Qwen 3B", "ollama", "qwen3:3b")
    conversation = client.post(
        "/conversations",
        json={
            "title": "Context integration",
            "model_id": model.id,
            "project_id": project.id,
        },
    ).json()

    remember(
        type="project_state",
        key="focus",
        value="Integrar o contexto do projeto",
        source="conversation",
        project_id=project.id,
    )

    captured = {}

    def fake_generate(self, messages, model_name, configuration):
        captured["messages"] = messages
        return "Contexto recebido"

    monkeypatch.setattr("app.services.chat.OllamaProvider.generate", fake_generate)

    response = client.post(
        f"/conversations/{conversation['id']}/chat",
        json={"content": "Onde estamos?"},
    )

    assert response.status_code == 200
    assert captured["messages"][0] == {
        "role": "system",
        "content": "Mosaic project state:\n{'phase': 'development'}",
    }
    assert captured["messages"][1] == {
        "role": "system",
        "content": "Mosaic memory:\n- [project_state] focus: Integrar o contexto do projeto",
    }
    assert captured["messages"][-1] == {
        "role": "user",
        "content": "Onde estamos?",
    }
