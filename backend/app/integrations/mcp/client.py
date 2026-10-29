"""Minimal JSON-RPC client for remote Model Context Protocol HTTP servers.

This client intentionally supports the remote HTTP transport needed by the GitHub
reference plugin. It never launches package-provided commands or expands shell text.
"""
from __future__ import annotations

import json
import re
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

MAX_RESPONSE_BYTES = 1_000_000
MAX_REQUEST_BYTES = 128_000
DEFAULT_TIMEOUT_SECONDS = 15.0

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)(\s*[:=]\s*)[^\s,;]+"),
)


class MCPError(RuntimeError):
    """Safe, user-facing MCP error."""


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    url: str
    headers: Mapping[str, str]
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def validate(self) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}", self.name):
            raise ValueError("Invalid MCP server name")
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MCP URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("MCP URL must not contain credentials, query, or fragment")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Remote MCP endpoints must use HTTPS")
        if not 1 <= self.timeout_seconds <= 60:
            raise ValueError("MCP timeout must be between 1 and 60 seconds")
        if not 1 <= self.max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError("MCP response limit is invalid")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.headers.items()):
            raise ValueError("MCP headers must be string pairs")
        # Do not allow header injection.
        if any("\r" in k or "\n" in k or "\r" in v or "\n" in v for k, v in self.headers.items()):
            raise ValueError("MCP headers cannot contain newlines")


def redact_secrets(value: str) -> str:
    result = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 1:
            result = pattern.sub(r"\1[REDACTED]", result)
        else:
            result = pattern.sub(r"\1\2[REDACTED]", result)
    return result[:4000]


