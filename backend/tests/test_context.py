import pytest

from app.context.manager import build_context
from app.db.database import get_connection, init_db
from app.memory.manager import remember
from app.models.conversation_repository import create_conversation
from app.models.message_repository import create_message
from app.models.repository import create_model
from app.models.task_repository import create_task
from app.models.tool_call_repository import create_tool_call
from app.models.tool_result_repository import create_tool_result


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


def test_context_limits_history_and_keeps_current_user_message_last() -> None:
    model = create_model("Qwen 3B", "ollama", "qwen3:3b")
    conversation = create_conversation("History limit", model.id)

    for index in range(25):
        create_message(conversation.id, "user", f"history-{index}")

    context = build_context(conversation.id)

    user_messages = [item["content"] for item in context if item["role"] == "user"]
    assert len(user_messages) == 21
    assert user_messages[:-1] == [f"history-{index}" for index in range(5, 25)]
    assert user_messages[-1] == "history-24"
    assert context[-1] == {"role": "user", "content": "history-24"}


def test_context_includes_current_task_and_tool_results() -> None:
    model = create_model("Qwen 3B", "ollama", "qwen3:3b")
    conversation = create_conversation("Task context", model.id)

    create_task(
        type="analysis",
        mode="create",
        conversation_id=conversation.id,
        status="executing",
        plan={"step": "analyze"},
    )
    tool_call = create_tool_call(
        conversation_id=conversation.id,
        tool_name="calculator",
        arguments={"expression": "2 + 2"},
        status="completed",
    )
    create_tool_result(
        tool_call.id,
        status="completed",
        data={"value": 4},
    )
    create_message(conversation.id, "user", "Qual foi o resultado?")

    context = build_context(conversation.id)

    assert any(
        item["role"] == "system" and "Mosaic current task:" in item["content"]
        for item in context
    )
    assert any(
        item["role"] == "tool"
        and "calculator" in item["content"]
        and '"value": 4' in item["content"]
        for item in context
    )
    assert context[-1] == {"role": "user", "content": "Qual foi o resultado?"}
