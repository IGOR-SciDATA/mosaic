"""Durable HIE evidence backed by the Core Artifact repository.

Evidence files live outside disposable workspaces. SQLite stores only Artifact
metadata; the file bytes remain under the application's data directory.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR
from app.models.artifact_repository import create_artifact


def _write_artifact(task_id: int, name: str, content: bytes, *, artifact_type: str, metadata: dict[str, Any], max_bytes: int) -> dict[str, Any]:
    if len(content) > max_bytes:
        raise ValueError("HIE evidence exceeds the configured artifact-size budget")
    root = (DATA_DIR / "artifacts" / "hie" / f"task-{task_id}").resolve()
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError("HIE evidence directory must not be a symlink")
    path = root / name
    if path.exists() and path.is_symlink():
        raise ValueError("HIE evidence path must not be a symlink")
    digest = hashlib.sha256(content).hexdigest()
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists() and temporary.is_symlink():
        raise ValueError("HIE evidence temporary path must not be a symlink")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    resolved = path.resolve()
    if resolved.parent != root:
        raise ValueError("HIE evidence path escaped its task directory")
    artifact_metadata = {**metadata, "sha256": digest, "size_bytes": len(content)}
    artifact = create_artifact(
        task_id=task_id,
        type=artifact_type,
        path=str(resolved),
        metadata=artifact_metadata,
    )
    return {"artifact_id": artifact.id, "path": artifact.path, "sha256": digest, "size_bytes": len(content)}


def persist_output_evidence(task_id: int, baseline_output: str, candidate_output: str, *, max_bytes: int) -> dict[str, dict[str, Any]]:
    baseline = baseline_output.encode("utf-8")
    candidate = candidate_output.encode("utf-8")
    if len(baseline) + len(candidate) > max_bytes:
        raise ValueError("Combined HIE output evidence exceeds the artifact-size budget")
    return {
        "baseline_output": _write_artifact(
            task_id, f"baseline-output-{hashlib.sha256(baseline).hexdigest()[:16]}.txt", baseline, artifact_type="hie_baseline_output",
            metadata={"role": "baseline_output"}, max_bytes=max_bytes,
        ),
        "candidate_output": _write_artifact(
            task_id, f"candidate-output-{hashlib.sha256(candidate).hexdigest()[:16]}.txt", candidate, artifact_type="hie_candidate_output",
            metadata={"role": "candidate_output"}, max_bytes=max_bytes,
        ),
    }


def persist_record_evidence(task_id: int, record: dict[str, Any], *, max_bytes: int) -> dict[str, Any]:
    content = (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return _write_artifact(
        task_id, f"experiment-record-{record[\"record_sha256\"][:16]}.json", content, artifact_type="hie_experiment_record",
        metadata={"role": "experiment_record", "record_sha256": record["record_sha256"]},
        max_bytes=max_bytes,
    )
