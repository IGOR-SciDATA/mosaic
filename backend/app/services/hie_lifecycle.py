"""Version-bound human approval, promotion, and rollback for HIE profile candidates.

Promotion is explicit, only applies declarative profile instructions, and refuses
stale approvals. Previous profile snapshots are persisted for audited rollback.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection
from app.models.task_event_repository import create_task_event
from app.services.agent_library import get_project_agent, update_project_agent
from app.services.hie_experiments import get_experiment, HieExperimentError

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

def _active_profile(experiment: dict[str, Any]) -> dict[str, Any]:
    profile = get_project_agent(experiment["project_id"], experiment["profile_slug"])
    if profile is None:
        raise HieLifecycleError("Active profile no longer exists")
    return profile

def _assert_candidate_current(experiment: dict[str, Any], candidate_sha256: str) -> dict[str, Any]:
    if experiment["status"] != "completed":
        raise HieLifecycleError("Only completed experiments can be approved")
    results = experiment.get("results") or {}
    if results.get("assessment") != "candidate_better":
        raise HieLifecycleError("Only candidates assessed as candidate_better can be promoted")
    candidate = experiment["candidate"]
    if candidate.get("sha256") != candidate_sha256:
        raise HieLifecycleError("Candidate hash changed; review the current candidate again")
    profile = _active_profile(experiment)
    target = candidate.get("target", {})
    if (
        target.get("profile_version") != profile.get("version")
        or target.get("profile_sha256") != profile.get("sha256")
    ):
        raise HieLifecycleError("Active profile changed since the experiment; approval is stale")
    return profile

def approve_candidate(experiment_id: int, *, candidate_sha256: str, active_version: int, active_sha256: str) -> dict[str, Any]:
    _init_tables()
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HieLifecycleError("Experiment not found")
    if not all(isinstance(v, str) and v for v in (candidate_sha256, active_sha256)):
        raise HieLifecycleError("Candidate and active profile hashes are required")
    profile = _assert_candidate_current(experiment, candidate_sha256)
    if profile["version"] != active_version or profile["sha256"] != active_sha256:
        raise HieLifecycleError("Approval must match the exact active profile version and hash")
    with get_connection() as connection:
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
        connection.commit()
    _event(experiment, "hie.candidate_approved", "Candidate explicitly approved for the reviewed profile version.", {
        "candidate_sha256": candidate_sha256, "active_version": active_version, "active_sha256": active_sha256,
    })
    return {"approved": True, "experiment_id": experiment_id, "candidate_sha256": candidate_sha256,
            "active_version": active_version, "active_sha256": active_sha256}

def promote_candidate(experiment_id: int, *, candidate_sha256: str, active_version: int, active_sha256: str) -> dict[str, Any]:
    _init_tables()
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HieLifecycleError("Experiment not found")
    profile = _assert_candidate_current(experiment, candidate_sha256)
    if profile["version"] != active_version or profile["sha256"] != active_sha256:
        raise HieLifecycleError("Active profile changed; approval is stale")
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        approval = connection.execute("SELECT * FROM hie_candidate_approvals WHERE experiment_id = ?", (experiment_id,)).fetchone()
        if not approval:
            raise HieLifecycleError("Explicit approval is required before promotion")
        if (approval["candidate_sha256"] != candidate_sha256 or approval["active_version"] != active_version
            or approval["active_sha256"] != active_sha256 or approval["project_id"] != experiment["project_id"]
            or approval["profile_slug"] != experiment["profile_slug"]):
            raise HieLifecycleError("Approval does not match this candidate and active profile")
        connection.commit()
    candidate = experiment["candidate"]
    if candidate.get("target", {}).get("kind") != "profile_instructions":
        raise HieLifecycleError("Only profile-instruction candidates are currently promotable")
    previous = json.loads(json.dumps(profile))
    updated = update_project_agent(experiment["project_id"], experiment["profile_slug"], {"instructions": candidate["content"]})
    if updated is None:
        raise HieLifecycleError("Active profile no longer exists")
    with get_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO hie_promotions
               (experiment_id, project_id, profile_slug, candidate_sha256, previous_profile,
                promoted_version, promoted_sha256, promoted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (experiment_id, experiment["project_id"], experiment["profile_slug"], candidate_sha256,
             json.dumps(previous, ensure_ascii=False), updated["version"], updated["sha256"], _now()),
        )
        connection.commit()
        promotion_id = cursor.lastrowid
    _event(experiment, "hie.candidate_promoted", "Approved declarative candidate promoted as a new profile version.", {
        "promotion_id": promotion_id, "candidate_sha256": candidate_sha256,
        "previous_version": profile["version"], "promoted_version": updated["version"],
        "promoted_sha256": updated["sha256"], "automatic_promotion": False,
    })
    return {"promoted": True, "promotion_id": promotion_id, "profile": updated,
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
        project_id, slug = promotion["project_id"], promotion["profile_slug"]
        connection.commit()
    active = get_project_agent(project_id, slug)
    if active is None:
        raise HieLifecycleError("Active profile no longer exists")
    if active["version"] != expected_active_version or active["sha256"] != expected_active_sha256:
        raise HieLifecycleError("Rollback requires the exact currently active version and hash")
    if active["version"] != promotion["promoted_version"] or active["sha256"] != promotion["promoted_sha256"]:
        raise HieLifecycleError("Profile changed after promotion; refusing to overwrite newer changes")
    previous = json.loads(promotion["previous_profile"])
    # Restore the previous declarative content as a NEW version; never rewind version numbers.
    restored = update_project_agent(project_id, slug, {
        "name": previous["name"], "description": previous["description"],
        "instructions": previous["instructions"], "skills": previous["skills"],
    })
    if restored is None:
        raise HieLifecycleError("Active profile no longer exists")
    with get_connection() as connection:
        connection.execute(
            "UPDATE hie_promotions SET rolled_back_at = ?, rollback_profile = ? WHERE id = ? AND rolled_back_at IS NULL",
            (_now(), json.dumps(restored, ensure_ascii=False), promotion_id),
        )
        connection.commit()
    experiment = get_experiment(promotion["experiment_id"])
    if experiment:
        _event(experiment, "hie.candidate_rolled_back", "Promotion rolled back by restoring the previous profile content as a new version.", {
            "promotion_id": promotion_id, "restored_version": restored["version"], "restored_sha256": restored["sha256"],
        })
    return {"rolled_back": True, "promotion_id": promotion_id, "profile": restored}

def _event(experiment: dict[str, Any], event_name: str, message: str, metadata: dict[str, Any]) -> None:
    create_task_event(
        task_id=experiment["task_id"], conversation_id=experiment["conversation_id"],
        project_id=experiment["project_id"], component="hie", event_name=event_name,
        message=message, status="completed", metadata={"experiment_id": experiment["id"], **metadata},
    )
