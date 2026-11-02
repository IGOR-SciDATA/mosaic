"""Project-scoped, evidence-bound HIE experiences stored as ordinary files.

The library deliberately reuses the existing HIE artifact directory and experiment/
promotion records; it does not add a SQLite table or mix experiences into user Memory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR
from app.db.database import get_connection
from app.services.hie_evidence import _check_evidence_directories
from app.services.hie_experiments import get_experiment


MAX_CUE_CHARS = 1200
MAX_LESSON_CHARS = 2400
MAX_LIMITATIONS_CHARS = 1200
MAX_EXPERIENCE_BYTES = 16_000
MAX_RETRIEVAL_RESULTS = 3
STOP_WORDS = {
    "a", "as", "ao", "aos", "com", "da", "das", "de", "do", "dos", "e", "em",
    "for", "from", "how", "is", "na", "nas", "no", "nos", "o", "os", "para",
    "por", "que", "the", "to", "um", "uma", "what", "when", "where", "which",
    "with", "you", "your",
}


class HieExperienceError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _root(project_id: int) -> Path:
    if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id < 1:
        raise HieExperienceError("A valid project_id is required")
    return _check_evidence_directories(Path(DATA_DIR).absolute() / "artifacts" / "hie" / f"experiences-project-{project_id}")


def _record_path(project_id: int, experience_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", experience_id or ""):
        raise HieExperienceError("Invalid experience id")
    root = _root(project_id)
    path = root / f"experience-{experience_id}.json"
    if path.parent.resolve(strict=True) != root or path.name != f"experience-{experience_id}.json":
        raise HieExperienceError("Experience path escaped its project scope")
    return path


def _read(path: Path) -> dict[str, Any] | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or path.stat().st_size > MAX_EXPERIENCE_BYTES:
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or record.get("record_sha256") != _digest(record):
        return None
    return record


def _write(project_id: int, record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["updated_at"] = _now()
    record["record_sha256"] = _digest(record)
    payload = _canonical(record) + b"\n"
    if len(payload) > MAX_EXPERIENCE_BYTES:
        raise HieExperienceError("Experience record exceeds its byte limit")
    path = _record_path(project_id, record["id"])
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        mode = None
    if mode is not None and (stat.S_ISLNK(mode) or not stat.S_ISREG(mode)):
        raise HieExperienceError("Experience destination must be a regular file")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".hie-experience-", suffix=".tmp", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.parent.resolve(strict=True) != _root(project_id):
            raise HieExperienceError("Experience directory changed during persistence")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    persisted = _read(path)
    if persisted is None:
        raise HieExperienceError("Experience persistence could not be verified")
    return persisted


def _evidence_refs(results: dict[str, Any], task_id: int) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for case in results.get("evidence", []):
        if not isinstance(case, dict):
            continue
        for role, evidence in (case.get("artifact_evidence") or {}).items():
            if not isinstance(evidence, dict) or not evidence.get("sha256"):
                continue
            artifact_id = evidence.get("artifact_id")
            if isinstance(artifact_id, bool) or not isinstance(artifact_id, int):
                continue
            with get_connection() as connection:
                artifact = connection.execute(
                    "SELECT task_id, type, metadata FROM artifacts WHERE id = ?", (artifact_id,)
                ).fetchone()
            if artifact is None or artifact["task_id"] != task_id or not str(artifact["type"]).startswith("hie_"):
                continue
            try:
                metadata = json.loads(artifact["metadata"] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if metadata.get("sha256") != evidence["sha256"]:
                continue
            refs.append({
                "fixture_id": case.get("fixture_id"),
                "role": role,
                "artifact_id": artifact_id,
                "sha256": evidence["sha256"],
                "type": artifact["type"],
            })
    unique = {}
    for ref in refs:
        unique[(ref["artifact_id"], ref["sha256"], ref.get("role"))] = ref
    return list(unique.values())[:32]


def create_experience(
    *, project_id: int, experiment_id: int, cue: str, lesson: str,
    limitations: str = "Evidence is limited to the recorded deterministic fixtures and provider/model snapshot.",
) -> dict[str, Any]:
    if not isinstance(cue, str) or not cue.strip() or len(cue) > MAX_CUE_CHARS:
        raise HieExperienceError(f"cue must contain 1 to {MAX_CUE_CHARS} characters")
    if not isinstance(lesson, str) or not lesson.strip() or len(lesson) > MAX_LESSON_CHARS:
        raise HieExperienceError(f"lesson must contain 1 to {MAX_LESSON_CHARS} characters")
    if not isinstance(limitations, str) or len(limitations) > MAX_LIMITATIONS_CHARS:
        raise HieExperienceError(f"limitations must not exceed {MAX_LIMITATIONS_CHARS} characters")
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HieExperienceError("Experiment not found")
    if experiment["project_id"] != project_id:
        raise HieExperienceError("Experiment does not belong to this project")
    results = experiment.get("results") or {}
    if experiment["status"] != "completed" or results.get("assessment") != "candidate_better":
        raise HieExperienceError("Only completed, evidence-supported improvements can become experiences")
    normalize = lambda value: " ".join(value.casefold().split())
    fixture_prompts = [
        normalize(fixture.get("prompt", ""))
        for fixture in experiment.get("fixtures", [])
        if isinstance(fixture, dict) and isinstance(fixture.get("prompt"), str)
    ]
    if not any(normalize(cue.strip()) in prompt for prompt in fixture_prompts):
        raise HieExperienceError("Experience cue must be quoted from a recorded fixture prompt")
    candidate_content = str((experiment.get("candidate") or {}).get("content", ""))
    if normalize(lesson.strip()) not in normalize(candidate_content):
        raise HieExperienceError("Experience lesson must be quoted from the promoted candidate instructions")
    with get_connection() as connection:
        promotion = connection.execute(
            """SELECT id FROM hie_promotions
               WHERE experiment_id = ? AND project_id = ? AND rolled_back_at IS NULL
               ORDER BY id DESC LIMIT 1""",
            (experiment_id, project_id),
        ).fetchone()
    if promotion is None:
        raise HieExperienceError("Experience requires an active, explicitly promoted candidate")
    evidence_refs = _evidence_refs(results, experiment['task_id'])
    if not evidence_refs:
        raise HieExperienceError("Experience requires persisted, hash-addressed probe evidence")
    delta = results.get("delta_pass_rate")
    if isinstance(delta, bool) or not isinstance(delta, (int, float)) or delta <= 0:
        raise HieExperienceError("Experience has no positive deterministic pass-rate improvement")
    experience_id = uuid.uuid4().hex
    fixture_count = len(experiment.get("fixtures", []))
    confidence = round(
        0.5 + min(1.0, float(delta)) * min(1.0, fixture_count / 4.0) * 0.35,
        2,
    )
    record = {
        "schema_version": 1,
        "id": experience_id,
        "project_id": project_id,
        "profile_slug": experiment["profile_slug"],
        "scope": {"kind": "project", "project_id": project_id, "profile_slug": experiment["profile_slug"]},
        "cue": cue.strip(),
        "lesson": lesson.strip(),
        "limitations": limitations.strip(),
        "confidence": confidence,
        "confidence_basis": "heuristic from deterministic pass-rate delta and fixture count; not a statistical probability",
        "lifecycle": "active",
        "source": {
            "experiment_id": experiment_id,
            "promotion_id": promotion["id"],
            "candidate_sha256": experiment["candidate"]["sha256"],
            "provider": experiment["provider"],
            "model_name": experiment["model_name"],
            "baseline_pass_rate": results.get("baseline_pass_rate"),
            "candidate_pass_rate": results.get("candidate_pass_rate"),
            "delta_pass_rate": delta,
            "evidence_refs": evidence_refs,
        },
        "created_at": _now(),
    }
    return _write(project_id, record)


def list_experiences(project_id: int, *, query: str | None = None, profile_slug: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    if not 1 <= limit <= 100:
        raise HieExperienceError("limit must be between 1 and 100")
    root = _root(project_id)
    tokens = {
        token.casefold() for token in re.findall(r"[\w.-]+", query or "", flags=re.UNICODE)
        if len(token) >= 3 and token.casefold() not in STOP_WORDS
    }
    found: list[tuple[int, str, dict[str, Any]]] = []
    for path in sorted(root.glob("experience-*.json")):
        record = _read(path)
        if not record or record.get("project_id") != project_id or record.get("lifecycle") != "active":
            continue
        source = record.get("source") or {}
        promotion_id = source.get("promotion_id")
        with get_connection() as connection:
            promotion = connection.execute(
                """SELECT id FROM hie_promotions
                   WHERE id = ? AND project_id = ? AND experiment_id = ? AND rolled_back_at IS NULL""",
                (promotion_id, project_id, source.get("experiment_id")),
            ).fetchone()
        if promotion is None:
            continue
        if profile_slug and record.get("profile_slug") != profile_slug:
            continue
        haystack = f"{record.get('cue', '')} {record.get('lesson', '')}".casefold()
        score = sum(1 for token in tokens if token in haystack)
        if tokens and score == 0:
            continue
        found.append((score, str(record.get("created_at", "")), record))
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [record for _, _, record in found[:limit]]


def get_experience(project_id: int, experience_id: str) -> dict[str, Any] | None:
    return _read(_record_path(project_id, experience_id))


def deactivate_experience(project_id: int, experience_id: str) -> dict[str, Any]:
    record = get_experience(project_id, experience_id)
    if record is None:
        raise HieExperienceError("Experience not found or failed integrity validation")
    if record.get("project_id") != project_id:
        raise HieExperienceError("Experience does not belong to this project")
    if record.get("lifecycle") != "active":
        raise HieExperienceError("Only active experiences can be deactivated")
    record["lifecycle"] = "inactive"
    return _write(project_id, record)


def delete_experience(project_id: int, experience_id: str) -> dict[str, Any]:
    record = get_experience(project_id, experience_id)
    if record is None:
        raise HieExperienceError("Experience not found or failed integrity validation")
    if record.get("project_id") != project_id:
        raise HieExperienceError("Experience does not belong to this project")
    path = _record_path(project_id, experience_id)
    path.unlink()
    return {"id": experience_id, "project_id": project_id, "deleted": True, "source_artifacts_preserved": True}


def retrieve_experiences(project_id: int, query: str, *, profile_slug: str | None = None, limit: int = MAX_RETRIEVAL_RESULTS) -> list[dict[str, Any]]:
    if not isinstance(query, str) or not query.strip():
        return []
    return list_experiences(project_id, query=query, profile_slug=profile_slug, limit=limit)
