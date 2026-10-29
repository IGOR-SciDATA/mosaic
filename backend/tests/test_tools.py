from pathlib import Path
from io import BytesIO

import pytest

from app.db.database import get_connection, init_db
from app.models.action_repository import create_action, update_action
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task, update_task
from app.models.tool_call_repository import create_tool_call, get_tool_call, update_tool_call
from app.models.tool_result_repository import get_tool_result
from app.services.tools import approve_tool_call, execute_tool_call, resolve_tool_policy, validate_tool_call
from app.tools import registry
from app.tools.builtin import FilesystemTool, TerminalTool, WebFetchTool, _read_capped
from app.tools.safe_http import _SafeRedirectHandler, validate_public_url
from urllib.request import Request


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def _conversation(project_id=None):
    model = create_model("Test", "ollama", "test:model")
    return create_conversation("Tools", model.id, project_id=project_id)


def test_registry_contains_initial_tools() -> None:
    names = {tool.name for tool in registry.list()}
    assert {"filesystem", "terminal", "search", "web_fetch", "calculator", "weather"} <= names


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


def test_tool_result_events_record_duration_and_bounded_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Tool evidence", str(workspace))
    conversation = _conversation(project.id)
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": "calculate 2 + 3"},
    )
    call = create_tool_call(
        conversation.id, "calculator", {"expression": "2 + 3"}, task_id=task.id
    )
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "completed"
    events = [
        event for event in list_task_events(task.id)
        if event.event_name == "tool.result_recorded"
    ]
    assert len(events) == 1
    event = events[0]
    assert event.tool_call_id == call.id
    assert event.status == "completed"
    assert event.duration_ms is not None and event.duration_ms >= 0
    assert event.metadata["tool_result_id"] == result.id
    assert event.metadata["tool_name"] == "calculator"
    assert event.metadata["result_data_keys"] == ["result"]
    assert "content" not in event.metadata


def test_failed_tool_result_event_records_error_type_without_raw_payload(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Failed tool evidence", str(workspace))
    conversation = _conversation(project.id)
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": "calculate invalid expression"},
    )
    call = create_tool_call(
        conversation.id, "calculator", {"expression": "unknown"}, task_id=task.id
    )
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "failed"
    event = next(
        event for event in list_task_events(task.id)
        if event.event_name == "tool.result_recorded"
    )
    assert event.status == "failed"
    assert event.duration_ms is not None and event.duration_ms >= 0
    assert event.metadata["error_type"] == "ValueError"
    assert "unknown" not in str(event.metadata)


def test_failed_tool_result_invariant() -> None:
    conversation = _conversation()
    call = create_tool_call(conversation.id, "calculator", {"expression": "unknown"})
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "failed"
    assert result.data is None
    assert result.error


def test_tool_schema_rejects_unknown_fields_and_invalid_ranges() -> None:
    calculator = registry.get("calculator")
    with pytest.raises(ValueError, match="Unknown argument"):
        calculator.validate({"expression": "2 + 2", "run_shell": True})

    weather = registry.get("weather")
    with pytest.raises(ValueError, match="maximum"):
        weather.validate({"latitude": 100, "longitude": 0})

    with pytest.raises(ValueError, match="number"):
        weather.validate({"latitude": True, "longitude": 0})


def test_filesystem_rejects_traversal_and_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = FilesystemTool()

    with pytest.raises(ValueError, match="traversal"):
        tool.execute({"operation": "read", "path": "../secret.txt"}, workspace=workspace)

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = workspace / "escape.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not available in this environment")
    with pytest.raises(ValueError, match="inside the active workspace"):
        tool.execute({"operation": "read", "path": "escape.txt"}, workspace=workspace)


def test_filesystem_schema_requires_content_for_create_and_write() -> None:
    tool = FilesystemTool()
    for operation in ("create", "write"):
        with pytest.raises(ValueError, match="content"):
            tool.validate({"operation": operation, "path": "summary.md"})


@pytest.mark.parametrize("operation", ["read", "list", "mkdir"])
def test_filesystem_schema_rejects_content_for_non_write_operations(operation: str) -> None:
    tool = FilesystemTool()
    with pytest.raises(ValueError, match="content is not allowed"):
        tool.validate({"operation": operation, "path": "summary.md", "content": "unexpected"})


def test_filesystem_schema_only_allows_overwrite_for_write() -> None:
    tool = FilesystemTool()
    with pytest.raises(ValueError, match="overwrite is only allowed"):
        tool.validate({"operation": "create", "path": "summary.md", "content": "summary", "overwrite": True})


