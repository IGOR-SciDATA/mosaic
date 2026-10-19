from app.db.database import get_connection, init_db
from app.models.conversation_repository import create_conversation, delete_conversation
from app.models.message_repository import create_message
from app.models.project_repository import create_project, delete_project, get_project
from app.models.repository import create_model
from app.models.task_repository import create_task, update_task
from app.models.memory_repository import create_memory
import pytest

@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "delete-test.db")
    init_db()

def _model():
    return create_model("Test", "ollama", "test-model")

def _finish_task(task_id):
    update_task(task_id, status="planning")
    update_task(task_id, status="executing")
    update_task(task_id, status="completed")

def _counts(table, where="", params=()):
    with get_connection() as connection:
        return connection.execute("SELECT COUNT(*) FROM " + table + (" WHERE " + where if where else ""), params).fetchone()[0]

def test_delete_conversation_removes_messages_and_task_records():
    project = create_project("Project", "/tmp/project")
    model = _model()
    conversation = create_conversation("Conversation", model.id, project.id)
    create_message(conversation.id, "user", "persisted message")
    task = create_task("generic", "agent", conversation_id=conversation.id, project_id=project.id)
    _finish_task(task.id)
    assert delete_conversation(conversation.id) is True
    assert _counts("conversations", "id = ?", (conversation.id,)) == 0
    assert _counts("messages", "conversation_id = ?", (conversation.id,)) == 0
    assert _counts("tasks", "id = ?", (task.id,)) == 0
    assert _counts("task_events", "task_id = ?", (task.id,)) == 0

def test_delete_project_preserves_conversations_and_memories_as_unassigned_records():
    project = create_project("Delete me", "/tmp/delete-me")
    other = create_project("Keep me", "/tmp/keep-me")
    model = _model()
    conversation = create_conversation("Project chat", model.id, project.id)
    other_conversation = create_conversation("Other chat", model.id, other.id)
    create_message(conversation.id, "user", "project message")
    create_message(other_conversation.id, "user", "keep message")
    create_memory("project_state", "key", "value", "test", project_id=project.id)
    task = create_task("generic", "agent", conversation_id=conversation.id, project_id=project.id)
    _finish_task(task.id)
    assert delete_project(project.id) is True
    assert get_project(project.id) is None
    assert _counts("conversations", "id = ? AND project_id IS NULL", (conversation.id,)) == 1
    assert _counts("messages", "conversation_id = ?", (conversation.id,)) == 1
    assert _counts("tasks", "id = ? AND project_id IS NULL", (task.id,)) == 1
    assert _counts("memories", "project_id IS NULL AND key = ?", ("key",)) == 1
    assert get_project(other.id) is not None
    assert _counts("conversations", "id = ? AND project_id = ?", (other_conversation.id, other.id)) == 1
    assert _counts("messages", "conversation_id = ?", (other_conversation.id,)) == 1

def test_cannot_delete_conversation_with_active_task():
    project = create_project("Active", "/tmp/active")
    conversation = create_conversation("Running", _model().id, project.id)
    create_task("generic", "agent", conversation_id=conversation.id, project_id=project.id)
    with pytest.raises(ValueError, match="active Tasks"):
        delete_conversation(conversation.id)
    assert _counts("conversations", "id = ?", (conversation.id,)) == 1

def test_cannot_delete_project_with_active_task():
    project = create_project("Active project", "/tmp/active-project")
    conversation = create_conversation("Running", _model().id, project.id)
    create_task("generic", "agent", conversation_id=conversation.id, project_id=project.id)
    with pytest.raises(ValueError, match="active Tasks"):
        delete_project(project.id)
    assert get_project(project.id) is not None
    assert _counts("conversations", "id = ?", (conversation.id,)) == 1
