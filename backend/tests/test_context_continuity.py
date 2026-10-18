import pytest

from app.context.manager import build_context
from app.db.database import init_db
from app.memory.manager import remember
from app.models.conversation_repository import create_conversation
from app.models.message_repository import create_message
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_repository import create_task
from app.services.agent import run_agent


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "context-continuity.db")
    init_db()


def test_continuity_request_recovers_project_state_history_and_memory_provenance(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project(
        "Continuity",
        str(workspace),
        state={
            "last_decision": "usar FastAPI e SQLite",
            "next_step": "validar o endpoint de tarefas",
        },
    )
    model = create_model("Selected", "ollama", "selected:test")
    conversation = create_conversation("Continuity", model.id, project_id=project.id)
    create_message(conversation.id, "user", "Decidimos usar FastAPI e SQLite.")
    create_message(conversation.id, "assistant", "Próximo passo: validar o endpoint de tarefas.")
    remember(
        type="project_state",
        key="last_decision",
        value="No Mosaic, decidimos usar FastAPI e SQLite.",
        source="user",
        project_id=project.id,
        confidence=0.9,
    )
    for index in range(45):
        remember(
            type="user_claim",
            key=f"unrelated_{index}",
            value=f"registro sem relação {index} " + ("texto longo " * 30),
            source="user",
        )

    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": "Mosaic, lembra onde paramos na decisão de usar FastAPI e SQLite?"},
    )
    captured = []

    def decide(context):
        captured.append(context)
        return {"type": "final", "content": "Retomada baseada no contexto persistido."}

    result = run_agent(task.id, decide)
    assert result["status"] == "completed"
    assert len(captured) == 1
    context = captured[0]
    project_state = next(
        item["content"] for item in context
        if item["role"] == "system" and item["content"].startswith("Mosaic project state:")
    )
    memory_context = next(
        item["content"] for item in context
        if item["role"] == "system" and item["content"].startswith("Mosaic memory:")
    )
    flattened = "\n".join(item["content"] for item in context)

    assert "last_decision" in project_state
    assert "usar FastAPI e SQLite" in project_state
    assert "validar o endpoint de tarefas" in project_state
    assert "Decidimos usar FastAPI e SQLite." in flattened
    assert "Próximo passo: validar o endpoint de tarefas." in flattened
    assert "source=user" in memory_context
    assert "scope=project:" in memory_context
    assert "confidence=0.9" in memory_context
    assert "No Mosaic, decidimos usar FastAPI e SQLite." in memory_context
    assert "unrelated_44" in memory_context
    assert "unrelated_0" not in memory_context
    assert len(memory_context) <= 4000
    assert "records omitted or clipped" in memory_context


def test_build_context_keeps_memory_provenance_and_isolates_project_scope(tmp_path):
    first_workspace = tmp_path / "first"
    second_workspace = tmp_path / "second"
    first_workspace.mkdir()
    second_workspace.mkdir()
    first_project = create_project("First", str(first_workspace), state={"project": "first"})
    second_project = create_project("Second", str(second_workspace), state={"project": "second"})
    model = create_model("Selected", "ollama", "selected:test")
    first = create_conversation("First", model.id, project_id=first_project.id)
    second = create_conversation("Second", model.id, project_id=second_project.id)
    remember("project_state", "focus", "first project focus", "source:first", first_project.id)
    remember("project_state", "focus", "second project focus", "source:second", second_project.id)

    first_context = "\n".join(item["content"] for item in build_context(first.id))
    second_context = "\n".join(item["content"] for item in build_context(second.id))
    assert "first project focus" in first_context
    assert "source=source:first" in first_context
    assert "second project focus" not in first_context
    assert "second project focus" in second_context
    assert "source=source:second" in second_context
    assert "first project focus" not in second_context
