from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.model import Model
from app.models.repository import create_model, get_model, list_models


class ModelCreate(BaseModel):
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    configuration: dict = Field(default_factory=dict)
    enabled: bool = True


router = APIRouter(prefix="/models", tags=["models"])


@router.post("", response_model=Model)
def create_model_endpoint(payload: ModelCreate) -> Model:
    try:
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


@router.get("/{model_id}", response_model=Model)
def get_model_endpoint(model_id: int) -> Model:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model
