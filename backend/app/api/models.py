from urllib import error, request
import json
import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.model import Model
from app.models.repository import create_model, get_model, list_models, update_model


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
        endpoint = os.environ.get("MOSAIC_REMOTE_INFERENCE_URL", "").strip().rstrip("/")
        token = os.environ.get("MOSAIC_REMOTE_INFERENCE_TOKEN", "").strip()
        configured = bool(endpoint and token)
        if not configured:
            return {"provider": normalized, "online": False, "configured": False, "running_models": []}
        from app.providers.remote_inference import RemoteInferenceProvider
        try:
            provider = RemoteInferenceProvider()
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
