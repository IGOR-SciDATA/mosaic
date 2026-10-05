from app.db.database import init_db
from app.models.repository import create_model, get_model


def test_model_persistence() -> None:
    init_db()

    created = create_model(
        name="Qwen 3B",
        provider="qwen",
        model_name="qwen3-3b",
    )

    recovered = get_model(created.id)

    assert recovered == created
