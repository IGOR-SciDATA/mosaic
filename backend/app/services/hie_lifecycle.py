"""Version-bound human approval, promotion, and rollback for HIE profile candidates.

Promotions update the existing Project.state profile library and promotion ledger
under one SQLite write transaction. Candidate content remains declarative data.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_connection
from app.models.task_event_repository import create_task_event
from app.models.task_repository import get_task
from app.services.agent_library import _seal_profile, _normalize_skills
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


def _load_profile_in_transaction(connection, project_id: int, slug: str) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    row = connection.execute(
        "SELECT id, state FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise HieLifecycleError("Project not found")
    try:
        state = json.loads(row["state"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise HieLifecycleError("Project state is invalid") from exc
    if not isinstance(state, dict):
        raise HieLifecycleError("Project state is invalid")
    library = state.get("agent_library", {})
    if not isinstance(library, dict):
        raise HieLifecycleError("Project agent library state is invalid")
    profile = library.get(slug)
    if profile is None:
        raise HieLifecycleError("Active profile no longer exists")
    return row, state, copy.deepcopy(profile)


def _save_profile_in_transaction(
    connection, project_id: int, slug: str, state: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    library = dict(state.get("agent_library", {}))
    library[slug] = profile
    state["agent_library"] = library
    connection.execute(
        "UPDATE projects SET state = ?, updated_at = ? WHERE id = ?",
        (json.dumps(state, ensure_ascii=False), _now(), project_id),
    )
    return copy.deepcopy(profile)


def _assert_candidate_current(experiment: dict[str, Any], profile: dict[str, Any], candidate_sha256: str) -> None:
    if experiment["status"] != "completed":
        raise HieLifecycleError("Only completed experiments can be approved")
    results = experiment.get("results") or {}
    if results.get("assessment") != "candidate_better":
        raise HieLifecycleError("Only candidates assessed as candidate_better can be promoted")
    candidate = experiment["candidate"]
    if candidate.get("sha256") != candidate_sha256:
        raise HieLifecycleError("Candidate hash changed; review the current candidate again")
    target = candidate.get("target", {})
    if (
        target.get("profile_version") != profile.get("version")
        or target.get("profile_sha256") != profile.get("sha256")
    ):
        raise HieLifecycleError("Active profile changed since the experiment; approval is stale")


def approve_candidate(
    experiment_id: int, *, candidate_sha256: str, active_version: int, active_sha256: str
) -> dict[str, Any]:
    _init_tables()
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HieLifecycleError("Experiment not found")
    if not all(isinstance(v, str) and v for v in (candidate_sha256, active_sha256)):
        raise HieLifecycleError("Candidate and active profile hashes are required")

    # Read/validate and record approval while holding a SQLite writer lock so the
    # profile snapshot cannot change between check and approval persistence.
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _, _, profile = _load_profile_in_transaction(
            connection, experiment["project_id"], experiment["profile_slug"]
        )
        _assert_candidate_current(experiment, profile, candidate_sha256)
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
            (
                experiment_id, experiment["project_id"], experiment["profile_slug"],
                candidate_sha256, active_version, active_sha256, _now(),
            ),
        )
        connection.commit()

    _event(experiment, "hie.candidate_approved", "Candidate explicitly approved for the reviewed profile version.", {
        "candidate_sha256": candidate_sha256, "active_version": active_version,
        "active_sha256": active_sha256,
    })
    return {
        "approved": True, "experiment_id": experiment_id, "candidate_sha256": candidate_sha256,
        "active_version": active_version, "active_sha256": active_sha256,
    }


def promote_candidate(
    experiment_id: int, *, candidate_sha256: str, active_version: int, active_sha256: str
) -> dict[str, Any]:
    _init_tables()
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise HieLifecycleError("Experiment not found")
    candidate = experiment["candidate"]
    if candidate.get("target", {}).get("kind") != "profile_instructions":
        raise HieLifecycleError("Only profile-instruction candidates are currently promotable")

    # The profile mutation and promotion ledger row share a single SQLite
    # transaction. The Project.state agent library is the canonical profile store.
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _, state, profile = _load_profile_in_transaction(
            connection, experiment["project_id"], experiment["profile_slug"]
        )
        _assert_candidate_current(experiment, profile, candidate_sha256)
        if profile.get("version") != active_version or profile.get("sha256") != active_sha256:
            raise HieLifecycleError("Active profile changed; approval is stale")

        approval = connection.execute(
            "SELECT * FROM hie_candidate_approvals WHERE experiment_id = ?", (experiment_id,)
        ).fetchone()
        if approval is None:
            raise HieLifecycleError("Explicit approval is required before promotion")
        if (
            approval["candidate_sha256"] != candidate_sha256
            or approval["active_version"] != active_version
            or approval["active_sha256"] != active_sha256
            or approval["project_id"] != experiment["project_id"]
            or approval["profile_slug"] != experiment["profile_slug"]
        ):
            raise HieLifecycleError("Approval does not match this candidate and active profile")

        previous = copy.deepcopy(profile)
        updated_profile = copy.deepcopy(profile)
        updated_profile["instructions"] = candidate["content"]
        if updated_profile["instructions"] != profile["instructions"]:
            updated_profile["version"] = int(profile.get("version", 1)) + 1
        updated_profile = _seal_profile(updated_profile)
        updated = _save_profile_in_transaction(
            connection, experiment["project_id"], experiment["profile_slug"], state, updated_profile
        )
        cursor = connection.execute(
            """INSERT INTO hie_promotions
               (experiment_id, project_id, profile_slug, candidate_sha256, previous_profile,
                promoted_version, promoted_sha256, promoted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment_id, experiment["project_id"], experiment["profile_slug"], candidate_sha256,
                json.dumps(previous, ensure_ascii=False), updated["version"], updated["sha256"], _now(),
            ),
        )
        promotion_id = cursor.lastrowid
        connection.commit()

    _event(experiment, "hie.candidate_promoted", "Approved declarative candidate promoted as a new profile version.", {
        "promotion_id": promotion_id, "candidate_sha256": candidate_sha256,
        "previous_version": profile["version"], "promoted_version": updated["version"],
        "promoted_sha256": updated["sha256"], "automatic_promotion": False,
    })
    return {
        "promoted": True, "promotion_id": promotion_id, "profile": updated,
        "previous_version": profile["version"],
    }


