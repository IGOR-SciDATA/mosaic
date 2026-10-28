import copy
import hashlib

import pytest

from app.services.hie_candidate import (
    MAX_CONTENT_CHARS,
    CandidateValidationError,
    build_candidate,
    candidate_diff,
    canonical_json,
    validate_candidate,
)


def _snapshot():
    profile = {
        "slug": "backend-reviewer",
        "name": "Backend Reviewer",
        "description": "Reviews backend changes",
        "instructions": "Check contracts and security.",
        "version": 3,
        "skills": [
            {"name": "API review", "content": "Check schemas.", "enabled": True, "version": 2},
            {"name": "Disabled skill", "content": "Not active.", "enabled": False, "version": 1},
        ],
    }

    def digest(value):
        return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

    for skill in profile["skills"]:
        skill["sha256"] = digest({
            key: skill[key] for key in ("name", "content", "enabled", "version")
        })
    profile["sha256"] = digest({
        key: profile[key] for key in (
            "slug", "name", "description", "instructions", "version", "skills"
        )
    })
    return profile


def test_build_and_validate_profile_instruction_candidate():
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Check contracts, security, and edge cases.")
    assert validate_candidate(candidate, baseline_snapshot=snapshot)
    assert candidate["target"]["kind"] == "profile_instructions"
    assert candidate["target"]["profile_sha256"] == snapshot["sha256"]
    assert len(candidate["sha256"]) == 64


def test_build_and_validate_selected_skill_candidate():
    snapshot = _snapshot()
    candidate = build_candidate(
        snapshot,
        "Validate request and response schemas.",
        target_kind="skill_content",
        skill_slug="api-review",
    )
    assert validate_candidate(candidate, baseline_snapshot=snapshot)
    assert candidate["target"]["skill_sha256"] == snapshot["skills"][0]["sha256"]


@pytest.mark.parametrize("mutator", [
    lambda item: item.update(extra="not allowed"),
    lambda item: item.update(schema_version=2),
    lambda item: item.update(content=17),
])
def test_rejects_unknown_keys_version_and_invalid_content(mutator):
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    tampered = copy.deepcopy(candidate)
    mutator(tampered)
    with pytest.raises(CandidateValidationError):
        validate_candidate(tampered, baseline_snapshot=snapshot)


def test_rejects_unknown_target_key_and_unsupported_target():
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    candidate["target"]["path"] = "app/config.py"
    candidate["sha256"] = hashlib.sha256(
        canonical_json({k: v for k, v in candidate.items() if k != "sha256"}).encode("utf-8")
    ).hexdigest()
    with pytest.raises(CandidateValidationError, match="unknown keys"):
        validate_candidate(candidate)

    with pytest.raises(CandidateValidationError, match="Unsupported candidate target kind"):
        build_candidate(snapshot, "content", target_kind="tool_schema")


def test_rejects_hash_mismatch_and_tampered_content():
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    candidate["content"] = "tampered without resealing"
    with pytest.raises(CandidateValidationError, match="hash mismatch"):
        validate_candidate(candidate)


def test_rejects_mismatched_profile_snapshot():
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "New instructions.")
    changed = copy.deepcopy(snapshot)
    changed["version"] += 1
    changed["sha256"] = "a" * 64
    with pytest.raises(CandidateValidationError, match="different profile snapshot"):
        validate_candidate(candidate, baseline_snapshot=changed)


def test_rejects_invalid_or_inactive_skill():
    snapshot = _snapshot()
    with pytest.raises(CandidateValidationError, match="Invalid Skill slug"):
        build_candidate(
            snapshot,
            "content",
            target_kind="skill_content",
            skill_slug="unsafe-path",
        )
    with pytest.raises(CandidateValidationError, match="exactly one enabled Skill"):
        build_candidate(
            snapshot,
            "content",
            target_kind="skill_content",
            skill_slug="disabled-skill",
        )


def test_rejects_oversized_content():
    snapshot = _snapshot()
    with pytest.raises(CandidateValidationError, match="character limit"):
        build_candidate(snapshot, "x" * (MAX_CONTENT_CHARS + 1))


def test_diff_is_deterministic_and_uses_fixed_labels():
    snapshot = _snapshot()
    candidate = build_candidate(snapshot, "Updated instructions.")
    diff = candidate_diff(snapshot, candidate)
    assert "--- baseline/profile-instructions" in diff
    assert "+++ candidate/profile-instructions" in diff
    assert "-Check contracts and security." in diff
    assert "+Updated instructions." in diff


def test_canonical_serialization_is_stable():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
