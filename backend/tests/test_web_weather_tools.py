import json
from io import BytesIO

import pytest

from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task
from app.models.tool_call_repository import create_tool_call, get_tool_call
from app.services.tools import approve_tool_call, execute_tool_call


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "web-weather.db")
    init_db()


def _task_and_conversation(tmp_path, name):
    workspace = tmp_path / name
    workspace.mkdir()
    project = create_project(name, str(workspace))
    model = create_model("Selected", "ollama", "selected:test")
    conversation = create_conversation(name, model.id, project_id=project.id)
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": f"Use {name} tool and report observed result"},
    )
    return task, conversation


def test_search_tool_returns_real_source_provenance_through_tool_result(monkeypatch, tmp_path):
    task, conversation = _task_and_conversation(tmp_path, "Search provenance")
    html = (
        b'<div class="result"><a class="result__a" href="https://example.com/mosaic">Mosaic Project</a>'
        b'<div class="result__snippet">Public source snippet.</div></div>'
        b'<div class="result"><a class="result__a" href="https://example.org/second">Second Result</a>'
        b'<div class="result__snippet">Second source snippet.</div></div>'
    )

    def fake_urlopen(request, timeout):
        assert request.full_url.startswith("https://html.duckduckgo.com/html/?q=")
        assert timeout == 10
        return BytesIO(html)

    monkeypatch.setattr("app.tools.builtin.safe_urlopen", fake_urlopen)
    call = create_tool_call(
        conversation.id, "search", {"query": "Mosaic project"}, task_id=task.id
    )
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "completed"
    assert result.data["status"] == "success"
    assert result.data["provider"] == "DuckDuckGo"
    assert result.data["query"] == "Mosaic project"
    assert result.data["retrieved_at"]
    assert result.data["results"][0]["title"] == "Mosaic Project"
    assert result.data["results"][0]["url"] == "https://example.com/mosaic"
    assert result.data["results"][0]["snippet"] == "Public source snippet."
    assert result.data["results"][0]["rank"] == 1
    assert result.data["results"][0]["retrieved_at"] == result.data["retrieved_at"]
    assert get_tool_call(call.id).status == "completed"


def test_weather_tool_returns_provider_and_retrieval_metadata(monkeypatch, tmp_path):
    task, conversation = _task_and_conversation(tmp_path, "Weather provenance")
    payload = {
        "latitude": 40.7,
        "longitude": -74.0,
        "current_units": {
            "temperature_2m": "C",
            "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h",
        },
        "current": {
            "temperature_2m": 21.5,
            "relative_humidity_2m": 52,
            "wind_speed_10m": 12.3,
        },
    }

    def fake_urlopen(url, timeout):
        assert "latitude=40.7" in url
        assert "longitude=-74.0" in url
        assert "current=temperature_2m,relative_humidity_2m,wind_speed_10m" in url
        return BytesIO(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("app.tools.builtin.safe_urlopen", fake_urlopen)
    call = create_tool_call(
        conversation.id, "weather", {"latitude": 40.7, "longitude": -74.0}, task_id=task.id
    )
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "completed"
    assert result.data["status"] == "success"
    assert result.data["provider"] == "Open-Meteo"
    assert result.data["retrieved_at"]
    assert result.data["data"]["current"]["temperature_2m"] == 21.5
    assert result.data["data"]["current_units"]["temperature_2m"] == "C"


@pytest.mark.parametrize("tool_name,arguments", [
    ("search", {"query": "Mosaic"}),
    ("weather", {"latitude": 40.7, "longitude": -74.0}),
])
def test_provider_error_becomes_failed_tool_result_and_event(monkeypatch, tmp_path, tool_name, arguments):
    task, conversation = _task_and_conversation(tmp_path, f"Provider error {tool_name}")

    def unavailable(*args, **kwargs):
        if tool_name == "search":
            raise TimeoutError("upstream unavailable")
        return BytesIO(json.dumps({"error": True, "reason": "service temporarily unavailable"}).encode("utf-8"))

    monkeypatch.setattr("app.tools.builtin.safe_urlopen", unavailable)
    call = create_tool_call(conversation.id, tool_name, arguments, task_id=task.id)
    result = execute_tool_call(approve_tool_call(call))

    assert result.status == "failed"
    assert get_tool_call(call.id).status == "failed"
    event = next(
        event for event in list_task_events(task.id)
        if event.event_name == "tool.result_recorded" and event.tool_call_id == call.id
    )
    assert event.status == "failed"
    assert event.metadata["error_type"] == "provider_error"
    assert "upstream unavailable" not in str(event.metadata)
