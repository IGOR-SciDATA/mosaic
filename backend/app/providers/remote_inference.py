"""Remote inference server adapter implementing Mosaic's existing ModelProvider contract.

Credentials are backend environment variables only. This adapter never falls back
to another provider and deliberately does not implement remote tool execution.
"""
import json
import os
from collections.abc import Iterable
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from app.providers.base import ModelProvider

DEFAULT_TIMEOUT_SECONDS = 90
MAX_TIMEOUT_SECONDS = 600


class RemoteInferenceProvider(ModelProvider):
    def __init__(self, base_url: str | None = None, token: str | None = None):
        raw_url = base_url if base_url is not None else os.getenv("MOSAIC_REMOTE_INFERENCE_URL", "")
        self.token = token if token is not None else os.getenv("MOSAIC_REMOTE_INFERENCE_TOKEN", "")
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Remote inference endpoint URL is invalid.")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Remote inference endpoint must use HTTPS.")
        self.base_url = raw_url.rstrip("/")
        if not self.token:
            raise RuntimeError("Remote inference credentials are not configured.")

    def generate(self, messages: list[dict[str, Any]], model_name: str, configuration: dict[str, Any]) -> str:
        payload = {
            "messages": self._messages(messages),
            "max_tokens": self._optional_int(configuration.get("max_output_tokens")),
            "temperature": self._optional_float(configuration.get("temperature")),
        }
        result = self._post("/v1/inference", payload, self._timeout(configuration))
        text = (result.get("output_text") or result.get("text")) if isinstance(result, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Remote inference server returned an invalid response.")
        return text

    def stream(self, messages: list[dict[str, Any]], model_name: str, configuration: dict[str, Any]) -> Iterable[str]:
        # RR3 stream protocol is explicit; a server without this capability fails closed.
        payload = {"messages": self._messages(messages)}
        req = request.Request(
            f"{self.base_url}/v1/inference/stream",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout(configuration)) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        value = line[5:].strip()
                        if value == "[DONE]":
                            return
                        if value:
                            yield value
        except error.HTTPError as exc:
            raise RuntimeError(self._safe_status_error(exc.code)) from None
        except (error.URLError, TimeoutError):
            raise RuntimeError("Remote inference server is unavailable or timed out.") from None

    def generate_with_tools(self, messages, model_name, configuration, tools):
        raise RuntimeError("Remote inference server does not advertise tool calling.")

    def _post(self, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        body = {key: value for key, value in payload.items() if value is not None}
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                if not isinstance(data, dict):
                    raise RuntimeError("Remote inference server returned an invalid response.")
                return data
        except error.HTTPError as exc:
            raise RuntimeError(self._safe_status_error(exc.code)) from None
        except (error.URLError, TimeoutError):
            raise RuntimeError("Remote inference server is unavailable or timed out.") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError("Remote inference server returned an invalid response.") from None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        if not isinstance(messages, list):
            raise ValueError("Messages must be a list.")
        output = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role, content = message.get("role"), message.get("content")
            if role in {"system", "user", "assistant"} and isinstance(content, str):
                output.append({"role": role, "content": content})
        if not output:
            raise ValueError("At least one text message is required.")
        return output

    @staticmethod
    def _timeout(configuration: dict[str, Any]) -> float:
        value = configuration.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        try:
            timeout = float(value)
        except (TypeError, ValueError):
            raise ValueError("request_timeout_seconds must be between 1 and 600.") from None
        if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
            raise ValueError("request_timeout_seconds must be between 1 and 600.")
        return timeout

    @staticmethod
    def _optional_int(value):
        if value is None:
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError("max_output_tokens must be a positive integer.") from None
        if value < 1 or value > 32768:
            raise ValueError("max_output_tokens must be between 1 and 32768.")
        return value

    @staticmethod
    def _optional_float(value):
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError("temperature must be between 0 and 2.") from None
        if not 0 <= value <= 2:
            raise ValueError("temperature must be between 0 and 2.")
        return value

    @staticmethod
    def _safe_status_error(status: int) -> str:
        if status in {401, 403}:
            return "Remote inference authentication failed."
        if status == 404:
            return "Remote inference endpoint or capability is unavailable."
        if status == 429:
            return "Remote inference server is busy; retry later."
        if status in {408, 504}:
            return "Remote inference request timed out."
        return "Remote inference request failed."
