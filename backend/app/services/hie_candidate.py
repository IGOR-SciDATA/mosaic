"""Strict, data-only candidate format for the Mosaic Harness Improvement Engine (HIE-1).

Candidates are proposals, not active configuration. This module does not persist,
apply, execute, or promote a candidate.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from typing import Any

from app.services.agent_library import validate_agent_snapshot

SCHEMA_VERSION = 1
MAX_CONTENT_CHARS = 12_000
MAX_CANDIDATE_BYTES = 48 * 1024
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_TOP_LEVEL_KEYS = {"schema_version", "target", "content", "sha256"}
_PROFILE_TARGET_KEYS = {
    "kind", "profile_slug", "profile_version", "profile_sha256"
}
_SKILL_TARGET_KEYS = _PROFILE_TARGET_KEYS | {"skill_slug", "skill_sha256"}


class CandidateValidationError(ValueError):
    """Raised when a declarative HIE candidate violates its contract."""


def canonical_json(value: Any) -> str:
    """Serialize JSON data deterministically for hashing and comparison."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CandidateValidationError("Candidate contains non-JSON data") from exc


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _slugify_skill(name: str) -> str:
    # Keep this normalization aligned with agent_library._skill_slug without
    # depending on its private helper.
    import unicodedata

    normalized = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", normalized)).strip("-")


