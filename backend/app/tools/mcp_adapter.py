"""Adapter exposing an approved MCP server's discovered tools through Mosaic Tool API.

Connections and enabled tool snapshots are process-local in this first increment;
persistent connection configuration and UI management are later phases.
"""
from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.tools.base import Tool
from app.tools.registry import ToolRegistry
from app.integrations.mcp.client import (
    MCPHTTPClient,
    MCPServerConfig,
    qualified_tool_name,
)

MAX_REMOTE_ARGUMENTS_BYTES = 128_000
MAX_TOOL_OUTPUT_BYTES = 500_000


class MCPConnection:
    def __init__(self, server_id: str, config: MCPServerConfig, *, enabled: bool = True):
        self.server_id = server_id
        self.config = config
        self.enabled = enabled
        self.client = MCPHTTPClient(config)
        self.tools: dict[str, dict[str, Any]] = {}
        self.lock = RLock()

    def refresh(self) -> list[dict[str, Any]]:
        with self.lock:
            if not self.enabled:
                raise ValueError("MCP connection is disabled")
            tools = self.client.list_tools()
            self.tools = {item["name"]: item for item in tools}
            return list(self.tools.values())

    def disconnect(self) -> None:
        with self.lock:
            self.enabled = False
            self.tools.clear()


class MCPConnectionManager:
    def __init__(self):
        self._connections: dict[str, MCPConnection] = {}
        self._lock = RLock()

    def connect(self, server_id: str, config: MCPServerConfig) -> MCPConnection:
        connection = MCPConnection(server_id, config)
        connection.refresh()
        with self._lock:
            self._connections[server_id] = connection
        return connection

    def get(self, server_id: str) -> MCPConnection | None:
        with self._lock:
            return self._connections.get(server_id)

    def disconnect(self, server_id: str) -> bool:
        with self._lock:
            connection = self._connections.get(server_id)
        if connection is None:
            return False
        connection.disconnect()
        return True

    def enabled_connections(self) -> list[MCPConnection]:
        with self._lock:
            return [connection for connection in self._connections.values() if connection.enabled]


connection_manager = MCPConnectionManager()


class MCPRemoteTool(Tool):
    """One immutable discovered tool descriptor; execution rechecks live enablement/schema."""

    def __init__(
        self,
        connection: MCPConnection,
        remote_name: str,
        descriptor: dict[str, Any],
    ):
        self.connection = connection
        self.remote_name = remote_name
        self.name = qualified_tool_name(connection.server_id, remote_name)
        self.description = f"MCP server '{connection.server_id}' tool '{remote_name}': {descriptor.get('description', '')}"[:2000]
        self.input_schema = descriptor["input_schema"]
        # All remote calls require approval until a future policy explicitly classifies
        # read-only operations using trusted metadata. Server descriptions are untrusted.
        self.permission_policy = {
            "approval_required": True,
            "scope": f"mcp:{connection.server_id}:{remote_name}",
            "timeout_seconds": connection.config.timeout_seconds,
        }

    def execute(
        self,
        arguments: dict[str, Any],
        *,
        workspace: Path | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Any:
        connection = self.connection
        with connection.lock:
            if not connection.enabled:
                raise ValueError("MCP connection is disabled")
            current = connection.tools.get(self.remote_name)
            if current is None:
                raise ValueError("MCP tool is no longer present in the enabled server snapshot")
            if current["input_schema"] != self.input_schema:
                raise ValueError("MCP tool schema changed; refresh and re-authorize before calling")
        import json
        if len(json.dumps(arguments, ensure_ascii=False).encode("utf-8")) > MAX_REMOTE_ARGUMENTS_BYTES:
            raise ValueError("MCP tool arguments exceed the configured limit")
        result = connection.client.call_tool(self.remote_name, arguments)
        encoded = json.dumps(result, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES:
            raise ValueError("MCP tool result exceeds the Mosaic adapter limit")
        return {
            "status": "success",
            "server": connection.server_id,
            "remote_tool": self.remote_name,
            "result": result,
        }


def register_mcp_tools(
    connection: MCPConnection,
    registry: ToolRegistry,
) -> list[str]:
    """Register the already-discovered snapshot in Mosaic's normal ToolRegistry."""
    registered = []
    for remote_name, descriptor in sorted(connection.tools.items()):
        tool = MCPRemoteTool(connection, remote_name, descriptor)
        registry.register(tool)
        registered.append(tool.name)
    return registered
