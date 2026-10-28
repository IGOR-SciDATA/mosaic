import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from app.services import hie_evidence


def test_persisted_evidence_is_registered_and_hash_verified(tmp_path, monkeypatch):
    registered = []

    monkeypatch.setattr(hie_evidence, "DATA_DIR", tmp_path)
    def register(**kwargs):
        artifact = SimpleNamespace(id=len(registered) + 1, path=kwargs["path"])
        registered.append((kwargs, artifact))
        return artifact
    monkeypatch.setattr(hie_evidence, "create_artifact", register)

    outputs = hie_evidence.persist_output_evidence(
        7, "baseline output", "candidate output", max_bytes=1024
    )
    for role, output in (
        ("baseline_output", "baseline output"),
        ("candidate_output", "candidate output"),
    ):
        ref = outputs[role]
        assert open(ref["path"], "rb").read() == output.encode("utf-8")
        assert ref["sha256"] == hashlib.sha256(output.encode("utf-8")).hexdigest()
    assert len(registered) == 2

    record = {"task_id": 7, "record_sha256": "abc123"}
    artifact = hie_evidence.persist_record_evidence(7, record, max_bytes=1024)
    stored = json.loads(open(artifact["path"], encoding="utf-8").read())
    assert stored == record
    assert registered[-1][0]["type"] == "hie_experiment_record"
    assert registered[-1][0]["metadata"]["record_sha256"] == "abc123"


def test_persist_output_evidence_enforces_combined_size_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(hie_evidence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(hie_evidence, "create_artifact", lambda **kwargs: None)
    try:
        hie_evidence.persist_output_evidence(7, "123", "456", max_bytes=5)
    except ValueError as exc:
        assert "Combined HIE output evidence" in str(exc)
    else:
        raise AssertionError("Expected combined evidence budget to be enforced")


def test_evidence_uses_initialized_core_artifact_repository(tmp_path, monkeypatch):
    from app.db import database
    from app.models.artifact_repository import list_artifacts

    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "mosaic.db")
    database.init_db()

    with database.get_connection() as connection:
        connection.execute(
            "INSERT INTO projects (name, workspace, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("HIE evidence test", str(tmp_path), "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        connection.execute(
            """INSERT INTO tasks (project_id, type, mode, status, created_at, updated_at)
               VALUES (1, 'generic', 'create', 'executing', ?, ?)""",
            ("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        connection.commit()

    monkeypatch.setattr(hie_evidence, "DATA_DIR", tmp_path / "data")
    outputs = hie_evidence.persist_output_evidence(
        1, "baseline output", "candidate output", max_bytes=1024
    )
    record = {
        "task_id": 1,
        "record_sha256": hashlib.sha256(b"record").hexdigest(),
        "evidence": outputs,
    }
    hie_evidence.persist_record_evidence(1, record, max_bytes=1024)

    artifacts = list_artifacts(1)
    assert [artifact.type for artifact in artifacts] == [
        "hie_baseline_output",
        "hie_candidate_output",
        "hie_experiment_record",
    ]
    assert all(artifact.metadata["sha256"] for artifact in artifacts[:2])
    assert artifacts[2].metadata["record_sha256"] == record["record_sha256"]
    assert all(Path(artifact.path).is_file() for artifact in artifacts)
