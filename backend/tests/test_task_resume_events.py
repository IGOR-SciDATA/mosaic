import asyncio
import json

import pytest
from fastapi import BackgroundTasks

from app.api.tasks import ToolDecision, decide_tool_call_endpoint, stream_task_events_endpoint
from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task, get_task, update_task
from app.models.tool_call_repository import create_tool_call, get_tool_call
from app.models.tool_result_repository import list_tool_results


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "resume-events.db")
    init_db()


def test_sse_reconnect_replays_only_events_after_last_event_id():
    project = create_project("SSE replay", "/tmp/mosaic-sse-replay")
    task = create_task(type="generic", mode="agent", project_id=project.id)
    update_task(task.id, status="executing")
    update_task(task.id, status="completed", result={"output": "done"})
    events = list_task_events(task.id)
    assert len(events) >= 3

    class FakeRequest:
        headers = {"last-event-id": str(events[0].id)}
        disconnect_checks = 0

        async def is_disconnected(self):
            self.disconnect_checks += 1
            return self.disconnect_checks > 1

    request = FakeRequest()

    async def consume():
        response = await stream_task_events_endpoint(task.id, request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
        return response, "".join(chunks)

    response, body = asyncio.run(consume())
    streamed_ids = [
        int(line.removeprefix("id: ").strip())
        for line in body.splitlines()
        if line.startswith("id: ")
    ]
    assert response.media_type == "text/event-stream"
    assert streamed_ids == [event.id for event in events[1:]]
    assert events[0].id not in streamed_ids
    assert all(f"event: task_event" in body for _ in [0])


def test_approved_write_resumes_same_task_and_verifies_once(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Resume after approval", str(workspace))
    model = create_model("Test", "ollama", "test:model")
    conversation = create_conversation("Resume after approval", model.id, project_id=project.id)
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": "crie arquivo Resumo.md"},
    )
    content = "# Resumo verificado\n\nConteúdo persistido.\n"
    call = create_tool_call(
        conversation.id,
        "filesystem",
        {"operation": "create", "path": "Resumo.md", "content": content},
        task_id=task.id,
    )
    update_task(task.id, status="executing")
    update_task(task.id, status="awaiting_approval", result={"tool_call_id": call.id})

    background = BackgroundTasks()
    pending_task = decide_tool_call_endpoint(
        task.id, call.id, ToolDecision(decision="approve"), background
    )
    assert pending_task.status == "executing"
    assert get_tool_call(call.id).status == "approved"
    assert len(background.tasks) == 1

    scheduled = background.tasks[0]
    scheduled.func(*scheduled.args, **scheduled.kwargs)

    completed_task = get_task(task.id)
    final_call = get_tool_call(call.id)
    results = list_tool_results(call.id)
    artifact = workspace / "Resumo.md"
    assert completed_task.status == "completed"
    assert completed_task.result["artifact"]["path"] == "Resumo.md"
    assert artifact.is_file()
    assert artifact.read_text(encoding="utf-8") == content
    assert final_call.status == "completed"
    assert len(results) == 1
    assert results[0].status == "completed"
    assert results[0].data["path"] == "Resumo.md"
    assert sum(event.event_name == "tool.completed" for event in list_task_events(task.id)) == 1
