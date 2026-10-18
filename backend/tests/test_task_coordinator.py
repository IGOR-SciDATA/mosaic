import pytest

from app.api.tasks import coordinate_task_endpoint
from app.db.database import get_connection, init_db
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task, get_task, list_tasks
from app.services.agent_profiles import validate_agent_profile_snapshot
from app.services.task_coordinator import run_coordinated_task


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "coordinator.db")
    init_db()


def _specs():
    return [
        {
            "id": "architecture",
            "profile": "architecture",
            "goal": "Produce architecture result",
            "depends_on": [],
            "acceptance_criteria": [{"type": "contains", "value": "architecture result"}],
        },
        {
            "id": "backend",
            "profile": "backend",
            "goal": "Use the architecture result and produce backend result",
            "depends_on": ["architecture"],
            "acceptance_criteria": [{"type": "contains", "value": "backend result"}],
        },
        {
            "id": "qa",
            "profile": "qa",
            "goal": "Review backend result and produce qa result",
            "depends_on": ["backend"],
            "acceptance_criteria": [{"type": "contains", "value": "qa result"}],
        },
    ]


def _parent_task(tmp_path, plan):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Coordinator", str(workspace))
    model = create_model("Selected", "ollama", "selected:test")
    conversation = create_conversation("Coordinator", model.id, project_id=project.id)
    return create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan=plan,
    )


def test_three_dependent_profile_tasks_run_sequentially_and_integrate_results(tmp_path):
    parent = _parent_task(
        tmp_path,
        {
            "goal": "Coordinate architecture, backend and QA",
            "subtasks": _specs(),
        },
    )
    execution_order = []

    def decider_factory(child):
        profile = child.plan["agent_profile_snapshot"]["name"]

        def decide(context):
            execution_order.append(profile)
            flattened = "\n".join(item["content"] for item in context)
            if profile == "architecture":
                return {"type": "final", "content": "architecture result"}
            if profile == "backend":
                assert "architecture result" in flattened
                return {"type": "final", "content": "backend result based on architecture result"}
            assert "backend result based on architecture result" in flattened
            return {"type": "final", "content": "qa result: backend result verified"}

        return decide

    completed = run_coordinated_task(parent.id, decider_factory=decider_factory)

    assert completed.status == "completed"
    assert execution_order == ["architecture", "backend", "qa"]
    assert "architecture result" in completed.result["output"]
    assert "backend result" in completed.result["output"]
    assert "qa result" in completed.result["output"]
    children = completed.plan["coordinator"]["children"]
    assert set(children) == {"architecture", "backend", "qa"}

    architecture = get_task(children["architecture"])
    backend = get_task(children["backend"])
    qa = get_task(children["qa"])
    assert architecture.status == backend.status == qa.status == "completed"
    assert validate_agent_profile_snapshot(architecture.plan["agent_profile_snapshot"])
    assert validate_agent_profile_snapshot(backend.plan["agent_profile_snapshot"])
    assert validate_agent_profile_snapshot(qa.plan["agent_profile_snapshot"])
    assert backend.plan["depends_on_task_ids"] == [architecture.id]
    assert backend.plan["dependency_results"]["architecture"]["output"] == "architecture result"
    assert qa.plan["depends_on_task_ids"] == [backend.id]
    assert qa.plan["dependency_results"]["backend"]["output"] == "backend result based on architecture result"
    assert len(completed.result["coordinator"]["subtasks"]) == 3

    events = list_task_events(parent.id)
    assert sum(event.event_name == "coordinator.subtask_completed" for event in events) == 3
    assert any(event.event_name == "coordinator.completed" for event in events)
    with get_connection() as connection:
        tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "task_dependencies" not in tables


def test_coordinator_rejects_dependency_cycles_before_creating_children(tmp_path):
    parent = _parent_task(
        tmp_path,
        {
            "goal": "Invalid cycle",
            "subtasks": [
                {
                    "id": "first",
                    "profile": "architecture",
                    "goal": "First",
                    "depends_on": ["second"],
                    "acceptance_criteria": [{"type": "non_empty"}],
                },
                {
                    "id": "second",
                    "profile": "qa",
                    "goal": "Second",
                    "depends_on": ["first"],
                    "acceptance_criteria": [{"type": "non_empty"}],
                },
            ],
        },
    )
    with pytest.raises(ValueError, match="cycle"):
        run_coordinated_task(parent.id)
    assert get_task(parent.id).status == "pending"
    assert len(list_tasks(conversation_id=parent.conversation_id)) == 1


def test_coordinate_endpoint_schedules_existing_task_engine(tmp_path):
    parent = _parent_task(
        tmp_path,
        {"goal": "Coordinate", "subtasks": _specs()},
    )
    from fastapi import BackgroundTasks

    background = BackgroundTasks()
    result = coordinate_task_endpoint(parent.id, background)
    assert result.status == "planning"
    assert len(background.tasks) == 1
    assert background.tasks[0].func is run_coordinated_task
    assert get_task(parent.id).status == "planning"
