import pytest

from app.db.database import get_connection, init_db
from app.models.conversation_repository import create_conversation
from app.models.repository import create_model
from app.models.tool_call_repository import create_tool_call, get_tool_call
from app.models.tool_result_repository import get_tool_result
from app.services.tools import approve_tool_call, execute_tool_call, validate_tool_call
from app.tools import registry


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def _conversation():
    model = create_model("Test", "ollama", "test:model")
    return create_conversation("Tools", model.id)


def test_registry_contains_initial_tools() -> None:
    names = {tool.name for tool in registry.list()}
    assert {"filesystem", "terminal", "search", "calculator", "weather"} <= names


def test_tool_call_is_intent_until_approved() -> None:
    conversation = _conversation()
    call = create_tool_call(conversation.id, "calculator", {"expression": "2 + 3"})

    validate_tool_call(call)
    with pytest.raises(ValueError):
        execute_tool_call(call)

    approved = approve_tool_call(call)
    assert approved.status == "approved"


def test_calculator_execution_persists_result() -> None:
    conversation = _conversation()
    call = create_tool_call(conversation.id, "calculator", {"expression": "2 + 3"})
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "completed"
    assert result.data == {"result": 5}
    assert get_tool_call(call.id).status == "completed"
    assert get_tool_result(result.id) == result


def test_failed_tool_result_invariant() -> None:
    conversation = _conversation()
    call = create_tool_call(conversation.id, "calculator", {"expression": "unknown"})
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "failed"
    assert result.data is None
    assert result.error
