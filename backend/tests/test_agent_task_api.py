import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.tasks import (
    TaskPlanUpdate,
    TaskStart,
    confirm_task_plan_endpoint,
    edit_task_plan_endpoint,
    run_task_endpoint,
    start_agent_task_endpoint,
)
from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.message_repository import list_messages
from app.models.repository import create_model
from app.models.task_repository import create_task, get_task
from app.services.task_coordinator import validate_coordinator_plan


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "agent-api.db")
    init_db()


def _conversation():
    model = create_model("Test", "ollama", "test:model")
    return create_conversation("Agent API", model.id)


def _valid_plan(goal="Analise o projeto"):
    return {
        "goal": goal,
        "subtasks": [{
            "id": "analyze",
            "goal": goal,
            "profile": "research",
            "depends_on": [],
            "inputs": [],
            "allowed_tools": ["filesystem"],
            "acceptance_criteria": [{"type": "non_empty"}],
        }],
    }


def test_start_agent_persists_validated_plan_without_executing(monkeypatch):
    conversation = _conversation()
    background = BackgroundTasks()
    monkeypatch.setattr("app.api.tasks.generate_coordinator_plan", lambda _conversation_id, goal: _valid_plan(goal))

    task = start_agent_task_endpoint(
        TaskStart(conversation_id=conversation.id, goal="Analise o projeto"),
        background,
    )

    assert task.mode == "agent"
    assert task.status == "awaiting_approval"
    assert task.plan["goal"] == "Analise o projeto"
    assert task.plan["plan_version"] == 1
    assert task.plan["plan_confirmed"] is False
    assert task.plan["subtasks"][0]["profile"] == "research"
    assert task.plan["subtasks"][0]["allowed_tools"] == ["filesystem"]
    assert task.conversation_id == conversation.id
    assert get_task(task.id).status == "awaiting_approval"
    messages = list_messages(conversation.id)
    assert messages[-1].role == "user"
    assert messages[-1].content == "Analise o projeto"
    assert len(background.tasks) == 0


def test_plan_edit_is_revalidated_and_increments_version(monkeypatch):
    conversation = _conversation()
    monkeypatch.setattr("app.api.tasks.generate_coordinator_plan", lambda _conversation_id, goal: _valid_plan(goal))
    task = start_agent_task_endpoint(
        TaskStart(conversation_id=conversation.id, goal="Analise o projeto"), BackgroundTasks()
    )
    edited = _valid_plan()
    edited["subtasks"][0]["goal"] = "Analisar e verificar o projeto"
    updated = edit_task_plan_endpoint(task.id, TaskPlanUpdate(plan=edited))
    assert updated.plan["plan_version"] == 2
    assert updated.plan["plan_confirmed"] is False
    assert updated.plan["subtasks"][0]["allowed_tools"] == ["filesystem"]


def test_invalid_edited_plan_is_rejected_before_execution(monkeypatch):
    conversation = _conversation()
    monkeypatch.setattr("app.api.tasks.generate_coordinator_plan", lambda _conversation_id, goal: _valid_plan(goal))
    task = start_agent_task_endpoint(
        TaskStart(conversation_id=conversation.id, goal="Analise o projeto"), BackgroundTasks()
    )
    invalid = _valid_plan()
    invalid["subtasks"][0]["depends_on"] = ["missing"]
    with pytest.raises(HTTPException) as exc:
        edit_task_plan_endpoint(task.id, TaskPlanUpdate(plan=invalid))
    assert exc.value.status_code == 422
    assert get_task(task.id).status == "awaiting_approval"


def test_plan_must_declare_registered_tools_before_confirmation():
    missing = _valid_plan()
    del missing["subtasks"][0]["allowed_tools"]
    with pytest.raises(ValueError, match="must declare allowed_tools"):
        validate_coordinator_plan(missing, require_tool_declarations=True)


def test_plan_rejects_unknown_tool_names():
    invalid = _valid_plan()
    invalid["subtasks"][0]["allowed_tools"] = ["made_up_tool"]
    with pytest.raises(ValueError, match="unknown tools"):
        validate_coordinator_plan(invalid, require_tool_declarations=True)


def test_confirmation_schedules_only_the_validated_plan(monkeypatch):
    conversation = _conversation()
    monkeypatch.setattr("app.api.tasks.generate_coordinator_plan", lambda _conversation_id, goal: _valid_plan(goal))
    task = start_agent_task_endpoint(
        TaskStart(conversation_id=conversation.id, goal="Analise o projeto"), BackgroundTasks()
    )
    background = BackgroundTasks()
    confirmed = confirm_task_plan_endpoint(task.id, background)
    assert confirmed.status == "executing"
    assert confirmed.plan["plan_confirmed"] is True
    assert len(background.tasks) == 1


def test_start_agent_rejects_blank_goal():
    conversation = _conversation()
    with pytest.raises(HTTPException) as exc:
        start_agent_task_endpoint(
            TaskStart(conversation_id=conversation.id, goal="   "),
            BackgroundTasks(),
        )
    assert exc.value.status_code == 422


def test_run_endpoint_rejects_non_agent_task():
    conversation = _conversation()
    task = create_task(
        type="generic", mode="create", conversation_id=conversation.id
    )
    with pytest.raises(HTTPException) as exc:
        run_task_endpoint(task.id, BackgroundTasks())
    assert exc.value.status_code == 409
