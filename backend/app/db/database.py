import sqlite3

from app.core.config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS _mosaic_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                configuration TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(models)").fetchall()
        }

        if "configuration" not in columns:
            connection.execute(
                "ALTER TABLE models ADD COLUMN configuration TEXT NOT NULL DEFAULT '{}'"
            )

        if "enabled" not in columns:
            connection.execute(
                "ALTER TABLE models ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
            )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_models_provider_model_name
            ON models (provider, model_name)
            """
        )
        connection.commit()