def rollback_promotion(
    promotion_id: int, *, expected_active_version: int, expected_active_sha256: str
) -> dict[str, Any]:
    _init_tables()
    experiment = None
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        promotion = connection.execute(
            "SELECT * FROM hie_promotions WHERE id = ?", (promotion_id,)
        ).fetchone()
        if promotion is None:
            raise HieLifecycleError("Promotion not found")
        if promotion["rolled_back_at"]:
            raise HieLifecycleError("Promotion has already been rolled back")

        project_id, slug = promotion["project_id"], promotion["profile_slug"]
        _, state, active = _load_profile_in_transaction(connection, project_id, slug)
        if active.get("version") != expected_active_version or active.get("sha256") != expected_active_sha256:
            raise HieLifecycleError("Rollback requires the exact currently active version and hash")
        if (
            active.get("version") != promotion["promoted_version"]
            or active.get("sha256") != promotion["promoted_sha256"]
        ):
            raise HieLifecycleError("Profile changed after promotion; refusing to overwrite newer changes")

        previous = json.loads(promotion["previous_profile"])
        restored_profile = copy.deepcopy(active)
        for key in ("name", "description", "instructions", "skills"):
            restored_profile[key] = previous[key]
        restored_profile["skills"] = _normalize_skills(restored_profile["skills"], active.get("skills", []))
        if any(restored_profile[key] != active.get(key) for key in ("name", "description", "instructions", "skills")):
            restored_profile["version"] = int(active.get("version", 1)) + 1
        restored_profile = _seal_profile(restored_profile)
        restored = _save_profile_in_transaction(
            connection, project_id, slug, state, restored_profile
        )
        cursor = connection.execute(
            """UPDATE hie_promotions SET rolled_back_at = ?, rollback_profile = ?
               WHERE id = ? AND rolled_back_at IS NULL AND promoted_version = ? AND promoted_sha256 = ?""",
            (
                _now(), json.dumps(restored, ensure_ascii=False), promotion_id,
                expected_active_version, expected_active_sha256,
            ),
        )
        if cursor.rowcount != 1:
            raise HieLifecycleError("Promotion state changed concurrently; refresh and retry")
        connection.commit()
        experiment_id = promotion["experiment_id"]

    experiment = get_experiment(experiment_id)
    if experiment:
        _event(experiment, "hie.candidate_rolled_back", "Promotion rolled back by restoring the previous profile content as a new version.", {
            "promotion_id": promotion_id, "restored_version": restored["version"],
            "restored_sha256": restored["sha256"],
        })
    return {"rolled_back": True, "promotion_id": promotion_id, "profile": restored}


def _event(experiment: dict[str, Any], event_name: str, message: str, metadata: dict[str, Any]) -> None:
    create_task_event(
        task_id=experiment["task_id"], conversation_id=experiment["conversation_id"],
        project_id=experiment["project_id"], component="hie", event_name=event_name,
        message=message, status="completed", metadata={"experiment_id": experiment["id"], **metadata},
    )
