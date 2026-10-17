"""Persist bounded, redacted diagnostic reports for terminal Task executions."""

import json
import os
import re
from pathlib import Path
from typing import Any

from app.models.task_event_repository import list_task_events
from app.models.task_repository import get_task
from app.models.tool_call_repository import list_tool_calls
from app.models.tool_result_repository import list_tool_results

_SECRET_KEY = re.compile(r"(token|secret|password|credential|authorization|api[_-]?key|private[_-]?key)", re.I)
_INLINE_SECRET = re.compile(r"(?i)\b(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*[^\s,;]+")
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.I | re.S)
_MAX_TEXT = 1200
_MAX_REPORT_CHARS = 250_000
_MAX_EVENTS = 500
_MAX_TOOL_CALLS = 100


def _safe_text(value: str, limit: int = _MAX_TEXT) -> str:
    # Never persist tagged private reasoning; diagnostics need the visible output only.
    value = _THINK_BLOCK.sub("[model thinking omitted]", value)
    if re.search(r"<think>", value, re.I):
        value = "[incomplete model thinking block omitted]"
    value = _INLINE_SECRET.sub(r"\1=[REDACTED]", value)
    return value[:limit]


def _safe_value(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return "[depth-limited]"
    if isinstance(value, dict):
        return {
            str(key)[:100]: (
                "[REDACTED]" if _SECRET_KEY.search(str(key)) else _safe_value(item, depth + 1)
            )
            for key, item in list(value.items())[:50]
        }
    if isinstance(value, list):
        return [_safe_value(item, depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return _safe_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _safe_text(str(value), 500)


def _bounded_value(value: Any, limit: int = 3000) -> Any:
    safe_value = _safe_value(value)
    encoded = json.dumps(safe_value, ensure_ascii=False, default=str)
    if len(encoded) <= limit:
        return safe_value
    return {"truncated": True, "preview": _safe_text(encoded, limit - 100)}


def _all_events(task_id: int) -> list[Any]:
    events: list[Any] = []
    cursor = 0
    while len(events) < _MAX_EVENTS:
        batch = list_task_events(task_id, after_id=cursor, limit=min(200, _MAX_EVENTS - len(events)))
        if not batch:
            break
        events.extend(batch)
        cursor = batch[-1].id
    return events


def write_task_execution_log(task_id: int) -> str | None:
    """Write one JSON diagnostic report for a terminal task; never disrupt task state."""
    task = get_task(task_id)
    if task is None or task.status not in {"completed", "failed", "cancelled"}:
        return None

    events = _all_events(task_id)
    tool_calls: list[dict[str, Any]] = []
    if task.conversation_id is not None:
        calls = [
            call for call in list_tool_calls(task.conversation_id)
            if call.task_id == task_id
        ][:_MAX_TOOL_CALLS]
        for call in calls:
            results = []
            for result in list_tool_results(call.id):
                item: dict[str, Any] = {
                    "id": result.id,
                    "status": result.status,
                    "created_at": result.created_at,
                }
                if result.data is not None:
                    item["data"] = _bounded_value(result.data)
                if result.error:
                    item["error"] = _safe_text(result.error)
                results.append(item)
            tool_calls.append({
                "id": call.id,
                "tool": call.tool_name,
                "status": call.status,
                "arguments": _bounded_value(call.arguments, 2000),
                "created_at": call.created_at,
                "updated_at": call.updated_at,
                "results": results,
            })

    model_responses = []
    for event in events:
        if event.component != "model":
            continue
        metadata = event.metadata or {}
        if event.event_name in {"decision_invalid", "decision_parsed", "model_request_completed", "model_request_failed"}:
            response = metadata.get("response_preview") or metadata.get("output_preview")
            model_responses.append({
                "event_id": event.id,
                "timestamp": event.timestamp,
                "event_name": event.event_name,
                "status": event.status,
                "message": event.message,
                "duration_ms": event.duration_ms,
                "model": metadata.get("model"),
                "attempt": metadata.get("attempt"),
                "response_chars": metadata.get("response_chars"),
                "validation_error": metadata.get("error") if event.event_name == "decision_invalid" else None,
                "response_preview": _safe_text(response) if isinstance(response, str) else None,
            })

    report = {
        "schema_version": 1,
        "task": {
            "id": task.id,
            "conversation_id": task.conversation_id,
            "project_id": task.project_id,
            "type": task.type,
            "mode": task.mode,
            "status": task.status,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "goal": _safe_text(str((task.plan or {}).get("goal", ""))),
            "plan": _bounded_value(task.plan, 5000),
            "result": _bounded_value(task.result, 5000),
        },
        "model_responses": model_responses,
        "tool_calls": tool_calls,
        "events": [{
            "id": event.id,
            "timestamp": event.timestamp,
            "level": event.level,
            "component": event.component,
            "event_name": event.event_name,
            "message": _safe_text(event.message, 500),
            "duration_ms": event.duration_ms,
            "status": event.status,
            "metadata": _safe_value(event.metadata or {}),
        } for event in events],
        "truncated": {
            "events": len(events) >= _MAX_EVENTS,
            "tool_calls": len(tool_calls) >= _MAX_TOOL_CALLS,
        },
    }

    configured_dir = os.environ.get("MOSAIC_TASK_LOG_DIR")
    log_dir = Path(configured_dir).expanduser() if configured_dir else Path(__file__).resolve().parents[2] / "data" / "task-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"task-{task.id}.json"
    temporary_path = log_path.with_suffix(".json.tmp")
    encoded = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if len(encoded) > _MAX_REPORT_CHARS:
        # Keep the newest diagnostic evidence when a task produces excessive output.
        report["events"] = report["events"][-100:]
        report["model_responses"] = report["model_responses"][-50:]
        report["tool_calls"] = report["tool_calls"][-30:]
        report["truncated"]["report_size_guard"] = True
        encoded = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if len(encoded) > _MAX_REPORT_CHARS:
        report["events"] = report["events"][-50:]
        report["model_responses"] = report["model_responses"][-20:]
        report["tool_calls"] = report["tool_calls"][-10:]
        encoded = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    temporary_path.write_text(encoded + "\n", encoding="utf-8")
    temporary_path.replace(log_path)
    return str(log_path)
