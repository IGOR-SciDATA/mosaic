import json
from collections.abc import Iterable
from typing import Any
from urllib import error, request

from app.providers.base import ModelProvider


class OllamaProvider(ModelProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        messages: list[dict[str, str]],
        model_name: str,
        configuration: dict[str, Any],
    ) -> str:
        payload = self._request_payload(messages, model_name, configuration, stream=False)
        response = self._post("/api/chat", payload)

        try:
            return response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Invalid Ollama response") from exc

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

        try:
            with request.urlopen(req) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue

                    chunk = json.loads(raw_line)
                    content = chunk.get("message", {}).get("content")
                    if content:
                        yield content

                    if chunk.get("done"):
                        break
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama request failed ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not connect to Ollama: {exc.reason}") from exc

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
        }

        options = {
            key: value
            for key, value in configuration.items()
            if key in {"temperature", "top_p", "top_k", "num_ctx", "num_predict"}
        }
        if options:
            payload["options"] = options

        return payload

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama request failed ({exc.code}): {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not connect to Ollama: {exc.reason}") from exc
