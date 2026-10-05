from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]
    permission_policy: dict[str, Any]

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError

    def validate(self, arguments: dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")

        required = self.input_schema.get("required", [])
        for field in required:
            if field not in arguments:
                raise ValueError(f"Missing required argument: {field}")

        properties = self.input_schema.get("properties", {})
        for field, value in arguments.items():
            schema = properties.get(field)
            if schema is None:
                continue

            expected_type = schema.get("type")
            if expected_type == "string" and not isinstance(value, str):
                raise ValueError(f"Argument {field} must be a string")
            if expected_type == "number" and not isinstance(value, (int, float)):
                raise ValueError(f"Argument {field} must be a number")
            if expected_type == "object" and not isinstance(value, dict):
                raise ValueError(f"Argument {field} must be an object")
