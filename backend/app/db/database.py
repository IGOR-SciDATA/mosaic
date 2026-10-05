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
        connection.execute(\n            """\n            CREATE TABLE IF NOT EXISTS models (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                name TEXT NOT NULL,\n                provider TEXT NOT NULL,\n                model_name TEXT NOT NULL\n            )\n            """\n        )\n        connection.commit()
