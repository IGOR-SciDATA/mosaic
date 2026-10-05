from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    id: int | None
    name: str
    provider: str
    model_name: str
