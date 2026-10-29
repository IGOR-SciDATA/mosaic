"""Durable HIE evidence backed by the Core Artifact repository.

Evidence bytes are stored outside disposable workspaces and referenced through
Core Artifacts. This is application-level path hardening, not an OS sandbox.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR
from app.models.artifact_repository import create_artifact


def _metadata_bytes(metadata: dict[str, Any], content: bytes) -> int:
    complete = {**metadata, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
    return len(json.dumps(complete, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _ensure_real_directory(path: Path) -> Path:
    """Create a directory and reject symlinks, including broken symlinks."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except FileExistsError as exc:
        if path.is_symlink():
            raise ValueError("HIE evidence directories must not be symlinks") from exc
        raise ValueError("HIE evidence path is not a directory") from exc
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValueError("HIE evidence directory could not be created") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ValueError("HIE evidence directories must be real directories, not symlinks")
    return path.resolve(strict=True)


def _check_evidence_directories(root: Path) -> Path:
    """Check each HIE-controlled path component before canonicalizing it."""
    data_root = Path(DATA_DIR).absolute()
    current = data_root
    for component in ("artifacts", "hie"):
        current = current / component
        _ensure_real_directory(current)
    task_root = current / root.name
    return _ensure_real_directory(task_root)


def _write_artifact(
    task_id: int,
    name: str,
    content: bytes,
    *,
    artifact_type: str,
    metadata: dict[str, Any],
    max_bytes: int,
) -> dict[str, Any]:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("HIE evidence byte budget must be a positive integer")
    metadata_size = _metadata_bytes(metadata, content)
    if len(content) + metadata_size > max_bytes:
        raise ValueError("HIE evidence file and Artifact metadata exceed the configured byte budget")
    if Path(name).name != name or name in {"", ".", ".."}:
        raise ValueError("HIE evidence filename must be a simple basename")

    root = _check_evidence_directories(Path(DATA_DIR).absolute() / "artifacts" / "hie" / f"task-{task_id}")
    path = root / name
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        mode = None
    if mode is not None and (stat.S_ISLNK(mode) or not stat.S_ISREG(mode)):
        raise ValueError("HIE evidence destination must be a regular file, not a symlink or special file")

    digest = hashlib.sha256(content).hexdigest()
    descriptor, temporary_name = tempfile.mkstemp(prefix=".hie-evidence-", suffix=".tmp", dir=str(root))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # Unique temporary names avoid collisions. Recheck the destination
        # immediately before replacing it; this does not claim race-free OS sandboxing.
        try:
            current_mode = path.lstat().st_mode
        except FileNotFoundError:
            current_mode = None
        if current_mode is not None and (
            stat.S_ISLNK(current_mode) or not stat.S_ISREG(current_mode)
        ):
            raise ValueError("HIE evidence destination changed to an unsafe file type")
        if path.parent.resolve(strict=True) != root:
            raise ValueError("HIE evidence path escaped its task directory")
        os.replace(temporary, path)
        stored_mode = path.lstat().st_mode
        if stat.S_ISLNK(stored_mode) or not stat.S_ISREG(stored_mode):
            raise ValueError("HIE evidence result is not a regular file")
        if path.parent.resolve(strict=True) != root:
            raise ValueError("HIE evidence path escaped its task directory")
        if path.stat().st_size != len(content):
            raise ValueError("HIE evidence size could not be verified")
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

    artifact_metadata = {**metadata, "sha256": digest, "size_bytes": len(content)}
    artifact = create_artifact(
        task_id=task_id,
        type=artifact_type,
        path=str(path),
        metadata=artifact_metadata,
    )
    return {
        "artifact_id": artifact.id,
        "path": artifact.path,
        "sha256": digest,
        "size_bytes": len(content),
        "metadata_bytes": len(json.dumps(artifact_metadata, ensure_ascii=False, sort_keys=True).encode("utf-8")),
        "budget_bytes": len(content) + len(json.dumps(artifact_metadata, ensure_ascii=False, sort_keys=True).encode("utf-8")),
    }


def persist_output_evidence(
    task_id: int,
    baseline_output: str,
    candidate_output: str,
    *,
    max_bytes: int,
) -> dict[str, dict[str, Any]]:
    baseline = baseline_output.encode("utf-8")
    candidate = candidate_output.encode("utf-8")
    baseline_meta = {"role": "baseline_output"}
    candidate_meta = {"role": "candidate_output"}
    total = (
        len(baseline) + _metadata_bytes(baseline_meta, baseline)
        + len(candidate) + _metadata_bytes(candidate_meta, candidate)
    )
    if total > max_bytes:
        raise ValueError("Combined HIE output evidence and metadata exceed the artifact-size budget")
    return {
        "baseline_output": _write_artifact(
            task_id,
            f"baseline-output-{hashlib.sha256(baseline).hexdigest()[:16]}.txt",
            baseline,
            artifact_type="hie_baseline_output",
            metadata=baseline_meta,
            max_bytes=max_bytes,
        ),
        "candidate_output": _write_artifact(
            task_id,
            f"candidate-output-{hashlib.sha256(candidate).hexdigest()[:16]}.txt",
            candidate,
            artifact_type="hie_candidate_output",
            metadata=candidate_meta,
            max_bytes=max_bytes,
        ),
    }


def persist_record_evidence(
    task_id: int,
    record: dict[str, Any],
    *,
    max_bytes: int,
) -> dict[str, Any]:
    content = (
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    return _write_artifact(
        task_id,
        f"experiment-record-{record['record_sha256'][:16]}.json",
        content,
        artifact_type="hie_experiment_record",
        metadata={"role": "experiment_record", "record_sha256": record["record_sha256"]},
        max_bytes=max_bytes,
    )
