"""OpenAI Responses API adapter implementing the Mosaic ModelProvider contract."""

import json
import os
from collections.abc import Iterable
from typing import Any
from urllib import error, request


DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
API_URL = "https://api.openai.com/v1/responses"


class OpenAIProvider:
    """OpenAI Responses API provider; credentials are read only from backend env."""

    def generate(
        self,
        messages: list[dict[str, Any]],
        model_name: str,
        configuration: dict[str, Any],
    ) -> str:
        response = self._post(self._payload(messages, model_name, configuration, stream=False), configuration)
        text = self._response_text(response)
        if not text.strip():
            raise RuntimeError("OpenAI returned an empty response.")
        return text

    def stream(
        self,
        messages: list[dict[str, Any]],
        model_name: str,
        configuration: dict[str, Any],
    ) -> Iterable[str]:
        payload = self._payload(messages, model_name, configuration, stream=True)
        req = self._request(payload, configuration)
        try:
            with request.urlopen(req, timeout=self._timeout(configuration)) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError("OpenAI returned an invalid streaming event.") from exc
                    event_type = event.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event.get("delta")
                        if isinstance(delta, str) and delta:
                            yield delta
                    elif event_type == "response.failed":
                        raise RuntimeError(self._safe_response_error(event))
                    elif event_type == "error":
                        raise RuntimeError(self._safe_response_error(event))
        except error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except error.URLError as exc:
            raise RuntimeError("Could not connect to OpenAI API. Check network access and timeout.") from exc
        except TimeoutError as exc:
            raise RuntimeError("OpenAI API request timed out.") from exc

    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        model_name: str,
        configuration: dict[str, Any],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Translate Mosaic's Chat-Completions-shaped tool catalog to Responses API tools."""
        payload = self._payload(messages, model_name, configuration, stream=False)
        payload["tools"] = [self._response_tool(tool) for tool in tools]
        response = self._post(payload, configuration)
        output = response.get("output", [])
        for item in output if isinstance(output, list) else []:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            name = item.get("name")
            arguments = item.get("arguments", "{}")
            try:
                parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.JSONDecodeError:
                parsed = arguments
            return {
                "type": "tool_call",
                "tool": name if isinstance(name, str) else "",
                "arguments": parsed,
            }
        content = self._response_text(response)
        if not content.strip():
            raise RuntimeError("OpenAI returned neither a tool call nor a text response.")
        return {"type": "final", "content": content}

    @staticmethod
    def _response_tool(tool: dict[str, Any]) -> dict[str, Any]:
        function = tool.get("function", {}) if isinstance(tool, dict) else {}
        if not isinstance(function, dict):
            raise ValueError("Invalid tool schema for OpenAI Responses API.")
        name = function.get("name")
        parameters = function.get("parameters")
        if not isinstance(name, str) or not name or not isinstance(parameters, dict):
            raise ValueError("Invalid tool schema for OpenAI Responses API.")
        result = {
            "type": "function",
            "name": name,
            "parameters": parameters,
            "strict": False,
        }
        description = function.get("description")
        if isinstance(description, str) and description:
            result["description"] = description
        return result

    @staticmethod
    def _payload(
        messages: list[dict[str, Any]],
        model_name: str,
        configuration: dict[str, Any],
        *,
        stream: bool,
    ) -> dict[str, Any]:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("OpenAI model identifier must not be empty.")
        input_messages = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "developer", "user", "assistant"}:
                # Mosaic's current chat context uses these four text roles. Do not
                # reinterpret tool/function records as user-authored instructions.
                continue
            if isinstance(content, str):
                input_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                input_messages.append({"role": role, "content": content})
        payload: dict[str, Any] = {
            "model": model_name.strip(),
            "input": input_messages,
            "stream": stream,
        }
        max_tokens = configuration.get("max_output_tokens", configuration.get("num_predict"))
        if max_tokens is not None:
            try:
                max_tokens = int(max_tokens)
            except (TypeError, ValueError) as exc:
                raise ValueError("max_output_tokens must be a positive integer.") from exc
            if max_tokens > 0:
                payload["max_output_tokens"] = min(max_tokens, 131072)
        # Temperature is intentionally omitted: OpenAI reasoning models may reject it.
        return payload

    @staticmethod
    def _timeout(configuration: dict[str, Any]) -> float:
        raw = configuration.get("request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)
        try:
            timeout = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("request_timeout_seconds must be between 1 and 600.") from exc
        if not 1 <= timeout <= 600:
            raise ValueError("request_timeout_seconds must be between 1 and 600.")
        return timeout

    @staticmethod
    def _request(payload: dict[str, Any], configuration: dict[str, Any]) -> request.Request:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OpenAI is selected, but OPENAI_API_KEY is not configured in the backend environment.")
        return request.Request(
            API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream" if payload.get("stream") else "application/json",
            },
            method="POST",
        )

    def _post(self, payload: dict[str, Any], configuration: dict[str, Any]) -> dict[str, Any]:
        req = self._request(payload, configuration)
        try:
            with request.urlopen(req, timeout=self._timeout(configuration)) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except error.URLError as exc:
            raise RuntimeError("Could not connect to OpenAI API. Check network access and timeout.") from exc
        except TimeoutError as exc:
            raise RuntimeError("OpenAI API request timed out.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI returned an invalid JSON response.") from exc
        if not isinstance(data, dict):
            raise RuntimeError("OpenAI returned an invalid response.")
        if data.get("error"):
            raise RuntimeError(self._safe_response_error(data))
        return data

    @staticmethod
    def _http_error(exc: error.HTTPError) -> RuntimeError:
        if exc.code in (401, 403):
            return RuntimeError("OpenAI authentication failed. Verify OPENAI_API_KEY and API access.")
        if exc.code == 404:
            return RuntimeError("OpenAI model or endpoint was not found. Verify the model identifier.")
        if exc.code == 429:
            return RuntimeError("OpenAI rate limit or quota exceeded. Check API usage and billing.")
        if exc.code in (408, 504):
            return RuntimeError("OpenAI API request timed out.")
        return RuntimeError(f"OpenAI API request failed with HTTP {exc.code}.")

    @staticmethod
    def _safe_response_error(payload: dict[str, Any]) -> str:
        error_data = payload.get("error")
        if not isinstance(error_data, dict):
            response = payload.get("response")
            error_data = response.get("error") if isinstance(response, dict) else None
        code = error_data.get("code") if isinstance(error_data, dict) else None
        if code in {"rate_limit_exceeded", "insufficient_quota"}:
            return "OpenAI rate limit or quota exceeded. Check API usage and billing."
        if code in {"invalid_api_key", "authentication_error"}:
            return "OpenAI authentication failed. Verify OPENAI_API_KEY and API access."
        return "OpenAI could not complete the request. Check the model, request settings, and API status."

    @staticmethod
    def _response_text(response: dict[str, Any]) -> str:
        output_text = response.get("output_text")
        if isinstance(output_text, str):
            return output_text
        pieces = []
        output = response.get("output", [])
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for part in item.get("content", []):
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        text = part.get("text")
                        if isinstance(text, str):
                            pieces.append(text)
        return "".join(pieces)
