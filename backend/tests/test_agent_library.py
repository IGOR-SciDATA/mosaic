from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.project_repository import create_project, get_project
from app.models.repository import create_model
from app.services.agent_library import (
    agent_snapshot_messages,
    create_agent_snapshot,
    create_project_agent,
    delete_project_agent,
    get_project_agent,
    list_project_agents,
    parse_agent_invocation,
    update_project_agent,
    validate_agent_snapshot,
)
import pytest


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()


def _project(name="Library"):
    return create_project(name, f"/tmp/{name.lower().replace(' ', '-')}")


def _payload(slug="backend-reviewer"):
    return {
        "slug": slug,
        "name": "Backend Reviewer",
        "description": "Reviews backend changes",
        "instructions": "Check contracts, edge cases and security.",
        "skills": [
            {"name": "API review", "content": "Check status codes and schemas.", "enabled": True},
            {"name": "Disabled skill", "content": "Must not enter active context.", "enabled": False},
        ],
    }


def test_project_agent_crud_and_slug_uniqueness():
    project = _project()
    created = create_project_agent(project.id, _payload())
    assert created["slug"] == "backend-reviewer"
    assert created["version"] == 1
    assert len(created["sha256"]) == 64
    assert [item["slug"] for item in list_project_agents(project.id)] == ["backend-reviewer"]
    assert get_project_agent(project.id, "backend-reviewer")["sha256"] == created["sha256"]
    with pytest.raises(ValueError, match="already exists"):
        create_project_agent(project.id, _payload())
    updated = update_project_agent(project.id, "backend-reviewer", {"description": "Updated"})
    assert updated["version"] == 2
    assert updated["sha256"] != created["sha256"]
    assert delete_project_agent(project.id, "backend-reviewer") is True
    assert list_project_agents(project.id) == []


def test_profiles_are_isolated_between_projects():
    first = _project("First")
    second = _project("Second")
    create_project_agent(first.id, _payload())
    assert list_project_agents(first.id)[0]["slug"] == "backend-reviewer"
    assert list_project_agents(second.id) == []
    with pytest.raises(ValueError, match="Unknown agent command"):
        create_agent_snapshot(second.id, "backend-reviewer")


def test_snapshot_is_immutable_and_valid_after_profile_edit():
    project = _project()
    create_project_agent(project.id, _payload())
    snapshot = create_agent_snapshot(project.id, "backend-reviewer")
    update_project_agent(project.id, "backend-reviewer", {
        "instructions": "Changed instructions.",
        "skills": [{"name": "API review", "content": "Changed skill.", "enabled": True}],
    })
    current = create_agent_snapshot(project.id, "backend-reviewer")
    assert validate_agent_snapshot(snapshot)
    assert snapshot["sha256"] != current["sha256"]
    assert snapshot["instructions"] == "Check contracts, edge cases and security."
    assert snapshot["skills"][0]["content"] == "Check status codes and schemas."


def test_skill_versions_change_only_when_skill_content_or_enabled_state_changes():
    project = _project()
    created = create_project_agent(project.id, _payload())
    skill = created["skills"][0]
    unchanged = update_project_agent(project.id, "backend-reviewer", {"skills": [
        {"name": skill["name"], "content": skill["content"], "enabled": skill["enabled"]},
        {"name": "Disabled skill", "content": "Must not enter active context.", "enabled": False},
    ]})
    assert unchanged["skills"][0]["version"] == skill["version"]
    changed = update_project_agent(project.id, "backend-reviewer", {"skills": [
        {"name": skill["name"], "content": "New procedure.", "enabled": True},
    ]})
    assert changed["skills"][0]["version"] == skill["version"] + 1
    assert changed["skills"][0]["sha256"] != skill["sha256"]


def test_agent_invocation_resolves_for_any_conversation_in_same_project():
    project = _project()
    model = create_model("Test", "ollama", "test:model")
    first = create_conversation("First", model.id, project_id=project.id)
    second = create_conversation("Second", model.id, project_id=project.id)
    create_project_agent(project.id, _payload())
    goal1, snapshot1 = parse_agent_invocation(first.project_id, "/backend-reviewer Review this endpoint")
    goal2, snapshot2 = parse_agent_invocation(second.project_id, "/backend-reviewer Review another endpoint")
    assert goal1 == "Review this endpoint"
    assert goal2 == "Review another endpoint"
    assert snapshot1["sha256"] == snapshot2["sha256"]


def test_unknown_or_empty_agent_command_fails_clearly():
    project = _project()
    with pytest.raises(ValueError, match="Unknown agent command '/missing'"):
        parse_agent_invocation(project.id, "/missing do work")
    with pytest.raises(ValueError, match="requires a task or message"):
        parse_agent_invocation(project.id, "/backend-reviewer")


def test_snapshot_integrity_and_only_enabled_skills_enter_context():
    project = _project()
    created = create_project_agent(project.id, _payload())
    snapshot = create_agent_snapshot(project.id, created["slug"])
    messages = agent_snapshot_messages(snapshot)
    flattened = "\n".join(item["content"] for item in messages)
    assert "Check status codes and schemas." in flattened
    assert "Must not enter active context." not in flattened
    tampered = dict(snapshot)
    tampered["instructions"] = "tampered"
    assert validate_agent_snapshot(tampered) is False
    with pytest.raises(ValueError, match="integrity validation"):
        agent_snapshot_messages(tampered)


def test_agent_library_is_stored_in_project_state_without_schema_changes():
    project = _project()
    create_project_agent(project.id, _payload())
    stored = get_project(project.id)
    assert stored.state["agent_library"]["backend-reviewer"]["version"] == 1