def _check_slug(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _SLUG_PATTERN.fullmatch(value):
        raise CandidateValidationError(f"Invalid {field}")


def _check_sha256(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise CandidateValidationError(f"Invalid {field}")


def _candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in candidate.items() if key != "sha256"}


def build_candidate(
    baseline_snapshot: dict[str, Any],
    content: str,
    *,
    target_kind: str = "profile_instructions",
    skill_slug: str | None = None,
) -> dict[str, Any]:
    """Build a hash-sealed proposal bound to an immutable agent snapshot."""
    if not validate_agent_snapshot(baseline_snapshot):
        raise CandidateValidationError("Baseline agent snapshot failed integrity validation")
    if not isinstance(content, str):
        raise CandidateValidationError("Candidate content must be a string")
    if len(content) > MAX_CONTENT_CHARS:
        raise CandidateValidationError("Candidate content exceeds character limit")

    profile_slug = baseline_snapshot.get("slug")
    _check_slug(profile_slug, "profile slug")
    version = baseline_snapshot.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise CandidateValidationError("Invalid baseline profile version")
    _check_sha256(baseline_snapshot.get("sha256"), "baseline profile hash")

    target: dict[str, Any] = {
        "kind": target_kind,
        "profile_slug": profile_slug,
        "profile_version": version,
        "profile_sha256": baseline_snapshot["sha256"],
    }
    if target_kind == "profile_instructions":
        if skill_slug is not None:
            raise CandidateValidationError("skill_slug is only valid for a Skill candidate")
    elif target_kind == "skill_content":
        if not isinstance(skill_slug, str):
            raise CandidateValidationError("skill_slug is required for a Skill candidate")
        _check_slug(skill_slug, "Skill slug")
        matches = [
            skill for skill in baseline_snapshot["skills"]
            if skill.get("enabled") is True and _slugify_skill(skill.get("name", "")) == skill_slug
        ]
        if len(matches) != 1:
            raise CandidateValidationError("Skill must identify exactly one enabled Skill in the baseline")
        target["skill_slug"] = skill_slug
        target["skill_sha256"] = matches[0]["sha256"]
    else:
        raise CandidateValidationError("Unsupported candidate target kind")

    candidate = {
        "schema_version": SCHEMA_VERSION,
        "target": target,
        "content": content,
    }
    candidate["sha256"] = _sha256_json(candidate)
    validate_candidate(candidate, baseline_snapshot=baseline_snapshot)
    if len(canonical_json(candidate).encode("utf-8")) > MAX_CANDIDATE_BYTES:
        raise CandidateValidationError("Candidate exceeds byte limit")
    return candidate


def validate_candidate(
    candidate: Any,
    *,
    baseline_snapshot: dict[str, Any] | None = None,
) -> bool:
    """Validate schema, target allowlist, content bounds, hash, and optional baseline binding.

    Raises CandidateValidationError with a safe reason on invalid input.
    Returns True for a valid candidate.
    """
    if not isinstance(candidate, dict) or set(candidate) != _TOP_LEVEL_KEYS:
        raise CandidateValidationError("Candidate has missing or unknown top-level keys")
    schema_version = candidate.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != SCHEMA_VERSION:
        raise CandidateValidationError("Unsupported candidate schema version")
    if not isinstance(candidate.get("content"), str):
        raise CandidateValidationError("Candidate content must be a string")
    if len(candidate["content"]) > MAX_CONTENT_CHARS:
        raise CandidateValidationError("Candidate content exceeds character limit")

    target = candidate.get("target")
    if not isinstance(target, dict):
        raise CandidateValidationError("Candidate target must be an object")
    kind = target.get("kind")
    expected_keys = (
        _PROFILE_TARGET_KEYS if kind == "profile_instructions"
        else _SKILL_TARGET_KEYS if kind == "skill_content"
        else None
    )
    if expected_keys is None:
        raise CandidateValidationError("Unsupported candidate target kind")
    if set(target) != expected_keys:
        raise CandidateValidationError("Candidate target has missing or unknown keys")

    _check_slug(target.get("profile_slug"), "profile slug")
    version = target.get("profile_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise CandidateValidationError("Invalid baseline profile version")
    _check_sha256(target.get("profile_sha256"), "baseline profile hash")
    if kind == "skill_content":
        _check_slug(target.get("skill_slug"), "Skill slug")
        _check_sha256(target.get("skill_sha256"), "baseline Skill hash")

    _check_sha256(candidate.get("sha256"), "candidate hash")
    if _sha256_json(_candidate_payload(candidate)) != candidate["sha256"]:
        raise CandidateValidationError("Candidate hash mismatch")
    if len(canonical_json(candidate).encode("utf-8")) > MAX_CANDIDATE_BYTES:
        raise CandidateValidationError("Candidate exceeds byte limit")

    if baseline_snapshot is not None:
        if not validate_agent_snapshot(baseline_snapshot):
            raise CandidateValidationError("Baseline agent snapshot failed integrity validation")
        if (
            target["profile_slug"] != baseline_snapshot["slug"]
            or target["profile_version"] != baseline_snapshot["version"]
            or target["profile_sha256"] != baseline_snapshot["sha256"]
        ):
            raise CandidateValidationError("Candidate is bound to a different profile snapshot")
        if kind == "skill_content":
            matches = [
                skill for skill in baseline_snapshot["skills"]
                if skill.get("enabled") is True
                and _slugify_skill(skill.get("name", "")) == target["skill_slug"]
            ]
            if len(matches) != 1 or matches[0]["sha256"] != target["skill_sha256"]:
                raise CandidateValidationError("Candidate is bound to a different or inactive Skill snapshot")
    return True


def candidate_diff(
    baseline_snapshot: dict[str, Any],
    candidate: dict[str, Any],
) -> str:
    """Return a bounded, reviewable unified diff without accepting filesystem paths."""
    validate_candidate(candidate, baseline_snapshot=baseline_snapshot)
    target = candidate["target"]
    if target["kind"] == "profile_instructions":
        before = baseline_snapshot["instructions"]
        label = "profile-instructions"
    else:
        skill = next(
            skill for skill in baseline_snapshot["skills"]
            if skill.get("enabled") is True
            and _slugify_skill(skill.get("name", "")) == target["skill_slug"]
        )
        before = skill["content"]
        label = f"skill-{target['skill_slug']}"
    if not isinstance(before, str):
        raise CandidateValidationError("Baseline content must be a string")
    def diff_lines(value: str) -> list[str]:
        lines = value.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\\n", "\\r")):
            lines[-1] += "\\n"
        return lines

    diff = "".join(difflib.unified_diff(
        diff_lines(before),
        diff_lines(candidate["content"]),
        fromfile=f"baseline/{label}",
        tofile=f"candidate/{label}",
        n=3,
    ))
    if len(diff.encode("utf-8")) > MAX_CANDIDATE_BYTES:
        raise CandidateValidationError("Candidate diff exceeds byte limit")
    return diff
