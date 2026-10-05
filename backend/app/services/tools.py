from typing import Any

from app.models.tool_call import ToolCall
from app.models.tool_call_repository import get_tool_call, update_tool_call
from app.models.tool_result import ToolResult
from app.models.tool_result_repository import create_tool_result
from app.tools import registry


def validate_tool_call(tool_call: ToolCall) -> None:
    tool = registry.get(tool_call.tool_name)
    if tool is None:
        raise ValueError(f"Unknown tool: {tool_call.tool_name}")
    tool.validate(tool_call.arguments)


def approve_tool_call(tool_call: ToolCall) -> ToolCall:
    if tool_call.status != "pending":
        raise ValueError(f"Invalid tool call transition: {tool_call.status} -> approved")
    return update_tool_call(tool_call.id, status="approved")


def execute_tool_call(tool_call: ToolCall) -> ToolResult:
    validate_tool_call(tool_call)

    if tool_call.status != "approved":
        raise ValueError("Tool call must be approved before execution")

    executing = update_tool_call(tool_call.id, status="executing")
    tool = registry.get(executing.tool_name)

    try:
        data = tool.execute(executing.arguments)
    except Exception as exc:
        update_tool_call(executing.id, status="failed")
        return create_tool_result(executing.id, "failed", error=str(exc))

    update_tool_call(executing.id, status="completed")
    if not isinstance(data, dict):
        data = {"value": data}
    return create_tool_result(executing.id, "completed", data=data)
