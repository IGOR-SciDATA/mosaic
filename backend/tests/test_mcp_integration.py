import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

from app.integrations.mcp.client import (
    MCPError,
    MCPHTTPClient,
    MCPServerConfig,
    parse_claude_plugin_config,
    qualified_tool_name,
)
from app.tools.mcp_adapter import MCPConnection, MCPRemoteTool
from app.tools.registry import ToolRegistry


class MCPHandler(BaseHTTPRequestHandler):
    calls = []
    tools = [{"name": "repo_info", "description": "Read repository metadata", "inputSchema": {
        "type": "object",
        "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
        "required": ["owner", "repo"],
        "additionalProperties": False,
    }}]

    def log_message(self, format, *args):
        return

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        envelope = json.loads(raw.decode("utf-8"))
        method = envelope.get("method")
        type(self).calls.append((method, self.headers.get("Authorization")))
        if self.headers.get("Authorization") == "Bearer bad-token":
            self.send_error(401)
            return
        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "test-mcp", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": self.tools}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": "repo found"}], "isError": False}
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"jsonrpc":"2.0","id":envelope.get("id"),"error":{"code":-32601,"message":"no"}}).encode())
            return
        body = json.dumps({"jsonrpc":"2.0","id":envelope.get("id"),"result":result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def mcp_url():
    MCPHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), MCPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/mcp"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_parse_official_style_plugin_config_without_executing_commands():
    manifest = json.dumps({"name": "github", "description": "Official GitHub MCP server", "author": {"name": "GitHub"}})
    mcp = json.dumps({"github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
                                  "headers": {"Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"}}})
    parsed = parse_claude_plugin_config(manifest, mcp)
    assert parsed["plugin"]["name"] == "github"
    assert parsed["servers"][0]["url"] == "https://api.githubcopilot.com/mcp/"
    assert parsed["servers"][0]["headers"]["Authorization"].endswith("${GITHUB_PERSONAL_ACCESS_TOKEN}")
    assert "not executed" in parsed["unsupported"][0]


@pytest.mark.parametrize("manifest,mcp", [
    ("not json", "{}"),
    ('{"name":"github"}', "[]"),
    ('{"name":"github"}', '{"github":{"type":"stdio","command":"evil"}}'),
    ('{"name":"github"}', '{"github":{"type":"http","url":"http://example.com"}}'),
])
def test_plugin_parser_rejects_invalid_or_unsupported_configs(manifest, mcp):
    with pytest.raises(ValueError):
        parse_claude_plugin_config(manifest, mcp)


def test_remote_server_discovery_and_call(mcp_url):
    client = MCPHTTPClient(MCPServerConfig("github", mcp_url, {"Authorization": "Bearer test-token"}))
    catalog = client.list_tools()
    assert catalog[0]["name"] == "repo_info"
    result = client.call_tool("repo_info", {"owner": "octo", "repo": "mosaic"})
    assert result["isError"] is False
    assert all(token is None or token == "Bearer test-token" for _, token in MCPHandler.calls)


def test_auth_errors_are_redacted(mcp_url):
    client = MCPHTTPClient(MCPServerConfig("github", mcp_url, {"Authorization": "Bearer bad-token"}))
    with pytest.raises(MCPError, match="HTTP 401") as exc:
        client.list_tools()
    assert "bad-token" not in str(exc.value)


def test_adapter_registers_namespaced_tool_and_rejects_disabled_connection(mcp_url):
    connection = MCPConnection("github", MCPServerConfig("github", mcp_url, {}))
    connection.refresh()
    descriptor = connection.tools["repo_info"]
    tool = MCPRemoteTool(connection, "repo_info", descriptor)
    assert tool.name == "mcp__github__repo_info"
    assert tool.permission_policy["approval_required"] is True
    tool.validate({"owner":"octo","repo":"mosaic"})
    with pytest.raises(ValueError):
        tool.validate({"owner":"octo"})
    connection.disconnect()
    with pytest.raises(ValueError, match="disabled"):
        tool.execute({"owner":"octo","repo":"mosaic"})


def test_qualified_names_are_stable_and_safe():
    assert qualified_tool_name("github", "pull-request.create") == "mcp__github__pull-request_create"
