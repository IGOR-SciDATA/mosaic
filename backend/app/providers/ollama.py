import json
from collections.abc import Iterable
from typing import Any
from urllib import error, request

from app.providers.base import ModelProvider


DEFAULT_REQUEST_TIMEOUT_SECONDS = 600


class OllamaProvider(ModelProvider):
    _THINKING_END = "</think>"

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        messages: list[dict[str, str]],
        model_name: str,
        configuration: dict[str, Any],
    ) -> str:
        payload = self._request_payload(messages, model_name, configuration, stream=False)
        timeout_seconds = self._request_timeout(configuration)
        response = self._post("/api/chat", payload, timeout_seconds=timeout_seconds)

        try:
            content = response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Invalid Ollama response") from exc

        return self._normalize_answer(content, model_name)

    def stream(
        self,
        messages: list[dict[str, str]],
        model_name: str,
        configuration: dict[str, Any],
    ) -> Iterable[str]:
        payload = self._request_payload(messages, model_name, configuration, stream=True)
        req = request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        inline_thinking = self._uses_inline_thinking(model_name)
        answer_started = not inline_thinking
        pending = ""

        try:
            with request.urlopen(req, timeout=self._request_timeout(configuration)) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue

                    chunk = json.loads(raw_line)
                    message = chunk.get("message", {})
                    content = message.get("content", "")

                    # Ollama may expose thinking in a separate field; in that case,
                    # message.content is already the user-facing answer.
                    if message.get("thinking"):
                        answer_started = True
                        pending = ""

                    if content:
                        if answer_started:
                            yield content
                        else:
                            pending += content
                            marker_index = pending.find(self._THINKING_END)
                            if marker_index >= 0:
                                answer = pending[marker_index + len(self._THINKING_END):].lstrip()
                                pending = ""
                                answer_started = True
                                if answer:
                                    yield answer

                    if chunk.get("done"):
                        break

            if not answer_started and pending:
                yield pending.strip()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama request failed ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not connect to Ollama: {exc.reason}") from exc

    @staticmethod
    def _request_timeout(configuration: dict[str, Any]) -> float:
        """Resolve a bounded per-request network timeout from model configuration."""
        raw_timeout = configuration.get(
            "request_timeout_seconds",
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("request_timeout_seconds must be a number between 1 and 600") from exc
        if not 1 <= timeout <= 600:
            raise ValueError("request_timeout_seconds must be between 1 and 600")
        return timeout

    @classmethod
    def _normalize_answer(cls, content: str, model_name: str) -> str:
        # Thinking tags are an output-format detail, not a model identity.
        if cls._THINKING_END in content:
            content = content.split(cls._THINKING_END, 1)[1]
        elif content.lstrip().startswith("<think>"):
            return ""
        return content.strip()

    @staticmethod
    def _uses_inline_thinking(model_name: str) -> bool:
        return model_name.strip().lower().split(":", 1)[0] == "qwen3"

    @staticmethod
    def _request_payload(
        messages: list[dict[str, str]],
        model_name: str,
        configuration: dict[str, Any],
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": stream,
            "think": configuration.get("think", False),
        }
        if configuration.get("format") == "json":
            payload["format"] = "json"

        options = {
            key: value
            for key, value in configuration.items()
            if key in {"temperature", "top_p", "top_k", "num_ctx", "num_predict"}
        }
        if options:
            payload["options"] = options
        return payload

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama request failed ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not connect to Ollama: {exc.reason}") from exc
