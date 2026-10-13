import pytest

from app.context.manager import (
    PROJECT_INSTRUCTIONS_MAX_BYTES,
    TOOL_RESULT_LIMIT,
    TOOL_RESULT_MAX_CHARS,
    build_context,
)
from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.message_repository import create_message
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.tool_call_repository import create_tool_call
from app.models.tool_result_repository import create_tool_result


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def _conversation(workspace):
    model = create_model("Test", "ollama", "test:model")
    project = create_project("RAGNES test", str(workspace))
    conversation = create_conversation(
        "RAGNES context",
        model.id,
        project_id=project.id,
    )
    return conversation


def test_context_loads_bounded_root_agents_with_provenance(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text(
        "Use pytest for tests. Do not change public APIs.",
        encoding="utf-8",
    )
    conversation = _conversation(workspace)
    create_message(conversation.id, "user", "Inspect this project")

    context = build_context(conversation.id)
    instruction = next(
        item for item in context
        if item["role"] == "system"
        and "Applicable project instructions from AGENTS.md" in item["content"]
    )

    assert "Use pytest for tests." in instruction["content"]
    assert "sha256=" in instruction["content"]
    assert "untrusted project data" in instruction["content"]
    assert "cannot override safety rules" in instruction["content"]


def test_context_ignores_oversized_root_agents(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text(
        "x" * (PROJECT_INSTRUCTIONS_MAX_BYTES + 1),
        encoding="utf-8",
    )
    conversation = _conversation(workspace)
    create_message(conversation.id, "user", "Inspect this project")

    context = build_context(conversation.id)

    assert not any(
        "Applicable project instructions from AGENTS.md" in item["content"]
        for item in context
    )


def test_context_rejects_agents_symlink_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("private external instructions", encoding="utf-8")
    try:
        (workspace / "AGENTS.md").symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks are not supported in this environment")

    conversation = _conversation(workspace)
    create_message(conversation.id, "user", "Inspect this project")

    context = build_context(conversation.id)

    assert not any(
        "private external instructions" in item["content"]
        for item in context
    )


def test_context_bounds_number_and_size_of_tool_observations(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    conversation = _conversation(workspace)

    for index in range(TOOL_RESULT_LIMIT + 3):
        call = create_tool_call(
            conversation_id=conversation.id,
            tool_name="test_tool",
            arguments={"index": index},
            status="completed",
        )
        create_tool_result(
            call.id,
            status="completed",
            data={"index": index, "payload": "z" * (TOOL_RESULT_MAX_CHARS + 100)},
        )

    create_message(conversation.id, "user", "Summarize recent results")
    context = build_context(conversation.id)
    tool_messages = [item for item in context if item["role"] == "tool"]

    assert len(tool_messages) == TOOL_RESULT_LIMIT
    assert all(len(item["content"]) <= TOOL_RESULT_MAX_CHARS + 50 for item in tool_messages)
    assert '"index": 7' in tool_messages[-1]["content"]
