"""Version-bound HIE approval, promotion, and rollback in the existing SQLite store."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection
from app.models.task_event_repository import create_task_event
from app.services.agent_library import _seal_profile
from app.services.hie_experiments import get_experiment


class HieLifecycleError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_tables() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS hie_candidate_approvals (
                experiment_id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                profile_slug TEXT NOT NULL,
                candidate_sha256 TEXT NOT NULL,
                active_version INTEGER NOT NULL,
                active_sha256 TEXT NOT NULL,
                approved_at TEXT NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES hie_experiments(id) ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS hie_promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                profile_slug TEXT NOT NULL,
                candidate_sha256 TEXT NOT NULL,
                previous_profile TEXT NOT NULL,
                promoted_version INTEGER NOT NULL,
                promoted_sha256 TEXT NOT NULL,
                promoted_at TEXT NOT NULL,
                rolled_back_at TEXT NULL,
                rollback_profile TEXT NULL,
                FOREIGN KEY (experiment_id) REFERENCES hie_experiments(id) ON DELETE CASCADE
            )
        """)
        connection.commit()


def _read_active_profile(connection, project_id: int, slug: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    row = connection.execute("SELECT state FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise HieLifecycleError("Project no longer exists")
    state = json.loads(row["state"] or "{}")
    library = state.get("agent_library", {})
    if not isinstance(library, dict) or not isinstance(library.get(slug), dict):
        raise HieLifecycleError("Active profile no longer exists")
    return state, dict(library), row["state"]


def _check_experiment(experiment: dict[str, Any] | None, candidate_sha256: str) -> dict[str, Any]:
    if experiment is None:
        raise HieLifecycleError("Experiment not found")
    if experiment["status"] != "completed":
        raise HieLifecycleError("Only completed experiments can be approved")
    results = experiment.get("results") or {}
    if results.get("assessment") != "candidate_better":
        raise HieLifecycleError("Only candidates assessed as candidate_better can be promoted")
    candidate = experiment.get("candidate") or {}
    if candidate.get("sha256") != candidate_sha256:
        raise HieLifecycleError("Candidate hash changed; review the current candidate again")
    if candidate.get("target", {}).get("kind") != "profile_instructions":
        raise HieLifecycleError("Only profile-instruction candidates are currently promotable")
    return candidate


def _check_baseline(candidate: dict[str, Any], profile: dict[str, Any]) -> None:
    target = candidate.get("target", {})
    if target.get("profile_version") != profile.get("version") or target.get("profile_sha256") != profile.get("sha256"):
        raise HieLifecycleError("Active profile changed since the experiment; approval is stale")


def _write_profile(connection, project_id: int, state: dict[str, Any], library: dict[str, Any], slug: str, profile: dict[str, Any], old_state_json: str) -> dict[str, Any]:
    library[slug] = profile
    state["agent_library"] = library
    cursor = connection.execute(
        "UPDATE projects SET state = ?, updated_at = ? WHERE id = ? AND state = ?",
        (json.dumps(state, ensure_ascii=False), _now(), project_id, old_state_json),
    )
    if cursor.rowcount != 1:
        raise HieLifecycleError("Project state changed concurrently")
    return profile


def _event(connection, experiment: dict[str, Any], event_name: str, message: str, metadata: dict[str, Any]) -> None:
    create_task_event(
        task_id=experiment["task_id"],
        conversation_id=experiment["conversation_id"],
        project_id=experiment["project_id"],
        component="hie",
        event_name=event_name,
        message=message,
        status="completed",
        metadata={"experiment_id": experiment["id"], **metadata},
        connection=connection,
    )


def approve_candidate(experiment_id: int, *, candidate_sha256: str, active_version: int, active_sha256: str) -> dict[str, Any]:
    _init_tables()
    experiment = get_experiment(experiment_id)
    candidate = _check_experiment(experiment, candidate_sha256)
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        state, library, state_json = _read_active_profile(connection, experiment["project_id"], experiment["profile_slug"])
        profile = library[experiment["profile_slug"]]
        _check_baseline(candidate, profile)
        if profile.get("version") != active_version or profile.get("sha256") != active_sha256:
            raise HieLifecycleError("Approval must match the exact active profile version and hash")
        connection.execute(
            """INSERT INTO hie_candidate_approvals
               (experiment_id, project_id, profile_slug, candidate_sha256, active_version, active_sha256, approved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(experiment_id) DO UPDATE SET
                 project_id=excluded.project_id, profile_slug=excluded.profile_slug,
                 candidate_sha256=excluded.candidate_sha256, active_version=excluded.active_version,
                 active_sha256=excluded.active_sha256, approved_at=excluded.approved_at""",
            (experiment_id, experiment["project_id"], experiment["profile_slug"], candidate_sha256,
             active_version, active_sha256, _now()),
        )
        _event(connection, experiment, "hie.candidate_approved", "Candidate explicitly approved for the reviewed profile version.", {
            "candidate_sha256": candidate_sha256, "active_version": active_version, "active_sha256": active_sha256,
        })
        connection.commit()
    return {"approved": True, "experiment_id": experiment_id, "candidate_sha256": candidate_sha256,
            "active_version": active_version, "active_sha256": active_sha256}


def promote_candidate(experiment_id: int, *, candidate_sha256: str, active_version: int, active_sha256: str) -> dict[str, Any]:
    _init_tables()
    experiment = get_experiment(experiment_id)
    candidate = _check_experiment(experiment, candidate_sha256)
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        state, library, state_json = _read_active_profile(connection, experiment["project_id"], experiment["profile_slug"])
        profile = library[experiment["profile_slug"]]
        _check_baseline(candidate, profile)
        if profile.get("version") != active_version or profile.get("sha256") != active_sha256:
            raise HieLifecycleError("Active profile changed; approval is stale")
        approval = connection.execute("SELECT * FROM hie_candidate_approvals WHERE experiment_id = ?", (experiment_id,)).fetchone()
        if not approval:
            raise HieLifecycleError("Explicit approval is required before promotion")
        if (approval["candidate_sha256"] != candidate_sha256 or approval["active_version"] != active_version
            or approval["active_sha256"] != active_sha256 or approval["project_id"] != experiment["project_id"]
            or approval["profile_slug"] != experiment["profile_slug"]):
            raise HieLifecycleError("Approval does not match this candidate and active profile")
        previous = json.loads(json.dumps(profile))
        next_profile = dict(profile)
        next_profile["instructions"] = candidate["content"]
        next_profile["version"] = int(profile.get("version", 1)) + 1
        next_profile = _seal_profile(next_profile)
        _write_profile(connection, experiment["project_id"], state, library, experiment["profile_slug"], next_profile, state_json)
        cursor = connection.execute(
            """INSERT INTO hie_promotions
               (experiment_id, project_id, profile_slug, candidate_sha256, previous_profile,
                promoted_version, promoted_sha256, promoted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (experiment_id, experiment["project_id"], experiment["profile_slug"], candidate_sha256,
             json.dumps(previous, ensure_ascii=False), next_profile["version"], next_profile["sha256"], _now()),
        )
        promotion_id = cursor.lastrowid
        _event(connection, experiment, "hie.candidate_promoted", "Approved declarative candidate promoted as a new profile version.", {
            "promotion_id": promotion_id, "candidate_sha256": candidate_sha256,
            "previous_version": profile["version"], "promoted_version": next_profile["version"],
            "promoted_sha256": next_profile["sha256"], "automatic_promotion": False,
        })
        connection.commit()
    return {"promoted": True, "promotion_id": promotion_id, "profile": next_profile,
            "previous_version": profile["version"]}


def rollback_promotion(promotion_id: int, *, expected_active_version: int, expected_active_sha256: str) -> dict[str, Any]:
    _init_tables()
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        promotion = connection.execute("SELECT * FROM hie_promotions WHERE id = ?", (promotion_id,)).fetchone()
        if not promotion:
            raise HieLifecycleError("Promotion not found")
        if promotion["rolled_back_at"]:
            raise HieLifecycleError("Promotion has already been rolled back")
        state, library, state_json = _read_active_profile(connection, promotion["project_id"], promotion["profile_slug"])
        active = library[promotion["profile_slug"]]
        if active.get("version") != expected_active_version or active.get("sha256") != expected_active_sha256:
            raise HieLifecycleError("Rollback requires the exact currently active version and hash")
        if active.get("version") != promotion["promoted_version"] or active.get("sha256") != promotion["promoted_sha256"]:
            raise HieLifecycleError("Profile changed after promotion; refusing to overwrite newer changes")
        previous = json.loads(promotion["previous_profile"])
        restored = dict(active)
        for key in ("name", "description", "instructions", "skills"):
            restored[key] = previous[key]
        restored["version"] = int(active.get("version", 1)) + 1
        restored = _seal_profile(restored)
        _write_profile(connection, promotion["project_id"], state, library, promotion["profile_slug"], restored, state_json)
        cursor = connection.execute(
            "UPDATE hie_promotions SET rolled_back_at = ?, rollback_profile = ? WHERE id = ? AND rolled_back_at IS NULL",
            (_now(), json.dumps(restored, ensure_ascii=False), promotion_id),
        )
        if cursor.rowcount != 1:
            raise HieLifecycleError("Promotion was already rolled back")
        experiment = get_experiment(promotion["experiment_id"])
        if experiment:
            _event(connection, experiment, "hie.candidate_rolled_back", "Promotion rolled back by restoring the previous profile content as a new version.", {
                "promotion_id": promotion_id, "restored_version": restored["version"], "restored_sha256": restored["sha256"],
            })
        connection.commit()
    return {"rolled_back": True, "promotion_id": promotion_id, "profile": restored}