def test_filesystem_read_returns_bounded_line_chunks(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "Documento.md"
    source.write_text("\n".join(f"linha {number}" for number in range(1, 101)), encoding="utf-8")
    tool = FilesystemTool()

    first = tool.execute({"operation": "read", "path": "Documento.md"}, workspace=workspace)
    assert first["start_line"] == 1
    assert first["end_line"] == 80
    assert first["total_lines"] == 100
    assert first["truncated"] is True
    assert first["next_start_line"] == 81
    assert "linha 80" in first["content"]
    assert "linha 81" not in first["content"]

    second = tool.execute(
        {"operation": "read", "path": "Documento.md", "start_line": 81, "max_lines": 80},
        workspace=workspace,
    )
    assert second["start_line"] == 81
    assert second["end_line"] == 100
    assert second["truncated"] is False
    assert second["next_start_line"] is None
    assert "linha 100" in second["content"]


def test_filesystem_rejects_chunk_arguments_for_non_read_operations() -> None:
    with pytest.raises(ValueError, match="only allowed for operation read"):
        FilesystemTool().validate({
            "operation": "create",
            "path": "summary.md",
            "content": "summary",
            "start_line": 2,
        })


def test_filesystem_write_requires_explicit_overwrite(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    tool = FilesystemTool()
    created = tool.execute({"operation": "create", "path": "notes/one.txt", "content": "first"}, workspace=workspace)
    assert created["written"] is True
    assert (workspace / "notes" / "one.txt").read_text(encoding="utf-8") == "first"

    with pytest.raises(FileExistsError):
        tool.execute({"operation": "write", "path": "notes/one.txt", "content": "second"}, workspace=workspace)

    tool.execute({"operation": "write", "path": "notes/one.txt", "content": "second", "overwrite": True}, workspace=workspace)
    assert (workspace / "notes" / "one.txt").read_text(encoding="utf-8") == "second"


def test_filesystem_create_preserves_exact_utf8_bytes_and_newlines(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    content = "# Resumo\n\nSão Paulo — versão 1.\n"
    result = FilesystemTool().execute(
        {"operation": "create", "path": "Resumo.md", "content": content},
        workspace=workspace,
    )
    assert result["written"] is True
    assert (workspace / "Resumo.md").read_bytes() == content.encode("utf-8")


def test_filesystem_execution_uses_project_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "project-workspace"
    project = create_project("test", str(workspace))
    conversation = _conversation(project.id)
    task = create_task(type="generic", mode="agent", conversation_id=conversation.id, project_id=project.id)
    call = create_tool_call(
        conversation.id,
        "filesystem",
        {"operation": "create", "path": "result.txt", "content": "verified"},
        task_id=task.id,
    )
    result = execute_tool_call(approve_tool_call(call))
    assert result.status == "completed"
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "verified"


def test_terminal_rejects_shell_operators_and_unapproved_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = TerminalTool()
    with pytest.raises(ValueError, match="Shell operators"):
        tool.execute({"command": "pwd; whoami"}, workspace=workspace)
    with pytest.raises(ValueError, match="allowlist"):
        tool.execute({"command": "whoami"}, workspace=workspace)


def test_terminal_runs_allowlisted_command_in_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = TerminalTool().execute({"command": "pwd"}, workspace=workspace)
    assert result["status"] == "success"
    assert Path(result["stdout"].strip()).resolve() == workspace.resolve()



def test_task_action_and_tool_call_transitions_are_enforced() -> None:
    conversation = _conversation()
    task = create_task(type="generic", mode="agent", conversation_id=conversation.id)
    with pytest.raises(ValueError, match="Invalid task transition"):
        update_task(task.id, status="completed")

    action = create_action(task.id, type="test")
    with pytest.raises(ValueError, match="Invalid action transition"):
        update_action(action.id, status="completed")

    call = create_tool_call(conversation.id, "calculator", {"expression": "1 + 1"}, task_id=task.id)
    with pytest.raises(ValueError, match="Invalid tool call transition"):
        update_tool_call(call.id, status="completed")



def test_public_web_fetch_blocks_local_and_non_http_destinations() -> None:
    with pytest.raises(ValueError, match="non-public"):
        validate_public_url("http://127.0.0.1/admin")
    with pytest.raises(ValueError, match="non-public"):
        validate_public_url("http://[::1]/")
    with pytest.raises(ValueError, match="HTTP and HTTPS"):
        validate_public_url("file:///etc/passwd")


def test_web_fetch_has_strict_schema() -> None:
    tool = WebFetchTool()
    with pytest.raises(ValueError, match="Unknown argument"):
        tool.validate({"url": "https://example.com", "allow_private": True})



def test_terminal_timeout_cleans_up_process_tree(tmp_path: Path, monkeypatch) -> None:
    from app.tools import builtin

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "test_wait.py").write_text(
        "import time\ndef test_wait():\n    time.sleep(5)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(builtin, "COMMAND_TIMEOUT_SECONDS", 0.3)
    result = TerminalTool().execute({"command": "python -m pytest test_wait.py"}, workspace=workspace)
    assert result["status"] == "timeout"
    assert result["duration_ms"] < 3_000


def test_terminal_cooperatively_cancels_running_task_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "test_wait.py").write_text(
        "import time\ndef test_wait():\n    time.sleep(5)\n",
        encoding="utf-8",
    )
    checks = 0

    def cancel_after_start() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 4

    result = TerminalTool().execute(
        {"command": "python -m pytest test_wait.py"},
        workspace=workspace,
        cancel_check=cancel_after_start,
    )
    assert result["status"] == "cancelled"
    assert result["duration_ms"] < 3_000



def test_public_web_fetch_rejects_private_dns_and_redirects(monkeypatch) -> None:
    import socket

    monkeypatch.setattr(
        "app.tools.safe_http.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 80))],
    )
    with pytest.raises(ValueError, match="non-public"):
        validate_public_url("http://public-looking.example/path")

    handler = _SafeRedirectHandler()
    with pytest.raises(ValueError, match="non-public"):
        handler.redirect_request(
            Request("https://example.com"),
            None,
            302,
            "Found",
            {},
            "http://169.254.169.254/latest/meta-data/",
        )


def test_search_results_are_normalized() -> None:
    from app.tools.builtin import _SearchResultsParser

    parser = _SearchResultsParser()
    parser.feed(
        '<div class="result"><a class="result__a" href="https://example.com/page">Example title</a>'
        '<div class="result__snippet">A short source snippet.</div></div>'
    )
    assert parser.results == [{
        "title": "Example title",
        "url": "https://example.com/page",
        "snippet": "A short source snippet.",
    }]



def test_calculator_rejects_excessive_exponents() -> None:
    calculator = registry.get("calculator")
    with pytest.raises(ValueError, match="exponent"):
        calculator.execute({"expression": "2 ** 1000000000"})



def test_new_work_items_cannot_start_in_terminal_or_approved_states() -> None:
    conversation = _conversation()
    with pytest.raises(ValueError, match="start in pending"):
        create_task(type="generic", mode="agent", conversation_id=conversation.id, status="completed")
    task = create_task(type="generic", mode="agent", conversation_id=conversation.id)
    with pytest.raises(ValueError, match="start in pending"):
        create_action(task.id, type="test", status="approved")
    with pytest.raises(ValueError, match="start in pending"):
        create_tool_call(conversation.id, "calculator", {"expression": "1 + 1"}, task_id=task.id, status="approved")



def test_core_policy_requires_approval_for_side_effects_but_not_local_reads() -> None:
    calculator = resolve_tool_policy("calculator", {"expression": "1 + 1"})
    search = resolve_tool_policy("search", {"query": "Mosaic project"})
    fetch = resolve_tool_policy("web_fetch", {"url": "https://example.com"})
    filesystem_read = resolve_tool_policy("filesystem", {"operation": "read", "path": "Documento.md"})
    filesystem_list = resolve_tool_policy("filesystem", {"operation": "list", "path": "."})
    filesystem_create = resolve_tool_policy(
        "filesystem",
        {"operation": "create", "path": "Resumo.md", "content": "# Resumo"},
    )

    assert calculator["approval_required"] is False
    assert search["approval_required"] is True
    assert fetch["approval_required"] is True
    assert filesystem_read["approval_required"] is False
    assert filesystem_list["approval_required"] is False
    assert filesystem_create["approval_required"] is True



def test_terminal_output_capture_is_bounded() -> None:
    output = bytearray()
    truncated = {"stdout": False}
    _read_capped(BytesIO(b"x" * 100), output, 16, truncated, "stdout")
    assert len(output) == 16
    assert truncated["stdout"] is True


def test_filesystem_explore_recursively_reads_text_and_excludes_generated_and_sensitive_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src" / "nested").mkdir(parents=True)
    (workspace / "node_modules" / "pkg").mkdir(parents=True)
    (workspace / ".git").mkdir()
    (workspace / ".venv" / "bin").mkdir(parents=True)
    (workspace / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (workspace / "src" / "nested" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (workspace / ".env").write_text("API_KEY=must-not-read", encoding="utf-8")
    (workspace / "node_modules" / "pkg" / "index.js").write_text("generated", encoding="utf-8")
    (workspace / ".git" / "config").write_text("git internals", encoding="utf-8")
    (workspace / ".venv" / "bin" / "activate").write_text("virtualenv", encoding="utf-8")
    (workspace / "image.bin").write_bytes(b"\x00\x01binary")
    result = FilesystemTool().execute({"operation": "explore", "path": "."}, workspace=workspace)
    assert result["status"] == "success"
    assert result["directories_found"] >= 3
    assert [item["path"] for item in result["files"]] == ["src/main.py", "src/nested/notes.md"]
    reasons = {item["reason"] for item in result["ignored"]}
    assert {"excluded_directory", "sensitive_filename", "binary_content"} <= reasons
    assert all("must-not-read" not in item["content"] for item in result["files"])


def test_filesystem_explore_reports_partial_limits_and_relative_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("12345", encoding="utf-8")
    (workspace / "b.txt").write_text("67890", encoding="utf-8")
    result = FilesystemTool().execute(
        {"operation": "explore", "path": ".", "max_files": 1, "max_file_bytes": 10, "max_total_bytes": 10},
        workspace=workspace,
    )
    assert result["status"] == "partial"
    assert result["files_read"] == 1
    assert "max_files" in result["limits_reached"]
    assert all(not Path(item["path"]).is_absolute() for item in result["files"])


def test_filesystem_explore_rejects_traversal_and_symlinks(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    tool = FilesystemTool()
    with pytest.raises(ValueError, match="traversal"):
        tool.execute({"operation": "explore", "path": "../"}, workspace=workspace)
    link = workspace / "escape"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not available in this environment")
    result = tool.execute({"operation": "explore", "path": "."}, workspace=workspace)
    assert all(item["path"] != "escape" for item in result["files"])
    assert any(item["path"] == "escape" and item["reason"] == "symlink" for item in result["ignored"])


def test_filesystem_explore_handles_empty_directories_and_oversized_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = FilesystemTool().execute({"operation": "explore", "path": "."}, workspace=empty)
    assert result["status"] == "success"
    assert result["directories"] == ["."]
    assert result["files_read"] == 0

    (empty / "large.txt").write_text("x" * 20, encoding="utf-8")
    result = FilesystemTool().execute({"operation": "explore", "path": "."}, workspace=empty)
    assert result["files_read"] == 1
    assert result["files"][0]["content"] == "x" * 20

    limited = FilesystemTool().execute(
        {"operation": "explore", "path": ".", "max_file_bytes": 10},
        workspace=empty,
    )
    assert limited["files_read"] == 0
    assert any(item["path"] == "large.txt" and item["reason"] == "file_size_limit" for item in limited["ignored"])


def test_filesystem_search_matches_relative_names_and_content_without_approval(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "engine.py").write_text("class WorkspaceEngine:\\n    pass\\n", encoding="utf-8")
    tool = FilesystemTool()
    assert tool.policy_for({"operation": "search", "path": ".", "query": "WorkspaceEngine"})["approval_required"] is False

    content_result = tool.execute(
        {"operation": "search", "path": ".", "query": "WorkspaceEngine", "search_in": "content"},
        workspace=workspace,
    )
    assert content_result["status"] == "success"
    assert content_result["matches"][0]["path"] == "src/engine.py"
    assert content_result["matches"][0]["content_matches"][0]["line"] == 1

    name_result = tool.execute(
        {"operation": "search", "path": ".", "query": "engine.py", "search_in": "name"},
        workspace=workspace,
    )
    assert name_result["matches"][0]["path"] == "src/engine.py"


def test_filesystem_explore_has_no_default_file_count_or_byte_caps(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for index in range(205):
        (workspace / f"file_{index:03}.txt").write_text("x" * 40_000, encoding="utf-8")
    result = FilesystemTool().execute({"operation": "explore", "path": "."}, workspace=workspace)
    assert result["status"] == "success"
    assert result["files_found"] == 205
    assert result["files_read"] == 205
    assert result["bytes_read"] == 205 * 40_000
    assert result["limits_reached"] == []
