import json
from typing import Any

from app.db.database import get_connection
from app.models.model import Model


def create_model(
    name: str,
    provider: str,
    model_name: str,
    configuration: dict[str, Any] | None = None,
    enabled: bool = True,
) -> Model:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO models (name, provider, model_name, configuration, enabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                provider,
                model_name,
                json.dumps(configuration or {}),
                int(enabled),
            ),
        )
        connection.commit()

        return Model(
            id=cursor.lastrowid,
            name=name,
            provider=provider,
            model_name=model_name,
            configuration=configuration or {},
            enabled=enabled,
        )


def get_model(model_id: int) -> Model | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, provider, model_name, configuration, enabled
            FROM models
            WHERE id = ?
            """,
            (model_id,),
        ).fetchone()

    if row is None:
        return None

    return Model(
        id=row["id"],
        name=row["name"],
        provider=row["provider"],
        model_name=row["model_name"],
        configuration=json.loads(row["configuration"]),
        enabled=bool(row["enabled"]),
    )
