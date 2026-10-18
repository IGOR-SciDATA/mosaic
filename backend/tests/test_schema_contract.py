import sqlite3

import pytest

from app.db.database import get_connection, init_db
from app.models.project_repository import create_project
from app.models.task_repository import create_task


@pytest.fixture
def database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "schema.db")
    init_db()
    yield


def test_mvp_artifact_and_setting_tables_match_contract(database):
    with get_connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {"artifacts", "settings", "task_events", "_mosaic_meta"} <= tables

        artifact_columns = {
            row["name"]: row for row in connection.execute("PRAGMA table_info(artifacts)")
        }
        assert list(artifact_columns) == [
            "id", "task_id", "type", "path", "metadata", "created_at"
        ]
        assert artifact_columns["id"]["pk"] == 1
        assert artifact_columns["task_id"]["notnull"] == 1
        assert artifact_columns["metadata"]["dflt_value"] == "'{}'"

        setting_columns = {
            row["name"]: row for row in connection.execute("PRAGMA table_info(settings)")
        }
        assert list(setting_columns) == ["key", "value"]
        assert setting_columns["key"]["pk"] == 1
        assert setting_columns["value"]["notnull"] == 1


def test_schema_initialization_is_idempotent_and_preserves_existing_data(database):
    project = create_project("Schema migration", "/tmp/mosaic-schema-test")
    task = create_task(
        type="generic",
        mode="agent",
        project_id=project.id,
        plan={"goal": "preserve existing data"},
    )
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO artifacts (task_id, type, path, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (task.id, "markdown", "Resumo.md", '{"verified": true}', "2026-10-18T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("theme", "dark"),
        )
        connection.commit()

    init_db()
    init_db()

    with get_connection() as connection:
        artifact = connection.execute(
            "SELECT task_id, type, path, metadata FROM artifacts WHERE task_id = ?",
            (task.id,),
        ).fetchone()
        setting = connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("theme",),
        ).fetchone()
    assert artifact is not None
    assert artifact["path"] == "Resumo.md"
    assert artifact["metadata"] == '{"verified": true}'
    assert setting["value"] == "dark"


def test_artifacts_cascade_when_their_task_is_deleted(database):
    project = create_project("Artifact cascade", "/tmp/mosaic-artifact-cascade")
    task = create_task(type="generic", mode="agent", project_id=project.id)
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO artifacts (task_id, type, path, created_at) VALUES (?, ?, ?, ?)",
            (task.id, "markdown", "Resumo.md", "2026-10-18T00:00:00Z"),
        )
        connection.execute("DELETE FROM tasks WHERE id = ?", (task.id,))
        connection.commit()
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM artifacts WHERE task_id = ?",
            (task.id,),
        ).fetchone()["count"]
    assert count == 0
