from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.message_repository import create_message
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_repository import create_task, get_task, update_task
from app.models.tool_call_repository import create_tool_call, get_tool_call, list_tool_calls
from app.models.tool_result_repository import list_tool_results
from app.services.agent import _tool_context, run_agent
from app.services.tools import approve_tool_call, execute_tool_call

@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()

def _conversation(project_id=None):
    model = create_model("Test", "ollama", "test:model")
    return create_conversation("Agent", model.id, project_id=project_id)

def _task(plan=None, project_id=None):
    conversation = _conversation(project_id)
    return create_task(type="generic", mode="agent", conversation_id=conversation.id, project_id=project_id, plan=plan)

def test_agent_auto_paginates_reads_and_uses_task_scoped_context(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Pagination", str(workspace))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "Documento.md").write_text(
        "\n".join(f"linha {number}" for number in range(1, 191)),
        encoding="utf-8",
    )
    task = _task(plan={"goal": "leia Documento.md"}, project_id=project.id)
    create_message(task.conversation_id, "user", "leia Documento.md")
    create_message(task.conversation_id, "assistant", "resposta antiga irrelevante")

    observed_contexts = []

    def decide(context):
        observed_contexts.append(context)
        if len(observed_contexts) == 1:
            return {
                "type": "tool_call",
                "tool": "filesystem",
                "arguments": {"operation": "read", "path": "Documento.md"},
            }
        assert [message["content"] for message in context if message.get("role") == "user"] == [
            "leia Documento.md"
        ]
        assert any("resposta antiga irrelevante" in message.get("content", "") for message in context)
        assert any("linha 190" in message.get("content", "") for message in context)
        read_calls = [
            call for call in list_tool_calls(task.conversation_id)
            if call.task_id == task.id and call.tool_name == "filesystem"
            and call.arguments.get("operation") == "read"
        ]
        assert len(read_calls) == 3
        return {"type": "final", "content": "Li o documento completo."}

    result = run_agent(task.id, decide)

    assert result["status"] == "completed"
    assert len(observed_contexts) == 2


def test_agent_does_not_complete_file_creation_goal_without_verified_artifact():
    task = _task(plan={"goal": "crie um novo arquivo .md com um resumo"})
    result = run_agent(
        task.id,
        lambda context: {"type": "final", "content": "Criei o resumo."},
        iteration_limit=1,
    )
    assert result["status"] == "failed"
    assert "iteration limit" in result["error"].lower()
    assert get_task(task.id).status == "failed"


def test_agent_does_not_complete_summary_without_reading_named_source(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Source validation", str(workspace))
    task = _task(
        plan={"goal": "leia Documento.md e crie um novo arquivo .md com um resumo"},
        project_id=project.id,
    )
    output_create = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "create", "path": "Resumo.md", "content": "# Resumo\\n\\nTexto sem fonte."},
        task_id=task.id,
    )
    assert execute_tool_call(approve_tool_call(output_create)).status == "completed"

    result = run_agent(
        task.id,
        lambda context: {"type": "final", "content": "Criei o resumo."},
        iteration_limit=1,
    )
    assert result["status"] == "failed"
    assert get_task(task.id).status == "failed"


def test_agent_completes_file_creation_goal_only_after_artifact_is_verified(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Artifact validation", str(workspace))
    task = _task(
        plan={"goal": "leia Documento.md e crie um novo arquivo .md com um resumo"},
        project_id=project.id,
    )
    source_create = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "create", "path": "Documento.md", "content": "\n".join(f"linha {number}" for number in range(1, 101))},
        task_id=task.id,
    )
    assert execute_tool_call(approve_tool_call(source_create)).status == "completed"
    source_read = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "read", "path": "Documento.md"},
        task_id=task.id,
    )
    first_read_result = execute_tool_call(approve_tool_call(source_read))
    assert first_read_result.status == "completed"
    source_read_next = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "read", "path": "Documento.md", "start_line": 81, "max_lines": 80},
        task_id=task.id,
    )
    second_read_result = execute_tool_call(approve_tool_call(source_read_next))
    assert second_read_result.status == "completed"
    output_create = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "create", "path": "Resumo.md", "content": "# Resumo\n\nConteúdo."},
        task_id=task.id,
    )
    tool_result = execute_tool_call(approve_tool_call(output_create))
    assert tool_result.status == "completed"

    result = run_agent(
        task.id,
        lambda context: {"type": "final", "content": "Criei o resumo."},
        iteration_limit=1,
    )
    assert result["status"] == "completed"
    assert result["artifact"]["path"] == "Resumo.md"
    assert result["artifact"]["bytes"] > 0
    assert (workspace / "Resumo.md").is_file()


