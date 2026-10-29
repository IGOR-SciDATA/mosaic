import ast
import hashlib
import io
from datetime import datetime, timezone
import json
from itertools import islice
import math
import operator
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Callable
from urllib.parse import quote
from xml.sax.saxutils import escape
from urllib.request import Request

from app.tools.safe_http import safe_urlopen

from app.tools.base import Tool

MAX_FILE_BYTES = 1_000_000
MAX_READ_LINES = 80
MAX_READ_CHARS = 5_000
MAX_LIST_ENTRIES = 500
# Workspace discovery has no arbitrary file-count, per-file, aggregate-byte, or wall-clock cap.
# OS permissions, the active workspace boundary, cancellation, and model context capacity still apply.
WORKSPACE_EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
    ".next", ".nuxt", ".cache", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".venv", "venv", "env", "virtualenv", "coverage",
    ".idea", ".vscode", ".ssh", ".aws", ".azure", ".gnupg", ".kube",
    "target", "out", "tmp", "temp",
}
WORKSPACE_SECRET_NAMES = {
    ".env", ".env.local", ".env.production", ".npmrc", ".pypirc",
    "id_rsa", "id_dsa", "id_ed25519", "authorized_keys", "known_hosts",
    "credentials", "credentials.json", "secrets.json", "service-account.json",
}
MAX_COMMAND_LENGTH = 2_000
MAX_PROCESS_OUTPUT_BYTES = 200_000
COMMAND_TIMEOUT_SECONDS = 30


def _require_workspace(workspace: Path | None) -> Path:
    if workspace is None:
        raise ValueError("An active project workspace is required for this tool")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve(strict=True)


def _workspace_path(root: Path, raw_path: str, *, allow_root: bool = True) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise ValueError("A non-empty valid workspace path is required")
    candidate_input = Path(raw_path)
    if any(part == ".." for part in candidate_input.parts):
        raise ValueError("Path traversal is not allowed")
    candidate = candidate_input if candidate_input.is_absolute() else root / candidate_input
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError("Path must remain inside the active workspace") from exc
    if not allow_root and resolved == root:
        raise ValueError("The workspace root cannot be used for this operation")
    # Reject existing symlinks in every path component, even when they point inward.
    relative = resolved.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink paths are not allowed in workspace operations")
    return resolved


