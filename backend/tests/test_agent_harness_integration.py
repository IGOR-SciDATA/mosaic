import pytest

from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task, get_task
from app.models.tool_call_repository import list_tool_calls
from app.models.tool_result_repository import list_tool_results
from app.services.agent import run_agent
from app.services.agent_decision import create_provider_decider


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "harness-integration.db")
    init_db()


def test_provider_decision_tool_result_observation_and_completion_use_selected_model(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Harness integration", str(workspace))
    model = create_model("Selected test model", "ollama", "selected-model:3b")
    conversation = create_conversation(
        "Harness integration", model.id, project_id=project.id
    )
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": "calcule 2 + 2 e informe o resultado"},
    )

    requests = []

    class FakeProvider:
        def generate_with_tools(self, *, messages, model_name, configuration, tools):
            requests.append({
                "messages": messages,
                "model_name": model_name,
                "configuration": configuration,
                "tools": tools,
            })
            assert model_name == "selected-model:3b"
            assert configuration["temperature"] == 0
            assert configuration["think"] is False

            if len(requests) == 1:
                available = {
                    item["function"]["name"] for item in tools
                }
                assert "calculator" in available
                return {
                    "type": "tool_call",
                    "tool": "calculator",
                    "arguments": {"expression": "2 + 2"},
                    "_native_message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "fake-calculation",
                            "type": "function",
                            "function": {
                                "name": "calculator",
                                "arguments": {"expression": "2 + 2"},
                            },
                        }],
                    },
                }

            assert len(requests) == 2
            assert any(
                message.get("role") == "tool"
                and message.get("tool_name") == "calculator"
                and '"result": 4' in message.get("content", "")
                for message in messages
            ), "The actual ToolResult must be observed before the next model decision"
            return {"type": "final", "content": "O resultado de 2 + 2 é 4."}

    fake_provider = FakeProvider()
    monkeypatch.setattr(
        "app.services.agent_decision.resolve_model_provider",
        lambda _model: fake_provider,
    )

    result = run_agent(task.id, create_provider_decider(task.id))

    assert result["status"] == "completed"
    assert len(requests) == 2
    assert all(request["model_name"] == model.model_name for request in requests)
    persisted_task = get_task(task.id)
    assert persisted_task.status == "completed"
    assert persisted_task.result["output"] == "O resultado de 2 + 2 é 4."

    calls = [
        call for call in list_tool_calls(conversation.id)
        if call.task_id == task.id
    ]
    assert len(calls) == 1
    assert calls[0].tool_name == "calculator"
    assert calls[0].status == "completed"
    results = list_tool_results(calls[0].id)
    assert len(results) == 1
    assert results[0].status == "completed"
    assert results[0].data == {"result": 4}

    event_names = [event.event_name for event in list_task_events(task.id)]
    assert "model_request_started" in event_names
    assert "model_request_completed" in event_names
    assert "tool.completed" in event_names
    assert "task.status_changed" in event_names
