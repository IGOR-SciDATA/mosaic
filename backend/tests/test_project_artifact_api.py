import pytest
from fastapi import HTTPException

from app.api.projects import (
    list_project_artifacts_endpoint,
    read_project_artifact_excerpt_endpoint,
    search_project_artifacts_endpoint,
    update_project_artifact_endpoint,
    WorkspaceFileUpdate,
)
from app.db.database import init_db
from app.models.project_repository import create_project


@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "project-artifacts.db")
    init_db()


def test_project_artifact_api_lists_and_reads_only_workspace_files(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("Mosaic project guide\nAgent context and tasks.", encoding="utf-8")
    project = create_project("Workspace", str(workspace))

    inventory = list_project_artifacts_endpoint(project.id)
    excerpt = read_project_artifact_excerpt_endpoint(project.id, "README.md", start_line=2, max_lines=1)
    search = search_project_artifacts_endpoint(project.id, "agent context")

    assert inventory["count"] == 1
    assert inventory["entries"][0]["path"] == "README.md"
    assert excerpt["content"] == "Agent context and tasks."
    assert excerpt["start_line"] == 2
    assert search["results"][0]["path"] == "README.md"


def test_project_artifact_api_rejects_path_traversal(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = create_project("Workspace", str(workspace))

    with pytest.raises(HTTPException) as exc:
        read_project_artifact_excerpt_endpoint(project.id, "../outside.txt")
    assert exc.value.status_code == 400


def test_project_artifact_api_returns_404_for_unknown_project():
    with pytest.raises(HTTPException) as exc:
        list_project_artifacts_endpoint(987654)
    assert exc.value.status_code == 404


def test_project_artifact_api_saves_existing_utf8_text_file(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "README.md"
    target.write_text("# Before\n", encoding="utf-8")
    project = create_project("Workspace", str(workspace))

    result = update_project_artifact_endpoint(
        project.id,
        WorkspaceFileUpdate(content="# Depois\nConteúdo atualizado.\n"),
        path="README.md",
    )

    assert result["saved"] is True
    assert target.read_text(encoding="utf-8") == "# Depois\nConteúdo atualizado.\n"


def test_project_artifact_api_rejects_edit_path_traversal(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("não alterar", encoding="utf-8")
    project = create_project("Workspace", str(workspace))

    with pytest.raises(HTTPException) as exc:
        update_project_artifact_endpoint(
            project.id,
            WorkspaceFileUpdate(content="conteúdo malicioso"),
            path="../outside.txt",
        )

    assert exc.value.status_code == 400
    assert outside.read_text(encoding="utf-8") == "não alterar"
