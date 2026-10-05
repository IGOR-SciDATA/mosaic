import ast
import operator
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen
import json

from app.tools.base import Tool


class FilesystemTool(Tool):
    name = "filesystem"
    description = "Read, write and list files."
    input_schema = {
        "type": "object",
        "required": ["operation", "path"],
        "properties": {
            "operation": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
    }
    permission_policy = {"approval_required": True}

    def execute(self, arguments: dict[str, Any]) -> Any:
        operation = arguments["operation"]
        path = Path(arguments["path"])

        if operation == "read":
            return {"content": path.read_text(encoding="utf-8")}
        if operation == "write":
            content = arguments.get("content")
            if content is None:
                raise ValueError("content is required for write")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"path": str(path), "written": True}
        if operation == "list":
            return {"entries": [item.name for item in path.iterdir()]}

        raise ValueError(f"Unsupported filesystem operation: {operation}")


class TerminalTool(Tool):
    name = "terminal"
    description = "Execute a terminal command after Mosaic approval."
    input_schema = {
        "type": "object",
        "required": ["command"],
        "properties": {"command": {"type": "string"}},
    }
    permission_policy = {"approval_required": True}

    def execute(self, arguments: dict[str, Any]) -> Any:
        completed = subprocess.run(
            arguments["command"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a basic arithmetic expression."
    input_schema = {
        "type": "object",
        "required": ["expression"],
        "properties": {"expression": {"type": "string"}},
    }
    permission_policy = {"approval_required": False}

    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def execute(self, arguments: dict[str, Any]) -> Any:
        return {"result": self._evaluate(arguments["expression"])}

    def _evaluate(self, expression: str) -> int | float:
        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in self._operators:
                return self._operators[type(node.op)](visit(node.left), visit(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in self._operators:
                return self._operators[type(node.op)](visit(node.operand))
            raise ValueError("Unsupported calculator expression")

        return visit(ast.parse(expression, mode="eval"))


class SearchTool(Tool):
    name = "search"
    description = "Search the web using a public search endpoint."
    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {"query": {"type": "string"}},
    }
    permission_policy = {"approval_required": False}

    def execute(self, arguments: dict[str, Any]) -> Any:
        url = "https://www.google.com/search?q=" + quote(arguments["query"])
        request = __import__("urllib.request", fromlist=["Request"]).Request(
            url,
            headers={"User-Agent": "Mosaic/0.1"},
        )
        with urlopen(request, timeout=10) as response:
            return {"content": response.read().decode("utf-8", errors="replace")}


class WeatherTool(Tool):
    name = "weather"
    description = "Retrieve current weather for a latitude and longitude."
    input_schema = {
        "type": "object",
        "required": ["latitude", "longitude"],
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
        },
    }
    permission_policy = {"approval_required": False}

    def execute(self, arguments: dict[str, Any]) -> Any:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={arguments['latitude']}&longitude={arguments['longitude']}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
        )
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))


def register_builtin_tools() -> None:
    from app.tools.registry import registry

    for tool in (
        FilesystemTool(),
        TerminalTool(),
        SearchTool(),
        CalculatorTool(),
        WeatherTool(),
    ):
        if registry.get(tool.name) is None:
            registry.register(tool)