def parse_claude_plugin_config(manifest_text: str, mcp_text: str) -> dict[str, Any]:
    """Parse supported Claude Code plugin metadata and .mcp.json without executing it."""
    try:
        manifest = json.loads(manifest_text)
        mcp_config = json.loads(mcp_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Plugin manifest and MCP configuration must be valid JSON") from exc
    if not isinstance(manifest, dict) or not isinstance(mcp_config, dict):
        raise ValueError("Plugin manifest and MCP configuration must be JSON objects")
    meta = manifest.get("name")
    if not isinstance(meta, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}", meta):
        raise ValueError("Plugin manifest requires a valid name")
    servers = mcp_config.get("mcpServers")
    # Current official GitHub plugin uses the server map in .mcp.json and may
    # alternatively be represented inline as a server object by plugin format versions.
    if servers is None and "github" in mcp_config and isinstance(mcp_config["github"], dict):
        servers = {"github": mcp_config["github"]}
    if not isinstance(servers, dict) or not servers:
        raise ValueError("Plugin configuration does not contain supported MCP server entries")
    normalized = []
    for server_name, raw in servers.items():
        if not isinstance(server_name, str) or not isinstance(raw, dict):
            raise ValueError("Invalid MCP server entry")
        transport = raw.get("type", "stdio" if "command" in raw else "http")
        if transport not in {"http", "sse"}:
            raise ValueError(f"Unsupported plugin server transport for '{server_name}': {transport}")
        url = raw.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError(f"HTTP MCP server '{server_name}' requires url")
        parsed_url = urlsplit(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname or parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
            raise ValueError(f"Invalid MCP URL for server '{server_name}'")
        if parsed_url.scheme != "https" and parsed_url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError(f"Remote MCP server '{server_name}' must use HTTPS")
        headers = raw.get("headers", {})
        if not isinstance(headers, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()):
            raise ValueError(f"Invalid headers for MCP server '{server_name}'")
        normalized.append({"name": server_name, "url": url, "headers": headers, "transport": transport})
    return {
        "plugin": {"name": meta, "description": manifest.get("description", ""), "author": manifest.get("author", {})},
        "servers": normalized,
        "unsupported": ["plugin scripts/hooks/commands/agents/LSP are not executed by this resolver"],
    }


class MCPHTTPClient:
    """Synchronous JSON-RPC client for an MCP Streamable HTTP endpoint."""

    def __init__(self, config: MCPServerConfig):
        config.validate()
        self.config = config
        self._request_id = 0
        self._session_id: str | None = None
        self._initialized = False

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _post(self, payload: dict[str, Any], *, session: bool = True) -> dict[str, Any] | None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise MCPError("MCP request exceeds the configured size limit")
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        headers.update(self.config.headers)
        if session and self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        request = urllib.request.Request(self.config.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self._session_id = session_id
                raw = response.read(self.config.max_response_bytes + 1)
                if len(raw) > self.config.max_response_bytes:
                    raise MCPError("MCP server response exceeds the configured size limit")
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            # Never copy remote response bodies or request headers into surfaced errors.
            code = exc.code
            if code in {401, 403}:
                raise MCPError(f"MCP authentication/permission failed (HTTP {code})") from None
            if code == 404:
                raise MCPError("MCP endpoint not found (HTTP 404)") from None
            raise MCPError(f"MCP HTTP request failed (HTTP {code})") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MCPError(f"MCP connection failed ({type(exc).__name__})") from None
        if not raw:
            # Notifications may be answered with HTTP 202 and no body.
            return None
        try:
            if "text/event-stream" in content_type:
                text = raw.decode("utf-8")
                data_lines = [line[6:] for line in text.splitlines() if line.startswith("data: ")]
                if not data_lines:
                    return None
                envelope = json.loads("\n".join(data_lines))
            else:
                envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MCPError("MCP server returned an invalid response") from None
        if not isinstance(envelope, dict):
            raise MCPError("MCP server response must be a JSON object")
        return envelope

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        envelope = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        })
        if not isinstance(envelope, dict):
            raise MCPError("MCP server returned no JSON-RPC response")
        error = envelope.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            # Remote error messages may contain sensitive input; only expose the code.
            raise MCPError(f"MCP operation failed (JSON-RPC error {code})")
        result = envelope.get("result")
        if not isinstance(result, dict):
            raise MCPError("MCP server response is missing a result object")
        return result

    def initialize(self) -> dict[str, Any]:
        result = self._rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mosaic-core", "version": "0.1.0"},
        })
        if not isinstance(result.get("protocolVersion"), str):
            raise MCPError("MCP initialization response is missing protocolVersion")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session=True)
        self._initialized = True
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        result = self._rpc("tools/list")
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise MCPError("MCP tools/list returned an invalid tool catalog")
        normalized = []
        for item in tools:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            schema = item.get("inputSchema", {"type": "object", "properties": {}, "additionalProperties": False})
            if not isinstance(schema, dict) or schema.get("type") != "object" or not isinstance(schema.get("properties", {}), dict):
                continue
            normalized.append({
                "name": item["name"],
                "description": str(item.get("description", ""))[:2000],
                "input_schema": schema,
            })
        return normalized

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()
        if not isinstance(name, str) or not name or len(name) > 128:
            raise ValueError("Invalid MCP tool name")
        if not isinstance(arguments, dict):
            raise ValueError("MCP tool arguments must be an object")
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        encoded = json.dumps(result, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > self.config.max_response_bytes:
            raise MCPError("MCP tool result exceeds the configured size limit")
        if result.get("isError") is True:
            raise MCPError("MCP tool execution failed")
        return result


def qualified_tool_name(server_name: str, remote_name: str) -> str:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", value)[:80]
    if not isinstance(server_name, str) or not isinstance(remote_name, str) or not server_name or not remote_name:
        raise ValueError("Server and tool names are required")
    return f"mcp__{normalize(server_name)}__{normalize(remote_name)}"


def _resolved_headers(raw_headers: Mapping[str, str], environ: Mapping[str, str]) -> dict[str, str]:
    """Resolve only explicit ${ENV_NAME} header references; never interpolate command text."""
    resolved = {}
    for key, value in raw_headers.items():
        match = re.fullmatch(r"\$\{([A-Z][A-Z0-9_]*)\}", value)
        if match:
            env_value = environ.get(match.group(1), "")
            if not env_value:
                raise ValueError(f"Missing environment credential: {match.group(1)}")
            resolved[key] = env_value
        else:
            if re.search(r"\$\{[^}]+\}", value):
                raise ValueError("Only a single whole-value environment reference is supported in headers")
            resolved[key] = value
    return resolved
