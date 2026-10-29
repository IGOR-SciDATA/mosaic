"""Tests for the generic MCP client and adapter using a local HTTP protocol fixture."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.integrations.mcp.client import MCPError, MCPHTTPClient, MCPServerConfig, parse_claude_plugin_config, qualified_tool_name
from app.tools.mcp_adapter import MCPConnection, MCPRemoteTool


class MCPHandler(BaseHTTPRequestHandler):
    calls = []
    tools = [{"name": "repo_info", "description": "Read repository metadata", "inputSchema": {
        "type": "object",
        "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
        "required": ["owner", "repo"], "additionalProperties": False,
    }}]

    def log_message(self, format, *args):
        return

    def do_POST(self):
        envelope = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode())
        method = envelope.get("method")
        type(self).calls.append((method, self.headers.get("Authorization")))
        if self.headers.get("Authorization") == "Bearer bad-token":
            self.send_error(401)
            return
        if method == "notifications/initialized":
            self.send_response(202); self.end_headers(); return
        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "fixture", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": type(self).tools}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": "repository found"}], "isError": False}
        else:
            result = {}
        body = json.dumps({"jsonrpc": "2.0", "id": envelope.get("id"), "result": result}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


@pytest.fixture
def mcp_url():
    MCPHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), MCPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/mcp"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_parse_official_style_github_plugin_config():
    manifest = json.dumps({"name":"github", "description":"GitHub MCP", "author":{"name":"GitHub"}})
    mcp = json.dumps({"github":{"type":"http","url":"https://api.githubcopilot.com/mcp/","headers":{"Authorization":"Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"}}})
    parsed = parse_claude_plugin_config(manifest, mcp)
    assert parsed["plugin"]["name"] == "github"
    assert parsed["servers"][0]["url"] == "https://api.githubcopilot.com/mcp/"
    assert "not executed" in parsed["unsupported"][0]


@pytest.mark.parametrize("manifest,mcp", [
    ("bad json", "{}"),
    ('{"name":"github"}', "[]"),
    ('{"name":"github"}', '{"github":{"type":"stdio","command":"unexpected"}}'),
    ('{"name":"github"}', '{"github":{"type":"http","url":"http://example.com"}}'),
])
def test_parser_rejects_invalid_or_unsafe_config(manifest, mcp):
    with pytest.raises(ValueError):
        parse_claude_plugin_config(manifest, mcp)


def test_discovery_initialization_and_tool_call(mcp_url):
    client = MCPHTTPClient(MCPServerConfig("github", mcp_url, {"Authorization":"Bearer test-token"}))
    tools = client.list_tools()
    assert tools[0]["name"] == "repo_info"
    assert client.call_tool("repo_info", {"owner":"octo","repo":"mosaic"})["isError"] is False
    assert [method for method, _ in MCPHandler.calls][:2] == ["initialize", "notifications/initialized"]


def test_auth_error_never_echoes_secret(mcp_url):
    client = MCPHTTPClient(MCPServerConfig("github", mcp_url, {"Authorization":"Bearer bad-token"}))
    with pytest.raises(MCPError, match="HTTP 401") as error:
        client.list_tools()
    assert "bad-token" not in str(error.value)


def test_adapter_requires_valid_schema_and_enabled_connection(mcp_url):
    connection = MCPConnection("github", MCPServerConfig("github", mcp_url, {}))
    connection.refresh()
    tool = MCPRemoteTool(connection, "repo_info", connection.tools["repo_info"])
    assert tool.name == "mcp__github__repo_info"
    assert tool.permission_policy["approval_required"] is True
    tool.validate({"owner":"octo","repo":"mosaic"})
    with pytest.raises(ValueError):
        tool.validate({"owner":"octo"})
    connection.disconnect()
    with pytest.raises(ValueError, match="disabled"):
        tool.execute({"owner":"octo","repo":"mosaic"})


def test_qualified_name_and_config_security():
    assert qualified_tool_name("github", "pull-request.create") == "mcp__github__pull-request_create"
    with pytest.raises(ValueError, match="HTTPS"):
        MCPServerConfig("remote", "http://example.com/mcp", {}).validate()


def test_response_size_limit(mcp_url):
    client = MCPHTTPClient(MCPServerConfig("github", mcp_url, {}, max_response_bytes=10))
    with pytest.raises(MCPError, match="size limit"):
        client.initialize()