def test_tool_observation_is_bounded_and_marks_truncation():
    result = SimpleNamespace(status="completed", data={"content": "x" * 20_000}, error=None)
    observation = _tool_context(1, result)
    assert len(observation["content"]) < 13_000
    assert "observação truncada pelo Core" in observation["content"]


def test_agent_returns_native_tool_result_in_protocol_shape():
    task = _task()
    observed = []

    def decide(context):
        observed.append(context)
        if len(observed) == 1:
            return {
                "type": "tool_call",
                "tool": "calculator",
                "arguments": {"expression": "2 + 3"},
                "_native_message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "calculator",
                            "arguments": {"expression": "2 + 3"},
                        }
                    }],
                },
            }
        assert any(message.get("role") == "assistant" and "tool_calls" in message for message in context)
        tool_result = next(message for message in context if message.get("role") == "tool")
        assert tool_result["tool_name"] == "calculator"
        assert "5" in tool_result["content"]
        return {"type": "final", "content": "O resultado é 5."}

    result = run_agent(task.id, decide)

    assert result["status"] == "completed"
    assert len(observed) == 2


def test_agent_runs_tool_then_returns_final():
    task = _task()
    decisions = iter([
        {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "2 + 3"}},
        {"type": "final", "content": "O resultado é 5."},
    ])
    result = run_agent(task.id, lambda context: next(decisions))
    assert result["status"] == "completed"
    assert result["iterations"] == 2
    assert get_task(task.id).status == "completed"

def test_agent_passes_tool_observation_to_next_decision():
    task = _task()
    observed = []
    def decide(context):
        observed.append(list(context))
        if len(observed) == 1:
            return {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "7 * 6"}}
        assert any(message["role"] == "system" and "42" in message["content"] for message in context)
        return {"type": "final", "content": "42"}
    result = run_agent(task.id, decide)
    assert result["status"] == "completed"
    assert len(observed) == 2

def test_agent_stops_for_approval_required_tool():
    task = _task()
    result = run_agent(
        task.id,
        lambda context: {
            "type": "tool_call",
            "tool": "filesystem",
            "arguments": {"operation": "create", "path": "Resumo.md", "content": "# Resumo"},
        },
    )
    assert result["status"] == "awaiting_approval"
    assert get_task(task.id).status == "awaiting_approval"
    call = get_tool_call(result["tool_call_id"])
    assert call.status == "pending"
    assert list_tool_results(call.id) == []

def test_agent_respects_iteration_limit():
    task = _task()
    result = run_agent(task.id, lambda context: {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "1 + 1"}}, iteration_limit=2)
    assert result["status"] == "failed"
    assert result["iterations"] == 2
    assert get_task(task.id).status == "failed"

def test_agent_can_be_cancelled_before_tool_execution():
    task = _task()
    calls = 0
    def decide(context):
        nonlocal calls
        calls += 1
        update_task(task.id, status="cancelled")
        return {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "1 + 1"}}
    result = run_agent(task.id, decide)
    assert result["status"] == "cancelled"
    assert calls == 1


def test_agent_blocks_consecutive_duplicate_successful_tool_call():
    task = _task()
    decisions = iter([
        {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "7 * 6"}},
        {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "7 * 6"}},
        {"type": "final", "content": "O resultado é 42."},
    ])
    result = run_agent(task.id, lambda context: next(decisions))
    calls = [call for call in list_tool_calls(task.conversation_id) if call.task_id == task.id]
    assert result["status"] == "completed"
    assert len(calls) == 1