class FilesystemTool(Tool):
    name = "filesystem"
    description = "List, read, create and write files inside the active project workspace."
    input_schema = {
        "type": "object",
        "required": ["operation", "path"],
        "additionalProperties": False,
        "properties": {
            "operation": {"type": "string", "enum": ["read", "write", "create", "mkdir", "list", "explore", "search"], "maxLength": 16},
            "path": {"type": "string", "minLength": 1, "maxLength": 2048},
            "content": {"type": "string", "maxLength": MAX_FILE_BYTES},
            "overwrite": {"type": "boolean"},
            "start_line": {"type": "integer", "minimum": 1, "maximum": 1_000_000},
            "max_lines": {"type": "integer", "minimum": 1, "maximum": 200},
            "max_files": {"type": ["integer", "null"], "minimum": 1},
            "max_file_bytes": {"type": ["integer", "null"], "minimum": 1},
            "max_total_bytes": {"type": ["integer", "null"], "minimum": 1},
            "query": {"type": "string", "minLength": 1, "maxLength": 300},
            "search_in": {"type": "string", "enum": ["name", "content", "both"]},
            "max_matches": {"type": ["integer", "null"], "minimum": 1},
        },
    }
    permission_policy = {"approval_required": True, "scope": "active_workspace"}

    def validate(self, arguments: dict[str, Any]) -> None:
        """Validate operation-specific arguments before policy or execution."""
        super().validate(arguments)
        operation = arguments["operation"]

        if operation in {"create", "write"} and "content" not in arguments:
            raise ValueError(f"Missing required argument(s): content for operation {operation}")
        if operation not in {"create", "write"} and "content" in arguments:
            raise ValueError(f"Argument content is not allowed for operation {operation}")
        if operation != "write" and "overwrite" in arguments:
            raise ValueError("Argument overwrite is only allowed for operation write")
        if operation != "read" and ({"start_line", "max_lines"} & set(arguments)):
            raise ValueError("Arguments start_line and max_lines are only allowed for operation read")
        if operation not in {"explore", "search"} and ({"max_files", "max_file_bytes", "max_total_bytes"} & set(arguments)):
            raise ValueError("Workspace exploration limits are only allowed for operation explore/search")
        for key in ("max_files", "max_file_bytes", "max_total_bytes", "max_matches"):
            if key in arguments and arguments[key] is not None and (not isinstance(arguments[key], int) or isinstance(arguments[key], bool) or arguments[key] < 1):
                raise ValueError(f"Argument {key} must be a positive integer or null")
        if operation == "search" and "query" not in arguments:
            raise ValueError("Argument query is required for operation search")
        if operation != "search" and ({"query", "search_in", "max_matches"} & set(arguments)):
            raise ValueError("Search arguments are only allowed for operation search")

    def policy_for(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Allow harmless workspace reads without approval; keep side effects gated."""
        if arguments.get("operation") in {"read", "list", "explore", "search"}:
            return {**self.permission_policy, "approval_required": False}
        return self.permission_policy

    def execute(self, arguments: dict[str, Any], *, workspace: Path | None = None, cancel_check: Callable[[], bool] | None = None) -> Any:
        root = _require_workspace(workspace)
        operation = arguments["operation"]
        path = _workspace_path(root, arguments["path"], allow_root=operation in {"list", "mkdir", "explore", "search"})
        if operation == "search":
            return _search_workspace(
                root,
                query=arguments["query"],
                search_in=arguments.get("search_in", "both"),
                max_matches=arguments.get("max_matches"),
                max_files=arguments.get("max_files"),
                max_file_bytes=arguments.get("max_file_bytes"),
                max_total_bytes=arguments.get("max_total_bytes"),
            )
        if operation == "explore":
            return _explore_workspace(
                root,
                max_files=arguments.get("max_files"),
                max_file_bytes=arguments.get("max_file_bytes"),
                max_total_bytes=arguments.get("max_total_bytes"),
                cancel_check=cancel_check,
            )
        if operation == "read":
            path = _workspace_path(root, arguments["path"], allow_root=False)
            if not path.is_file():
                raise ValueError("The requested workspace file does not exist")
            with path.open("rb") as handle:
                raw = handle.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise ValueError("File exceeds the read limit")
            text = raw.decode("utf-8")
            lines = text.splitlines(keepends=True)
            total_lines = len(lines)
            start_line = arguments.get("start_line", 1)
            max_lines = arguments.get("max_lines", MAX_READ_LINES)
            if total_lines and start_line > total_lines:
                raise ValueError("start_line exceeds the file line count")
            selected_lines = []
            chunk_chars = 0
            for line in lines[start_line - 1:start_line - 1 + max_lines]:
                if len(line) > MAX_READ_CHARS:
                    if not selected_lines:
                        raise ValueError("A single line exceeds the filesystem read chunk limit")
                    break
                if chunk_chars + len(line) > MAX_READ_CHARS:
                    break
                selected_lines.append(line)
                chunk_chars += len(line)
            chunk = "".join(selected_lines)
            end_line = start_line + len(selected_lines) - 1
            truncated = end_line < total_lines
            return {
                "operation": "read",
                "status": "success",
                "path": path.relative_to(root).as_posix(),
                "start_line": start_line,
                "end_line": end_line,
                "total_lines": total_lines,
                "truncated": truncated,
                "next_start_line": end_line + 1 if truncated else None,
                "content": chunk,
                "bytes": len(chunk.encode("utf-8")),
            }
        if operation == "list":
            path = _workspace_path(root, arguments["path"], allow_root=True)
            if not path.is_dir():
                raise ValueError("The requested workspace directory does not exist")
            sampled = list(islice(path.iterdir(), MAX_LIST_ENTRIES + 1))
            truncated = len(sampled) > MAX_LIST_ENTRIES
            entries = sorted(item.name for item in sampled[:MAX_LIST_ENTRIES])
            return {"operation": "list", "status": "success", "path": "." if path == root else path.relative_to(root).as_posix(), "entries": entries, "count": len(entries), "truncated": truncated}
        if operation == "mkdir":
            path = _workspace_path(root, arguments["path"], allow_root=True)
            existed = path.is_dir()
            path.mkdir(parents=True, exist_ok=True)
            if not path.is_dir():
                raise OSError("Directory creation could not be verified")
            return {"operation": "mkdir", "status": "success", "path": "." if path == root else path.relative_to(root).as_posix(), "created": not existed}
        if operation in {"write", "create"}:
            content = arguments.get("content")
            if content is None:
                raise ValueError("content is required for write/create")
            if len(content.encode("utf-8")) > MAX_FILE_BYTES:
                raise ValueError("File content exceeds the write limit")
            overwrite = arguments.get("overwrite", False)
            existed = path.exists()
            if existed and not path.is_file():
                raise ValueError("The destination exists and is not a regular file")
            if existed and (operation == "create" or not overwrite):
                raise FileExistsError("File already exists; set overwrite=true to replace it")
            path.parent.mkdir(parents=True, exist_ok=True)
            # Re-check after parent creation immediately before the side effect.
            path = _workspace_path(root, arguments["path"], allow_root=False)
            existed = path.exists()
            if existed and not path.is_file():
                raise ValueError("The destination exists and is not a regular file")
            if existed and (operation == "create" or not overwrite):
                raise FileExistsError("File already exists; set overwrite=true to replace it")
            encoded = content.encode("utf-8")
            temporary = path.with_name(f".{path.name}.mosaic-tmp")
            try:
                # Write bytes, not text: Windows text mode translates LF to CRLF,
                # making the subsequent UTF-8 byte-length check fail after the
                # destination has already been replaced.
                with temporary.open("xb") as handle:
                    handle.write(encoded)
                if path.exists() and (operation == "create" or not overwrite):
                    raise FileExistsError("File already exists; set overwrite=true to replace it")
                os.replace(temporary, path)
                if not path.is_file() or path.read_bytes() != encoded:
                    raise OSError("Written file could not be verified")
            finally:
                if temporary.exists():
                    temporary.unlink()
            return {"operation": operation, "status": "success", "path": path.relative_to(root).as_posix(), "written": True, "created": not existed, "overwritten": existed, "bytes": len(encoded)}
        raise ValueError(f"Unsupported filesystem operation: {operation}")


def _validate_command(tokens: list[str], root: Path) -> None:
    if not tokens:
        raise ValueError("Command is empty")
    # Deliberately support common inspection and validation commands, not arbitrary shell.
    exact_commands = {
        ("pwd",), ("ls",), ("ls", "-la"), ("ls", "-al"),
        ("git", "status"), ("git", "diff"), ("git", "log"), ("git", "ls-files"),
        ("git", "diff", "--stat"), ("git", "log", "-5"),
        ("pytest",), ("python", "-m", "pytest"),
        ("python", "-m", "compileall", "."),
        ("npm", "run", "build"), ("npm", "test"),
    }
    if tuple(tokens) in exact_commands:
        return
    if tokens[:3] == ["python", "-m", "pytest"] and len(tokens) > 3:
        path_tokens = tokens[3:]
        if any(token.startswith("-") for token in path_tokens):
            raise ValueError("Command options are not supported for path-scoped commands")
        for raw in path_tokens:
            _workspace_path(root, raw)
        return
    if tokens[0] in {"cat", "ls", "pytest"} and len(tokens) >= 2:
        if any(token.startswith("-") for token in tokens[1:]):
            raise ValueError("Command options are not supported for path-scoped commands")
        for raw in tokens[1:]:
            _workspace_path(root, raw, allow_root=tokens[0] == "ls")
        return
    raise ValueError("Command is not in the supported non-interactive command allowlist")


def _read_capped(stream, output: bytearray, cap: int, truncation: dict[str, bool], key: str) -> None:
    while True:
        chunk = stream.read(8192)
        if not chunk:
            return
        remaining = cap - len(output)
        if remaining > 0:
            output.extend(chunk[:remaining])
        if len(chunk) > max(remaining, 0):
            truncation[key] = True


def _stop_process_tree(process: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            if process.poll() is not None:
                return
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5, check=False,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            # Kill the process group even if its leader exited but a child retained the pipes.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except (OSError, subprocess.SubprocessError):
        if process.poll() is None:
            process.kill()


class TerminalTool(Tool):
    name = "terminal"
    description = "Run a limited set of non-interactive inspection and validation commands in the active workspace."
    input_schema = {
        "type": "object",
        "required": ["command"],
        "additionalProperties": False,
        "properties": {"command": {"type": "string", "minLength": 1, "maxLength": MAX_COMMAND_LENGTH}},
    }
    permission_policy = {"approval_required": True, "scope": "active_workspace", "timeout_seconds": COMMAND_TIMEOUT_SECONDS}

    def execute(self, arguments: dict[str, Any], *, workspace: Path | None = None, cancel_check: Callable[[], bool] | None = None) -> Any:
        root = _require_workspace(workspace)
        command = arguments["command"]
        if re.search(r"[|;&><\x60$()\n\r]", command):
            raise ValueError("Shell operators and compound commands are not supported")
        try:
            tokens = shlex.split(command, posix=(os.name != "nt"))
        except ValueError as exc:
            raise ValueError("Invalid command quoting") from exc
        _validate_command(tokens, root)

        # Handle the portable workspace query without depending on a platform-specific
        # executable (Windows does not ship a `pwd` command).
        if tokens == ["pwd"]:
            return {
                "status": "success",
                "returncode": 0,
                "stdout": f"{root}{os.linesep}",
                "stderr": "",
                "output_truncated": False,
                "duration_ms": 0,
                "cwd": ".",
            }

        # Use the same interpreter running Mosaic for Python validation commands.
        # A bare `python` may resolve to another installation that lacks pytest.
        if tokens[0] == "python":
            tokens[0] = sys.executable

        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(root), "PYTHONNOUSERSITE": "1"}
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
            if key in os.environ:
                env[key] = os.environ[key]
        started_at = time.monotonic()
        try:
            process = subprocess.Popen(
                tokens,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=(os.name != "nt"),
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
            )
        except OSError as exc:
            return {
                "status": "launch_failure", "returncode": None, "stdout": "",
                "stderr": str(exc), "duration_ms": round((time.monotonic() - started_at) * 1000),
            }
        stdout_buffer, stderr_buffer = bytearray(), bytearray()
        truncation = {"stdout": False, "stderr": False}
        stdout_thread = threading.Thread(target=_read_capped, args=(process.stdout, stdout_buffer, MAX_PROCESS_OUTPUT_BYTES, truncation, "stdout"), daemon=True)
        stderr_thread = threading.Thread(target=_read_capped, args=(process.stderr, stderr_buffer, MAX_PROCESS_OUTPUT_BYTES, truncation, "stderr"), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        stop_status = None
        deadline = started_at + COMMAND_TIMEOUT_SECONDS
        while process.poll() is None:
            if cancel_check is not None:
                try:
                    cancellation_requested = cancel_check()
                except Exception:
                    cancellation_requested = True
                if cancellation_requested:
                    stop_status = "cancelled"
                    _stop_process_tree(process)
                    break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_status = "timeout"
                _stop_process_tree(process)
                break
            try:
                process.wait(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                continue
        if stop_status is not None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _stop_process_tree(process)
                process.wait()
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        if stop_status is not None:
            return {
                "status": stop_status, "returncode": None,
                "stdout": stdout_buffer.decode("utf-8", errors="replace"),
                "stderr": stderr_buffer.decode("utf-8", errors="replace"),
                "output_truncated": truncation["stdout"] or truncation["stderr"],
                "timeout_seconds": COMMAND_TIMEOUT_SECONDS if stop_status == "timeout" else None,
                "duration_ms": round((time.monotonic() - started_at) * 1000),
            }
        return {
            "status": "success" if process.returncode == 0 else "non_zero_exit",
            "returncode": process.returncode,
            "stdout": stdout_buffer.decode("utf-8", errors="replace"),
            "stderr": stderr_buffer.decode("utf-8", errors="replace"),
            "output_truncated": truncation["stdout"] or truncation["stderr"],
            "duration_ms": round((time.monotonic() - started_at) * 1000),
            "cwd": ".",
        }


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a basic arithmetic expression."
    input_schema = {
        "type": "object", "required": ["expression"], "additionalProperties": False,
        "properties": {"expression": {"type": "string", "minLength": 1, "maxLength": 500}},
    }
    permission_policy = {"approval_required": False}

    _operators = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def execute(self, arguments: dict[str, Any], *, workspace: Path | None = None, cancel_check: Callable[[], bool] | None = None) -> Any:
        return {"result": self._evaluate(arguments["expression"])}

    def _evaluate(self, expression: str) -> int | float:
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 100:
            raise ValueError("Calculator expression is too complex")

        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in self._operators:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                    raise ValueError("Calculator exponent exceeds the safety limit")
                result = self._operators[type(node.op)](left, right)
                if isinstance(result, int) and result.bit_length() > 4096:
                    raise ValueError("Calculator integer result exceeds the safety limit")
                if isinstance(result, float) and not math.isfinite(result):
                    raise ValueError("Calculator result must be finite")
                return result
            if isinstance(node, ast.UnaryOp) and type(node.op) in self._operators:
                return self._operators[type(node.op)](visit(node.operand))
            raise ValueError("Unsupported calculator expression")

        result = visit(tree)
        if isinstance(result, float) and not math.isfinite(result):
            raise ValueError("Calculator result must be finite")
        return result


class SearchTool(Tool):
    name = "search"
    description = "Search the web using a public search endpoint."
    input_schema = {
        "type": "object", "required": ["query"], "additionalProperties": False,
        "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 500}},
    }
    permission_policy = {"approval_required": True, "scope": "public_web"}

    def execute(self, arguments: dict[str, Any], *, workspace: Path | None = None, cancel_check: Callable[[], bool] | None = None) -> Any:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        url = "https://html.duckduckgo.com/html/?q=" + quote(arguments["query"])
        request = Request(url, headers={"User-Agent": "Mosaic/0.1"})
        try:
            with safe_urlopen(request, timeout=10) as response:
                raw = response.read(1_000_001)
                truncated = len(raw) > 1_000_000
                parser = _SearchResultsParser()
                parser.feed(raw[:1_000_000].decode("utf-8", errors="replace"))
                results_truncated = len(parser.results) > 10
                results = parser.results[:10]
                for index, result in enumerate(results, start=1):
                    result["rank"] = index
                    result["provider"] = "DuckDuckGo"
                    result["retrieved_at"] = retrieved_at
                return {
                    "status": "success" if results else "no_results",
                    "query": arguments["query"],
                    "provider": "DuckDuckGo",
                    "results": results,
                    "retrieved_at": retrieved_at,
                    "truncated": truncated or results_truncated,
                }
        except Exception as exc:
            return {
                "status": "provider_error",
                "query": arguments["query"],
                "provider": "DuckDuckGo",
                "results": [],
                "retrieved_at": retrieved_at,
                "error": f"{type(exc).__name__}: {exc}",
            }


class _SearchResultsParser:
    def __init__(self):
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, unquote, urljoin, urlsplit

        class Parser(HTMLParser):
            def __init__(self, outer):
                super().__init__(convert_charrefs=True)
                self.outer = outer
                self.current = None
                self.capture = None
                self.capture_tag = None

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                classes = set((attrs.get("class") or "").split())
                if tag == "a" and "result__a" in classes:
                    self._finish()
                    href = attrs.get("href", "")
                    href = urljoin("https://html.duckduckgo.com", href)
                    parsed = urlsplit(href)
                    target = parse_qs(parsed.query).get("uddg", [None])[0]
                    if target:
                        href = unquote(target)
                    if urlsplit(href).scheme in {"http", "https"} and urlsplit(href).hostname:
                        self.current = {"title": "", "url": href, "snippet": ""}
                        self.capture = "title"
                        self.capture_tag = "a"
                elif self.current is not None and "result__snippet" in classes:
                    self.capture = "snippet"
                    self.capture_tag = tag

            def handle_data(self, data):
                if self.current is not None and self.capture in {"title", "snippet"}:
                    piece = " ".join(data.split())
                    if piece:
                        self.current[self.capture] += (" " if self.current[self.capture] else "") + piece

            def handle_endtag(self, tag):
                if self.capture_tag == tag:
                    self.capture = None
                    self.capture_tag = None

            def _finish(self):
                if self.current and self.current["title"].strip():
                    self.outer.results.append({
                        "title": self.current["title"].strip()[:300],
                        "url": self.current["url"],
                        "snippet": self.current["snippet"].strip()[:500],
                    })
                self.current = None
                self.capture = None
                self.capture_tag = None

            def close(self):
                super().close()
                self._finish()

        self.results = []
        self.parser = Parser(self)

    def feed(self, content: str) -> None:
        self.parser.feed(content)
        self.parser.close()


class ArtifactTool(Tool):
    name = "artifact"
    description = "Create Markdown, PDF, DOCX, XLSX or PPTX artifacts and validate them after reopening."
    permission_policy = {"approval_required": True, "scope": "active_workspace"}
    input_schema = {
        "type": "object",
        "required": ["format", "path", "content"],
        "additionalProperties": False,
        "properties": {
            "format": {"type": "string", "enum": ["markdown", "pdf", "docx", "xlsx", "pptx"]},
            "path": {"type": "string", "minLength": 1, "maxLength": 300},
            "content": {"type": "string", "maxLength": 50_000},
            "title": {"type": "string", "maxLength": 300},
        },
    }
    _EXTENSIONS = {
        "markdown": {".md", ".markdown"}, "pdf": {".pdf"}, "docx": {".docx"},
        "xlsx": {".xlsx"}, "pptx": {".pptx"},
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        fmt = arguments["format"]
        if Path(arguments["path"]).suffix.lower() not in self._EXTENSIONS[fmt]:
            raise ValueError(f"Artifact path extension does not match format {fmt}")
        if fmt == "xlsx":
            self._parse_workbook_content(arguments["content"])

    @staticmethod
    def _markdown_blocks(content: str) -> list[tuple[str, int, str]]:
        blocks = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            heading = re.match(r"^(#{1,3})\s+(.+)$", line)
            if heading:
                blocks.append(("heading", len(heading.group(1)), heading.group(2).strip()))
            elif re.match(r"^(?:[-*])\s+", line):
                blocks.append(("bullet", 0, re.sub(r"^(?:[-*])\s+", "", line, count=1)))
            elif re.match(r"^\d+[.)]\s+", line):
                blocks.append(("number", 0, re.sub(r"^\d+[.)]\s+", "", line, count=1)))
            else:
                blocks.append(("paragraph", 0, line))
        return blocks

    @staticmethod
    def _parse_workbook_content(content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("XLSX content must be JSON with a sheets array") from exc
        sheets = payload.get("sheets") if isinstance(payload, dict) else None
        if not isinstance(sheets, list) or not 1 <= len(sheets) <= 20:
            raise ValueError("XLSX content must contain 1 to 20 sheets")
        names, total_cells = set(), 0
        for sheet in sheets:
            if not isinstance(sheet, dict):
                raise ValueError("Each XLSX sheet must be an object")
            name, rows = sheet.get("name"), sheet.get("rows")
            if not isinstance(name, str) or not name.strip() or len(name) > 31:
                raise ValueError("XLSX sheet names must contain 1 to 31 characters")
            if any(char in name for char in "[]:*?/\\") or name in names:
                raise ValueError("XLSX sheet name is invalid or duplicated")
            names.add(name)
            if not isinstance(rows, list) or not 1 <= len(rows) <= 1_000:
                raise ValueError(f"Sheet {name} must contain 1 to 1000 rows")
            for row in rows:
                if not isinstance(row, list) or not 1 <= len(row) <= 100:
                    raise ValueError(f"Rows in sheet {name} must contain 1 to 100 cells")
                total_cells += len(row)
                for value in row:
                    if value is None or isinstance(value, (str, int, float, bool)):
                        if isinstance(value, str) and len(value) > 10_000:
                            raise ValueError("XLSX cell text exceeds 10000 characters")
                    elif not (
                        isinstance(value, dict) and set(value) == {"formula"}
                        and isinstance(value["formula"], str)
                        and value["formula"].startswith("=") and len(value["formula"]) <= 1_000
                    ):
                        raise ValueError("XLSX cells must be scalar values or explicit formula objects")
        if total_cells > 10_000:
            raise ValueError("XLSX content exceeds 10000 cells")
        return payload

    def _render_pdf(self, content: str, title: str) -> bytes:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4, title=title)
        styles, story = getSampleStyleSheet(), []
        for kind, level, text in self._markdown_blocks(content):
            rendered = escape(text)
            if kind in {"bullet", "number"}:
                rendered = "&#8226; " + rendered
            story.extend([Paragraph(rendered, styles[f"Heading{level}"] if kind == "heading" else styles["BodyText"]), Spacer(1, 5)])
        if not story:
            raise ValueError("PDF content must not be empty")
        document.build(story)
        return buffer.getvalue()

    def _render_docx(self, content: str, title: str) -> bytes:
        from docx import Document

        document = Document()
        document.core_properties.title = title
        for kind, level, text in self._markdown_blocks(content):
            if kind == "heading":
                document.add_heading(text, level=level)
            elif kind == "bullet":
                document.add_paragraph(text, style="List Bullet")
            elif kind == "number":
                document.add_paragraph(text, style="List Number")
            else:
                document.add_paragraph(text)
        if not any(paragraph.text.strip() for paragraph in document.paragraphs):
            raise ValueError("DOCX content must not be empty")
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _render_xlsx(self, content: str) -> bytes:
        from openpyxl import Workbook

        payload = self._parse_workbook_content(content)
        workbook = Workbook()
        workbook.remove(workbook.active)
        for sheet_data in payload["sheets"]:
            worksheet = workbook.create_sheet(sheet_data["name"])
            for row in sheet_data["rows"]:
                output_row = []
                for value in row:
                    if isinstance(value, dict) and set(value) == {"formula"}:
                        output_row.append(value["formula"])
                    elif isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                        output_row.append("'" + value)
                    else:
                        output_row.append(value)
                worksheet.append(output_row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def _render_pptx(self, content: str, title: str) -> bytes:
        from pptx import Presentation

        presentation = Presentation()
        default_title = title or "Presentation"
        slides, current_title, current_blocks = [], default_title, []
        for block in self._markdown_blocks(content):
            kind, _level, text = block
            if kind == "heading":
                if current_blocks or current_title != default_title:
                    slides.append((current_title, current_blocks))
                current_title, current_blocks = text, []
            else:
                current_blocks.append(block)
        if current_blocks or not slides:
            slides.append((current_title, current_blocks))
        if len(slides) > 100:
            raise ValueError("PPTX content exceeds 100 slides")
        for slide_title, blocks in slides:
            slide = presentation.slides.add_slide(presentation.slide_layouts[1])
            slide.shapes.title.text = slide_title[:250]
            frame = slide.placeholders[1].text_frame
            frame.clear()
            for index, (kind, _level, text) in enumerate(blocks):
                paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
                paragraph.text = text
                if kind in {"bullet", "number"}:
                    paragraph.level = 0
        buffer = io.BytesIO()
        presentation.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _expected_marker(content: str) -> str:
        for line in content.splitlines():
            line = line.strip()
            if line:
                line = re.sub(r"^#{1,3}\s+", "", line)
                return re.sub(r"^(?:[-*]|\d+[.)])\s+", "", line)[:100]
        return ""

    def _validate_reopened(self, fmt: str, data: bytes, content: str) -> dict[str, Any]:
        marker = self._expected_marker(content)
        if fmt == "markdown":
            reopened = data.decode("utf-8")
            if reopened != content or not reopened.strip():
                raise ValueError("Markdown re-open validation failed")
            return {"valid": True, "method": "utf8_exact_content", "characters": len(reopened)}
        if fmt == "pdf":
            from pypdf import PdfReader
            document = PdfReader(io.BytesIO(data))
            extracted = "\n".join(page.extract_text() or "" for page in document.pages)
            if not document.pages or not extracted.strip() or (marker and marker not in extracted):
                raise ValueError("PDF re-open validation failed")
            return {"valid": True, "method": "pypdf_reopen_and_text_check", "pages": len(document.pages)}
        if fmt == "docx":
            from docx import Document
            document = Document(io.BytesIO(data))
            extracted = "\n".join(paragraph.text for paragraph in document.paragraphs)
            if not extracted.strip() or (marker and marker not in extracted):
                raise ValueError("DOCX re-open validation failed")
            return {"valid": True, "method": "python_docx_reopen_and_text_check", "paragraphs": len(document.paragraphs)}
        if fmt == "xlsx":
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(data), data_only=False, read_only=True)
            cells = sum(sheet.max_row * sheet.max_column for sheet in workbook.worksheets)
            if not workbook.sheetnames or cells <= 0:
                raise ValueError("XLSX re-open validation failed")
            return {"valid": True, "method": "openpyxl_reopen_and_structure_check", "sheets": workbook.sheetnames, "cells": cells}
        if fmt == "pptx":
            from pptx import Presentation
            presentation = Presentation(io.BytesIO(data))
            extracted = "\n".join(shape.text for slide in presentation.slides for shape in slide.shapes if hasattr(shape, "text"))
            if not presentation.slides or not extracted.strip() or (marker and marker not in extracted):
                raise ValueError("PPTX re-open validation failed")
            return {"valid": True, "method": "python_pptx_reopen_and_text_check", "slides": len(presentation.slides)}
        raise ValueError(f"Unsupported artifact format: {fmt}")

    def execute(self, arguments: dict[str, Any], *, workspace: Path | None = None, cancel_check: Callable[[], bool] | None = None) -> dict[str, Any]:
        root = _require_workspace(workspace)
        fmt, relative_path = arguments["format"], arguments["path"]
        title = arguments.get("title") or Path(relative_path).stem
        if cancel_check and cancel_check():
            return {"status": "cancelled", "path": relative_path, "format": fmt}
        target = _workspace_path(root, relative_path)
        if target.exists():
            raise FileExistsError(f"Artifact already exists: {relative_path}")
        content = arguments["content"]
        if fmt == "markdown":
            data = content.encode("utf-8")
        elif fmt == "pdf":
            data = self._render_pdf(content, title)
        elif fmt == "docx":
            data = self._render_docx(content, title)
        elif fmt == "xlsx":
            data = self._render_xlsx(content)
        else:
            data = self._render_pptx(content, title)
        if not data or len(data) > MAX_FILE_BYTES:
            raise ValueError(f"Generated artifact must be between 1 and {MAX_FILE_BYTES} bytes")
        self._validate_reopened(fmt, data, content)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _workspace_path(root, relative_path)
        if cancel_check and cancel_check():
            return {"status": "cancelled", "path": relative_path, "format": fmt}
        if target.exists():
            raise FileExistsError(f"Artifact already exists: {relative_path}")
        with target.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        reopened = target.read_bytes()
        validation = self._validate_reopened(fmt, reopened, content)
        return {
            "status": "success", "operation": "create",
            "path": target.relative_to(root).as_posix(), "format": fmt,
            "bytes": len(reopened), "sha256": hashlib.sha256(reopened).hexdigest(),
            "validation": validation, "reopened": True,
        }


class WeatherTool(Tool):
    name = "weather"
    description = "Retrieve current weather for a latitude and longitude."
    input_schema = {
        "type": "object", "required": ["latitude", "longitude"], "additionalProperties": False,
        "properties": {
            "latitude": {"type": "number", "minimum": -90, "maximum": 90},
            "longitude": {"type": "number", "minimum": -180, "maximum": 180},
        },
    }
    permission_policy = {"approval_required": True, "scope": "public_web"}

    def execute(self, arguments: dict[str, Any], *, workspace: Path | None = None, cancel_check: Callable[[], bool] | None = None) -> Any:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={arguments['latitude']}&longitude={arguments['longitude']}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
        )
        with safe_urlopen(url, timeout=10) as response:
            payload = json.loads(response.read(500_001).decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("current"), dict):
            return {
                "status": "provider_error",
                "provider": "Open-Meteo",
                "retrieved_at": retrieved_at,
                "error": str(payload.get("reason", "Weather response did not contain current conditions"))[:500]
                if isinstance(payload, dict) else "Invalid weather response",
            }
        return {
            "status": "success",
            "provider": "Open-Meteo",
            "retrieved_at": retrieved_at,
            "data": payload,
        }



class _ReadableHTML:
    """Small standard-library HTML extractor; scripts and styles are discarded."""

    def __init__(self):
        from html.parser import HTMLParser

        class Parser(HTMLParser):
            def __init__(self, outer):
                super().__init__(convert_charrefs=True)
                self.outer = outer
                self.skip_depth = 0
                self.in_title = False

            def handle_starttag(self, tag, attrs):
                tag = tag.lower()
                if tag in {"script", "style", "noscript", "svg"}:
                    self.skip_depth += 1
                if tag == "title":
                    self.in_title = True

            def handle_endtag(self, tag):
                tag = tag.lower()
                if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
                    self.skip_depth -= 1
                if tag == "title":
                    self.in_title = False

            def handle_data(self, data):
                if self.skip_depth:
                    return
                text = " ".join(data.split())
                if not text:
                    return
                if self.in_title and not self.outer.title:
                    self.outer.title = text[:300]
                self.outer.parts.append(text)

        self.title = ""
        self.parts = []
        self.parser = Parser(self)

    def feed(self, content: str) -> None:
        self.parser.feed(content)


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Read a public HTTP/HTTPS page as bounded text; private and local destinations are blocked."
    input_schema = {
        "type": "object", "required": ["url"], "additionalProperties": False,
        "properties": {"url": {"type": "string", "minLength": 8, "maxLength": 2048}},
    }
    permission_policy = {"approval_required": True, "scope": "public_web", "timeout_seconds": 10}

    def execute(self, arguments: dict[str, Any], *, workspace: Path | None = None, cancel_check: Callable[[], bool] | None = None) -> Any:
        request = Request(arguments["url"], headers={"User-Agent": "Mosaic/0.1"})
        with safe_urlopen(request, timeout=10) as response:
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ValueError(f"Unsupported page content type: {content_type}")
            raw = response.read(1_000_001)
            truncated = len(raw) > 1_000_000
            text = raw[:1_000_000].decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            if content_type == "text/plain":
                title = response.geturl()
                content = text
            else:
                parser = _ReadableHTML()
                parser.feed(text)
                title = parser.title or response.geturl()
                content = "\n".join(parser.parts)
            return {
                "url": response.geturl(),
                "title": title[:300],
                "content_type": content_type,
                "content": content[:100_000],
                "truncated": truncated or len(content) > 100_000,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

def _is_sensitive_workspace_path(relative_path: str) -> bool:
    name = Path(relative_path).name.casefold()
    if name in WORKSPACE_SECRET_NAMES or name.startswith(".env."):
        return True
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".keystore")):
        return True
    return any(token in name for token in ("secret", "credential", "private_key", "id_rsa", "id_ed25519"))


def _explore_workspace(
    root: Path,
    *,
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Discover and read eligible UTF-8 text files deterministically under the authorized root."""
    started = time.monotonic()
    excluded_dirs = {name.casefold() for name in WORKSPACE_EXCLUDED_DIRS}
    directories: set[str] = {"."}
    found: list[Path] = []
    ignored: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    contents: list[dict[str, Any]] = []
    total_bytes = 0
    limits: list[str] = []
    root = root.resolve(strict=True)

    def record_walk_error(error: OSError) -> None:
        raw_path = getattr(error, "filename", None)
        try:
            relative = Path(raw_path).relative_to(root).as_posix() if raw_path else "."
        except ValueError:
            relative = "."
        failures.append({"path": relative, "reason": "directory_scan_error"})

    for current_dir, dir_names, file_names in os.walk(
        root, topdown=True, onerror=record_walk_error, followlinks=False
    ):
        if cancel_check is not None and cancel_check():
            limits.append("cancelled")
            break
        current = Path(current_dir)
        try:
            current.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            ignored.append({"path": ".", "reason": "directory_outside_workspace"})
            dir_names[:] = []
            continue
        kept_dirs = []
        for name in sorted(dir_names):
            candidate = current / name
            relative = candidate.relative_to(root).as_posix()
            try:
                if name.casefold() in excluded_dirs:
                    ignored.append({"path": relative, "reason": "excluded_directory"})
                    continue
                if candidate.is_symlink():
                    ignored.append({"path": relative, "reason": "symlink"})
                    continue
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
                if not resolved.is_dir():
                    ignored.append({"path": relative, "reason": "not_directory"})
                    continue
                directories.add(relative)
                kept_dirs.append(name)
            except (OSError, ValueError):
                ignored.append({"path": relative, "reason": "unsafe_or_unreadable_directory"})
        dir_names[:] = kept_dirs
        for name in sorted(file_names):
            candidate = current / name
            relative = candidate.relative_to(root).as_posix()
            if candidate.is_symlink():
                ignored.append({"path": relative, "reason": "symlink"})
                continue
            if _is_sensitive_workspace_path(relative):
                ignored.append({"path": relative, "reason": "sensitive_filename"})
                continue
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
                if not resolved.is_file():
                    ignored.append({"path": relative, "reason": "not_regular_file"})
                    continue
                found.append(resolved)
            except (OSError, ValueError):
                failures.append({"path": relative, "reason": "path_or_stat_error"})
        if "time_limit" in limits:
            break

    found.sort(key=lambda item: item.relative_to(root).as_posix().casefold())
    files_found = len(found)
    for candidate in found:
        if cancel_check is not None and cancel_check():
            limits.append("cancelled")
            break
        if time.monotonic() - started >= WORKSPACE_SCAN_TIMEOUT_SECONDS:
            limits.append("time_limit")
            break
        relative = candidate.relative_to(root).as_posix()
        if max_files is not None and len(contents) >= max_files:
            if "max_files" not in limits:
                limits.append("max_files")
            ignored.append({"path": relative, "reason": "max_files_limit"})
            continue
        try:
            size = candidate.stat().st_size
            if max_file_bytes is not None and size > max_file_bytes:
                limits.append("max_file_bytes")
                ignored.append({"path": relative, "reason": "file_size_limit"})
                continue
            if max_total_bytes is not None and total_bytes + size > max_total_bytes:
                limits.append("max_total_bytes")
                ignored.append({"path": relative, "reason": "total_bytes_limit"})
                continue
            with candidate.open("rb") as handle:
                raw = handle.read(max_file_bytes + 1 if max_file_bytes is not None else -1)
            if max_file_bytes is not None and len(raw) > max_file_bytes:
                limits.append("max_file_bytes")
                ignored.append({"path": relative, "reason": "file_size_limit"})
                continue
            if b"\x00" in raw:
                ignored.append({"path": relative, "reason": "binary_content"})
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                ignored.append({"path": relative, "reason": "unsupported_encoding"})
                continue
            import hashlib
            contents.append({
                "path": relative,
                "content": text,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
            total_bytes += len(raw)
        except OSError:
            failures.append({"path": relative, "reason": "read_error"})

    return {
        "operation": "explore",
        "status": "success" if not limits and not failures else "partial",
        "workspace": str(root),
        "directories_found": len(directories),
        "directories": sorted(directories, key=str.casefold),
        "files_found": files_found,
        "files_read": len(contents),
        "files_ignored": len(ignored),
        "files_failed": len(failures),
        "bytes_read": total_bytes,
        "duration_ms": max(0, round((time.monotonic() - started) * 1000)),
        "limits_reached": sorted(set(limits)),
        "files": contents,
        "ignored": ignored,
        "failures": failures,
    }


def _search_workspace(
    root: Path,
    *,
    query: str,
    search_in: str,
    max_matches: int | None = None,
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
) -> dict[str, Any]:
    """Search eligible workspace paths/content using the same bounded, safe explorer."""
    exploration = _explore_workspace(
        root,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    for item in exploration["files"]:
        relative = item["path"]
        name_match = needle in relative.casefold() if search_in in {"name", "both"} else False
        line_matches = []
        if search_in in {"content", "both"}:
            for line_number, line in enumerate(item["content"].splitlines(), start=1):
                if needle in line.casefold():
                    line_matches.append({"line": line_number, "preview": line[:300]})
                    if len(line_matches) >= 5:
                        break
        if name_match or line_matches:
            matches.append({
                "path": relative,
                "name_match": name_match,
                "content_matches": line_matches,
            })
            if max_matches is not None and len(matches) >= max_matches:
                exploration["limits_reached"] = sorted(set(exploration["limits_reached"] + ["max_matches"]))
                break
    return {
        "operation": "search",
        "status": exploration["status"] if not exploration["limits_reached"] else "partial",
        "workspace": exploration["workspace"],
        "query": query,
        "search_in": search_in,
        "directories_found": exploration["directories_found"],
        "files_found": exploration["files_found"],
        "files_searched": exploration["files_read"],
        "files_ignored": exploration["files_ignored"],
        "files_failed": exploration["files_failed"],
        "bytes_scanned": exploration["bytes_read"],
        "duration_ms": exploration["duration_ms"],
        "limits_reached": exploration["limits_reached"],
        "matches": matches,
        "ignored": exploration["ignored"],
        "failures": exploration["failures"],
    }




def register_builtin_tools() -> None:
    from app.tools.registry import registry
    for tool in (FilesystemTool(), ArtifactTool(), TerminalTool(), SearchTool(), WebFetchTool(), CalculatorTool(), WeatherTool()):
        if registry.get(tool.name) is None:
            registry.register(tool)
