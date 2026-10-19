from urllib import error, request
import json
import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.model import Model
from app.models.repository import create_model, get_model, list_models, update_model
from app.db.database import get_connection


class ModelCreate(BaseModel):
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    configuration: dict = Field(default_factory=dict)
    enabled: bool = True


class ModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    configuration: dict | None = None
    enabled: bool | None = None


class RemoteInferenceConfig(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


router = APIRouter(prefix="/models", tags=["models"])


_SECRET_FIELD = re.compile(r"(api.?key|authorization|access.?token|refresh.?token|password|secret|credential)", re.IGNORECASE)


def _reject_secret_configuration(value: object, path: str = "configuration") -> None:
    """Keep provider credentials out of model configuration returned by the API."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and _SECRET_FIELD.search(key):
                raise ValueError(f"{path} must not contain secret fields; configure credentials in the backend environment.")
            _reject_secret_configuration(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_configuration(nested, f"{path}[{index}]")




@router.post("", response_model=Model)
def create_model_endpoint(payload: ModelCreate) -> Model:
    try:
        _reject_secret_configuration(payload.configuration)
        return create_model(
            name=payload.name,
            provider=payload.provider,
            model_name=payload.model_name,
            configuration=payload.configuration,
            enabled=payload.enabled,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[Model])
def list_models_endpoint() -> list[Model]:
    return list_models()


@router.get("/remote-inference/config")
def get_remote_inference_config() -> dict:
    """Return the locally stored endpoint URL, never credentials."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("remote_inference_url",),
        ).fetchone()
    return {"url": row["value"] if row else os.environ.get("MOSAIC_REMOTE_INFERENCE_URL", "")}


@router.put("/remote-inference/config")
def save_remote_inference_config(payload: RemoteInferenceConfig) -> dict:
    """Persist endpoint URL locally; the bearer token remains backend-only in the environment."""
    from urllib.parse import urlparse

    value = payload.url.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Informe uma URL HTTP/HTTPS válida, sem credenciais embutidas.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=400, detail="Endpoints remotos devem usar HTTPS.")
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("remote_inference_url", value),
        )
        connection.commit()
    return {"url": value, "configured": bool(os.environ.get("MOSAIC_REMOTE_INFERENCE_TOKEN", "").strip())}


@router.get("/status")
def model_provider_status(provider: str = "ollama") -> dict:
    """Report Ollama reachability or whether OpenAI backend credentials are configured."""
    normalized = provider.strip().lower()
    if normalized == "openai":
        configured = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        return {
            "provider": "openai",
            "online": configured,
            "configured": configured,
            "running_models": [],
        }
    if normalized == "remote_inference":
        token = os.environ.get("MOSAIC_REMOTE_INFERENCE_TOKEN", "").strip()
        from app.providers.remote_inference import RemoteInferenceProvider
        try:
            provider = RemoteInferenceProvider()
            configured = bool(provider.base_url and token)
            # The server's liveness endpoint is intentionally lightweight; inference remains
            # the final compatibility check because server versions may expose different capabilities.
            req = request.Request(
                f"{provider.base_url}/health/ready",
                headers={"Authorization": f"Bearer {provider.token}", "Accept": "application/json"},
                method="GET",
            )
            with request.urlopen(req, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            ready = isinstance(payload, dict) and payload.get("status") in {"ready", "ok"}
            return {
                "provider": normalized,
                "online": bool(ready),
                "configured": True,
                "running_models": [payload.get("model")] if ready and payload.get("model") else [],
            }
        except (error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError, ValueError):
            return {"provider": normalized, "online": False, "configured": True, "running_models": []}
    if normalized != "ollama":
        return {"provider": normalized, "online": False, "configured": False, "running_models": []}
    try:
        with request.urlopen("http://localhost:11434/api/ps", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        running = [item.get("name") for item in payload.get("models", []) if item.get("name")]
        return {"provider": "ollama", "online": True, "running_models": running}
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return {"provider": "ollama", "online": False, "running_models": []}


@router.get("/{model_id}", response_model=Model)
def get_model_endpoint(model_id: int) -> Model:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.patch("/{model_id}", response_model=Model)
def update_model_endpoint(model_id: int, payload: ModelUpdate) -> Model:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        if payload.configuration is not None:
            _reject_secret_configuration(payload.configuration)
        return update_model(
            model_id,
            name=payload.name,
            configuration=payload.configuration,
            enabled=payload.enabled,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
