import json
from types import SimpleNamespace

from app.services import task_execution_log as diagnostics


def test_execution_log_captures_model_responses_and_tool_data(monkeypatch, tmp_path):
    task = SimpleNamespace(
        id=12,
        conversation_id=3,
        project_id=4,
        type="document",
        mode="agent",
        status="failed",
        plan={"goal": "Leia o arquivo e resuma"},
        result={"error": "Model response was not valid JSON"},
        created_at="2026-10-17T00:00:00+00:00",
        updated_at="2026-10-17T00:01:00+00:00",
    )
    events = [
        SimpleNamespace(
            id=1, timestamp="2026-10-17T00:00:00+00:00", level="info",
            component="model", event_name="model_request_started", message="Request started",
            duration_ms=None, status="started",
            metadata={
                "model": "qwen2.5:3b", "attempt": 1, "message_count": 4,
                "message_roles": ["system", "system", "system", "system"],
                "request_preview": '[{"role":"system","content_tail":"ToolResult completed"}]',
            },
        ),
        SimpleNamespace(
            id=2, timestamp="2026-10-17T00:00:01+00:00", level="warning",
            component="model", event_name="decision_invalid", message="JSON inválido",
            duration_ms=500, status="invalid",
            metadata={
                "model": "qwen2.5:3b", "attempt": 1, "response_chars": 50,
                "error": "Model response was not valid JSON",
                "response_preview": '{"type": "final", "content": "<think>private</think> token=abc123"}',
            },
        )
    ]
    call = SimpleNamespace(
        id=8, task_id=12, tool_name="filesystem", status="completed",
        arguments={"operation": "read", "path": "Documento.md"},
        created_at="2026-10-17T00:00:02+00:00", updated_at="2026-10-17T00:00:03+00:00",
    )
    result = SimpleNamespace(
        id=9, status="completed", created_at="2026-10-17T00:00:03+00:00",
        data={"status": "success", "content": "Conteúdo lido"},
        error=None,
    )
    monkeypatch.setattr(diagnostics, "get_task", lambda task_id: task)
    monkeypatch.setattr(diagnostics, "list_task_events", lambda *args, **kwargs: events if kwargs.get("after_id", 0) == 0 else [])
    monkeypatch.setattr(diagnostics, "list_tool_calls", lambda conversation_id: [call])
    monkeypatch.setattr(diagnostics, "list_tool_results", lambda call_id: [result])
    monkeypatch.setenv("MOSAIC_TASK_LOG_DIR", str(tmp_path))

    log_path = diagnostics.write_task_execution_log(12)

    report = json.loads(open(log_path, encoding="utf-8").read())
    assert report["task"]["status"] == "failed"
    assert report["model_requests"][0]["message_count"] == 4
    assert "ToolResult completed" in report["model_requests"][0]["request_preview"]
    assert report["model_responses"][0]["validation_error"] == "Model response was not valid JSON"
    preview = report["model_responses"][0]["response_preview"]
    assert "private" not in preview
    assert "abc123" not in preview
    assert "[REDACTED]" in preview
    assert report["tool_calls"][0]["results"][0]["data"]["status"] == "success"


def test_execution_log_skips_non_terminal_tasks(monkeypatch):
    monkeypatch.setattr(
        diagnostics, "get_task",
        lambda task_id: SimpleNamespace(id=task_id, status="awaiting_approval"),
    )
    assert diagnostics.write_task_execution_log(12) is None


def test_terminal_task_transition_triggers_diagnostic_log(monkeypatch, tmp_path):
    from app.db.database import init_db
    from app.models.conversation_repository import create_conversation
    from app.models.repository import create_model
    from app.models.task_repository import create_task, update_task

    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()
    model = create_model("Test", "ollama", "test:model")
    conversation = create_conversation("Diagnostics", model.id)
    task = create_task(type="generic", mode="agent", conversation_id=conversation.id)
    calls = []
    monkeypatch.setattr(diagnostics, "write_task_execution_log", lambda task_id: calls.append(task_id) or str(tmp_path / f"task-{task_id}.json"))

    update_task(task.id, status="executing")
    update_task(task.id, status="failed", result={"error": "test failure"})

    assert calls == [task.id]
