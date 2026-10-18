import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.database import init_db
from app.models.conversation_repository import create_conversation
from app.models.message_repository import create_message
from app.models.project_repository import create_project
from app.models.repository import create_model
from app.models.task_event_repository import list_task_events
from app.models.task_repository import create_task, get_task, update_task
from app.models.tool_call_repository import create_tool_call, get_tool_call, list_tool_calls, update_tool_call
from app.models.tool_result_repository import create_tool_result, list_tool_results
from app.services.agent import _tool_context, run_agent
from app.services.tools import approve_tool_call, execute_tool_call

@pytest.fixture(autouse=True)
def test_database(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.database.DATABASE_PATH", tmp_path / "test.db")
    init_db()

def _conversation(project_id=None):
    model = create_model("Test", "ollama", "test:model")
    return create_conversation("Agent", model.id, project_id=project_id)

def _task(plan=None, project_id=None):
    conversation = _conversation(project_id)
    return create_task(type="generic", mode="agent", conversation_id=conversation.id, project_id=project_id, plan=plan)

def test_agent_auto_paginates_reads_before_model_and_excludes_unrelated_history(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Pagination", str(workspace))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "Documento.md").write_text(
        "\n".join(f"linha {number}" for number in range(1, 191)),
        encoding="utf-8",
    )
    conversation = _conversation(project.id)
    create_message(conversation.id, "user", "leia Documento_ANTIGO.md e crie um resumo")
    create_message(conversation.id, "assistant", "resposta antiga irrelevante")
    goal = "leia Documento.md"
    create_message(conversation.id, "user", goal)
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": goal},
    )

    observed_contexts = []

    def decide(context):
        observed_contexts.append(context)
        assert [message["content"] for message in context if message.get("role") == "user"] == [goal]
        flattened = "\n".join(str(message.get("content", "")) for message in context)
        assert "resposta antiga irrelevante" not in flattened
        assert "Documento_ANTIGO.md" not in flattened
        assert "linha 190" in flattened
        # Evidence is presented before the active goal; the goal must be the final
        # message so the model acts on the evidence instead of copying tool metadata.
        assert context[-1] == {"role": "user", "content": goal}
        assert context[-2]["role"] == "system"
        assert "linha 190" in context[-2]["content"]
        assert "ToolResult" not in context[-2]["content"]
        assert "'operation': 'read'" not in context[-2]["content"]
        read_calls = [
            call for call in list_tool_calls(conversation.id)
            if call.task_id == task.id and call.tool_name == "filesystem"
            and call.arguments.get("operation") == "read"
        ]
        assert len(read_calls) == 3
        return {"type": "final", "content": "Li o documento completo."}

    result = run_agent(task.id, decide)

    assert result["status"] == "completed"
    assert len(observed_contexts) == 1
    assert get_task(task.id).plan["planner_version"] == "task-plan-v1"
    assert get_task(task.id).plan["steps"][0]["status"] == "completed"


@pytest.mark.parametrize(
    "goal",
    [
        "crie um novo arquivo .md com um resumo",
        "faça um novo arquivo .md com um resumo do que está escrito",
        "fazer um novo arquivo Markdown com um resumo",
    ],
)
def test_agent_does_not_complete_file_creation_goal_without_verified_artifact(goal: str):
    task = _task(plan={"goal": goal})
    result = run_agent(
        task.id,
        lambda context: {"type": "final", "content": "Criei o resumo."},
        iteration_limit=1,
    )
    assert result["status"] == "failed"
    assert get_task(task.id).status == "failed"


def test_agent_turns_final_summary_into_approved_artifact_creation(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Deterministic artifact creation", str(workspace))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "Documento.md").write_text(
        "# Documento\n\nConteúdo de origem para resumir.\n",
        encoding="utf-8",
    )
    task = _task(
        plan={"goal": "leia Documento.md e faça um novo arquivo .md com um resumo"},
        project_id=project.id,
    )
    source_read = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "read", "path": "Documento.md"},
        task_id=task.id,
    )
    assert execute_tool_call(approve_tool_call(source_read)).status == "completed"

    summary = (
        "# Resumo do documento\n\n"
        "O documento descreve a proposta, seus objetivos e os passos iniciais para validar a solução. "
        "A implementação deverá ser modular, com foco em entregar um protótipo funcional.\n\n"
        "Para criar um documento Markdown baseado nesse texto, vou começar com o título e a estrutura."
    )
    result = run_agent(task.id, lambda context: {"type": "final", "content": summary})

    assert result["status"] == "awaiting_approval"
    assert get_task(task.id).status == "awaiting_approval"
    calls = [call for call in list_tool_calls(task.conversation_id) if call.task_id == task.id]
    create_call = next(
        call for call in calls
        if call.tool_name == "filesystem" and call.arguments.get("operation") == "create"
    )
    assert create_call.arguments["path"] == "Resumo_Documento.md"
    assert "Para criar um documento" not in create_call.arguments["content"]
    assert create_call.arguments["content"].startswith("# Resumo do documento")

    assert execute_tool_call(approve_tool_call(create_call)).status == "completed"
    update_task(task.id, status="executing")
    completed = run_agent(task.id, lambda context: {"type": "final", "content": summary})

    assert completed["status"] == "completed"
    assert completed["artifact"]["path"] == "Resumo_Documento.md"
    assert (workspace / "Resumo_Documento.md").is_file()


@pytest.mark.parametrize(
    ("goal", "expected_sources", "expected_output"),
    [
        (
            "leia docs/Documento.md e crie um novo arquivo .md com um resumo",
            ["docs/Documento.md"],
            "docs/Resumo_Documento.md",
        ),
        (
            "leia docs/Documento.md e depois crie um novo arquivo .md com um resumo",
            ["docs/Documento.md"],
            "docs/Resumo_Documento.md",
        ),
        (
            "leia Documento.md e crie um arquivo chamado Saida.md com um resumo",
            ["Documento.md"],
            "Saida.md",
        ),
        ("crie um arquivo Saida.md", [], "Saida.md"),
        ("salve o resumo como Saida.md", [], "Saida.md"),
    ],
)
def test_file_task_intent_paths_are_resolved_deterministically(goal, expected_sources, expected_output):
    from app.services.agent import _artifact_output_path, _goal_requires_file_artifact, _required_source_paths

    assert _required_source_paths(goal) == expected_sources
    assert _goal_requires_file_artifact(goal)
    assert _artifact_output_path(goal) == expected_output


def test_artifact_content_keeps_short_documents_and_removes_trailing_narration():
    from app.services.agent import _artifact_content_from_final

    assert _artifact_content_from_final("OK") is None
    assert _artifact_content_from_final("# OK") == "# OK"
    assert _artifact_content_from_final(
        "# Resumo\n\nO projeto combina voz, IA e animação. Vamos criar um documento de escopo detalhado agora."
    ) == "# Resumo\n\nO projeto combina voz, IA e animação."


def test_history_is_included_only_when_goal_requests_continuity():
    from app.services.agent import _agent_context

    raw_context = [
        {"role": "system", "content": "Mosaic identity"},
        {"role": "system", "content": 'Mosaic project state: {"skills":[{"name":"Disabled guide","enabled":false}]} '},
        {"role": "user", "content": "old unrelated request"},
        {"role": "assistant", "content": "old unrelated answer"},
        {"role": "user", "content": "leia B.md"},
    ]

    scoped = _agent_context(raw_context, "leia B.md", {"steps": [], "current_step": None})
    scoped_text = "\n".join(message["content"] for message in scoped)
    assert "old unrelated request" not in scoped_text
    assert "old unrelated answer" not in scoped_text
    assert "Disabled guide" not in scoped_text

    continuity = _agent_context(
        raw_context,
        "continue from the previous conversation and read B.md",
        {"steps": [], "current_step": None},
    )
    flattened = "\n".join(message["content"] for message in continuity)
    assert "old unrelated request" in flattened
    assert "old unrelated answer" in flattened
    assert "Disabled guide" not in flattened

    project_state = _agent_context(
        raw_context,
        "show the project state",
        {"steps": [], "current_step": None},
    )
    assert "Disabled guide" in "\n".join(message["content"] for message in project_state)


def test_agent_creates_explicit_subtasks_for_read_summarize_create(tmp_path: Path):
    from app.services.agent import _build_task_steps

    steps = _build_task_steps(
        "leia o arquivo docs/Documento.md e faça um novo arquivo .md com um resumo"
    )

    assert [step["kind"] for step in steps] == [
        "read_file",
        "summarize_source",
        "create_artifact",
    ]
    assert steps[0]["path"] == "docs/Documento.md"
    assert steps[2]["path"] == "docs/Resumo_Documento.md"
    assert steps[0]["depends_on"] == []
    assert steps[1]["depends_on"] == ["read_source_1"]
    assert steps[2]["depends_on"] == ["summarize_source"]


def test_task_step_cannot_start_before_dependencies_are_complete(tmp_path: Path):
    from app.services.agent import _ensure_task_plan, _set_task_step_status

    project = create_project("Task step dependencies", str(tmp_path))
    task = _task(
        plan={"goal": "leia Documento.md e crie um novo arquivo Resumo.md com um resumo"},
        project_id=project.id,
    )
    _ensure_task_plan(task.id)

    with pytest.raises(ValueError, match="dependencies are incomplete"):
        _set_task_step_status(task.id, "summarize_source", "in_progress")


def test_existing_file_update_is_planned_as_read_transform_write():
    from app.services.agent import _artifact_operation, _artifact_output_path, _build_task_steps

    goal = "atualize README.md para incluir uma seção de instalação"
    steps = _build_task_steps(goal)

    assert [step["kind"] for step in steps] == [
        "read_file",
        "transform_source",
        "write_artifact",
    ]
    assert steps[0]["path"] == "README.md"
    assert steps[2]["path"] == "README.md"
    assert _artifact_output_path(goal) == "README.md"
    assert _artifact_operation(goal) == "write"


def test_agent_updates_existing_file_only_after_approval(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Update existing file", str(workspace))
    workspace.mkdir(parents=True, exist_ok=True)
    readme = workspace / "README.md"
    readme.write_text("# Projeto\n\nDescrição original.\n", encoding="utf-8")
    task = _task(
        plan={"goal": "atualize README.md para incluir uma seção de instalação"},
        project_id=project.id,
    )
    updated_content = (
        "# Projeto\n\nDescrição original.\n\n"
        "## Instalação\n\nExecute pip install -r requirements.txt.\n"
    )

    result = run_agent(
        task.id,
        lambda context: {"type": "final", "content": updated_content},
    )

    assert result["status"] == "awaiting_approval"
    call = next(
        call for call in list_tool_calls(task.conversation_id)
        if call.task_id == task.id and call.tool_name == "filesystem"
        and call.arguments.get("operation") == "write"
    )
    assert call.arguments["path"] == "README.md"
    assert call.arguments["overwrite"] is True
    assert readme.read_text(encoding="utf-8") == "# Projeto\n\nDescrição original.\n"

    assert execute_tool_call(approve_tool_call(call)).status == "completed"
    update_task(task.id, status="executing")
    completed = run_agent(task.id, lambda context: pytest.fail("Verified output must complete without another model call"))

    assert completed["status"] == "completed"
    assert completed["artifact"]["path"] == "README.md"
    assert "## Instalação" in readme.read_text(encoding="utf-8")


def test_agent_task_context_contains_only_current_task_tool_results(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Task isolation", str(workspace))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "A.md").write_text("Conteúdo do arquivo A.", encoding="utf-8")
    (workspace / "B.md").write_text("Conteúdo exclusivo do arquivo B.", encoding="utf-8")
    conversation = _conversation(project.id)

    old_goal = "leia A.md e faça um resumo antigo"
    create_message(conversation.id, "user", old_goal)
    create_message(conversation.id, "assistant", "RESUMO ANTIGO QUE NÃO DEVE VAZAR")
    old_task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": old_goal},
    )
    old_read = create_tool_call(
        conversation.id,
        "filesystem",
        {"operation": "read", "path": "A.md"},
        task_id=old_task.id,
    )
    assert execute_tool_call(approve_tool_call(old_read)).status == "completed"

    goal = "leia B.md"
    create_message(conversation.id, "user", goal)
    task = create_task(
        type="generic",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": goal},
    )
    observed_contexts = []

    def decide(context):
        observed_contexts.append(context)
        flattened = "\n".join(str(message.get("content", "")) for message in context)
        assert [message["content"] for message in context if message.get("role") == "user"] == [goal]
        assert "RESUMO ANTIGO QUE NÃO DEVE VAZAR" not in flattened
        assert "Conteúdo exclusivo do arquivo B." in flattened
        assert "Conteúdo do arquivo A." not in flattened
        return {"type": "final", "content": "Li somente o arquivo B."}

    result = run_agent(task.id, decide)

    assert result["status"] == "completed"
    assert len(observed_contexts) == 1


def test_agent_recovers_artifact_after_post_write_verification_error(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Artifact recovery", str(workspace))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "Documento.md").write_text("# Documento\n\nFonte completa.\n", encoding="utf-8")
    goal = "Leia Documento.md e faça um novo arquivo .md com um resumo do que está escrito."
    task = _task(plan={"goal": goal}, project_id=project.id)
    content = "# Resumo\n\nO documento apresenta a proposta e os objetivos do projeto.\n"
    output_path = workspace / "Resumo_Documento.md"
    output_path.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))

    call = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "create", "path": "Resumo_Documento.md", "content": content},
        task_id=task.id,
    )
    approve_tool_call(call)
    update_tool_call(call.id, status="executing")
    update_tool_call(call.id, status="failed")
    create_tool_result(
        call.id,
        "failed",
        error="OSError: Written file could not be verified",
    )

    def unexpected_model_call(context):
        raise AssertionError("Recovery must finish without another model inference")

    result = run_agent(task.id, unexpected_model_call)

    assert result["status"] == "completed"
    assert result["iterations"] == 0
    assert result["artifact"]["path"] == "Resumo_Documento.md"
    assert result["artifact"]["recovered_after_verification_error"] is True
    assert get_task(task.id).status == "completed"
    assert get_task(task.id).plan["steps"][-1]["status"] == "completed"


def test_agent_does_not_complete_summary_without_reading_named_source(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Source validation", str(workspace))
    task = _task(
        plan={"goal": "leia Documento.md e crie um novo arquivo .md com um resumo"},
        project_id=project.id,
    )
    output_create = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "create", "path": "Resumo.md", "content": "# Resumo\\n\\nTexto sem fonte."},
        task_id=task.id,
    )
    assert execute_tool_call(approve_tool_call(output_create)).status == "completed"

    result = run_agent(
        task.id,
        lambda context: {"type": "final", "content": "Criei o resumo."},
        iteration_limit=1,
    )
    assert result["status"] == "failed"
    assert get_task(task.id).status == "failed"


def test_agent_completes_file_creation_goal_only_after_artifact_is_verified(tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = create_project("Artifact validation", str(workspace))
    task = _task(
        plan={"goal": "leia Documento.md e crie um novo arquivo .md com um resumo"},
        project_id=project.id,
    )
    source_create = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "create", "path": "Documento.md", "content": "\n".join(f"linha {number}" for number in range(1, 101))},
        task_id=task.id,
    )
    assert execute_tool_call(approve_tool_call(source_create)).status == "completed"
    source_read = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "read", "path": "Documento.md"},
        task_id=task.id,
    )
    first_read_result = execute_tool_call(approve_tool_call(source_read))
    assert first_read_result.status == "completed"
    source_read_next = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "read", "path": "Documento.md", "start_line": 81, "max_lines": 80},
        task_id=task.id,
    )
    second_read_result = execute_tool_call(approve_tool_call(source_read_next))
    assert second_read_result.status == "completed"
    output_create = create_tool_call(
        task.conversation_id,
        "filesystem",
        {"operation": "create", "path": "Resumo_Documento.md", "content": "# Resumo\n\nConteúdo."},
        task_id=task.id,
    )
    tool_result = execute_tool_call(approve_tool_call(output_create))
    assert tool_result.status == "completed"

    result = run_agent(
        task.id,
        lambda context: {"type": "final", "content": "Criei o resumo."},
        iteration_limit=1,
    )
    assert result["status"] == "completed"
    assert result["artifact"]["path"] == "Resumo_Documento.md"
    assert result["artifact"]["bytes"] > 0
    assert (workspace / "Resumo_Documento.md").is_file()



def test_markdown_summary_flow_reads_source_creates_and_reopens_verified_artifact(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source_content = (
        "# Plano do projeto\n\n"
        "## Objetivo\nConstruir um protótipo funcional.\n\n"
        "## Etapas\n- Implementar a API.\n- Validar a interface.\n"
    )
    (workspace / "Documento.md").write_text(source_content, encoding="utf-8")
    project = create_project("Markdown regression", str(workspace))
    goal = "leia Documento.md e crie um novo arquivo Resumo.md com um resumo"
    task = _task(plan={"goal": goal}, project_id=project.id)
    observed_contexts = []

    summary = (
        "# Resumo do projeto\n\n"
        "## Objetivo\nConstruir um protótipo funcional.\n\n"
        "## Etapas principais\n"
        "- Implementar e validar a API.\n"
        "- Validar a interface antes de concluir.\n"
    )

    def decide(context):
        observed_contexts.append(context)
        evidence = "\n".join(
            item["content"] for item in context if item.get("role") == "system"
        )
        assert "Construir um protótipo funcional." in evidence
        assert "Implementar a API." in evidence
        assert context[-1] == {"role": "user", "content": goal}
        return {"type": "final", "content": summary}

    pending = run_agent(task.id, decide)
    assert pending["status"] == "awaiting_approval"
    assert len(observed_contexts) == 1

    calls = [call for call in list_tool_calls(task.conversation_id) if call.task_id == task.id]
    source_reads = [
        call for call in calls
        if call.tool_name == "filesystem" and call.arguments.get("operation") == "read"
        and call.arguments.get("path") == "Documento.md"
    ]
    output_call = next(
        call for call in calls
        if call.tool_name == "filesystem"
        and call.arguments.get("operation") == "create"
        and call.arguments.get("path") == "Resumo.md"
    )
    assert source_reads
    assert output_call.status == "pending"
    assert output_call.arguments["content"].startswith("# Resumo do projeto")
    assert "## Objetivo" in output_call.arguments["content"]
    assert "## Etapas principais" in output_call.arguments["content"]

    write_result = execute_tool_call(approve_tool_call(output_call))
    assert write_result.status == "completed"
    update_task(task.id, status="executing")
    completed = run_agent(
        task.id,
        lambda context: pytest.fail("A verified Markdown artifact must complete without another model call"),
    )

    artifact_path = workspace / "Resumo.md"
    assert completed["status"] == "completed"
    assert completed["artifact"]["path"] == "Resumo.md"
    assert artifact_path.is_file()
    reopened = artifact_path.read_text(encoding="utf-8")
    assert reopened == output_call.arguments["content"]
    assert reopened.startswith("# Resumo do projeto")
    assert "Construir um protótipo funcional." in reopened
    assert "## Etapas principais" in reopened
    assert len(reopened.encode("utf-8")) == completed["artifact"]["bytes"]
    assert completed["artifact"]["verified"] is True
    assert completed["artifact"]["sha256"] == hashlib.sha256(reopened.encode("utf-8")).hexdigest()
    assert completed["artifact"]["verification_method"] == "sha256+persisted_content_match"
    assert completed["artifact"]["verification_event_recorded"] is True
    verification_events = [
        event for event in list_task_events(task.id)
        if event.event_name == "artifact.verified"
    ]
    assert len(verification_events) == 1
    assert verification_events[0].metadata["sha256"] == completed["artifact"]["sha256"]
    assert verification_events[0].tool_call_id == output_call.id
    assert verification_events[0].metadata["tool_result_id"] > 0
    assert any(result.status == "completed" for result in list_tool_results(output_call.id))

    persisted_plan = get_task(task.id).plan
    persisted_steps = {step["id"]: step for step in persisted_plan["steps"]}
    assert all(step["status"] == "completed" for step in persisted_steps.values())
    source_step = persisted_steps["read_source_1"]
    assert source_step["source_path"] == "Documento.md"
    assert source_step["source_sha256"] == hashlib.sha256(source_content.encode("utf-8")).hexdigest()
    assert source_step["tool_call_ids"]
    assert source_step["tool_result_ids"]
    summary_step = persisted_steps["summarize_source"]
    assert summary_step["output_sha256"] == hashlib.sha256(reopened.encode("utf-8")).hexdigest()
    assert summary_step["output_chars"] == len(reopened)
    artifact_step = persisted_steps["create_artifact"]
    assert artifact_step["artifact_path"] == "Resumo.md"
    assert artifact_step["artifact_sha256"] == completed["artifact"]["sha256"]
    assert artifact_step["artifact_verified"] is True

def test_web_research_report_fetches_source_and_persists_cited_url(tmp_path: Path, monkeypatch):
    from email.message import Message
    from io import BytesIO

    workspace = tmp_path / "web-workspace"
    workspace.mkdir()
    project = create_project("Web research report", str(workspace))
    conversation = _conversation(project.id)
    goal = "pesquise na internet sobre o Mosaic e crie um relatório Markdown chamado Relatorio.md com referências"
    task = create_task(
        type="report",
        mode="agent",
        conversation_id=conversation.id,
        project_id=project.id,
        plan={"goal": goal},
    )
    search_html = (
        b'<div class="result"><a class="result__a" href="https://example.com/mosaic">Mosaic source</a>'
        b'<div class="result__snippet">A source about the Mosaic project.</div></div>'
    )

    class FakePage:
        def __init__(self, url, body):
            self._url = url
            self._body = body
            self.headers = Message()
            self.headers["Content-Type"] = "text/html; charset=utf-8"

        def read(self, limit=-1):
            return self._body if limit < 0 else self._body[:limit]

        def geturl(self):
            return self._url

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    page_html = (
        b"<html><head><title>Mosaic source page</title></head>"
        b"<body><main><p>Mosaic preserves task state and verified artifacts.</p></main></body></html>"
    )

    def fake_urlopen(request, timeout):
        url = request.full_url
        assert timeout == 10
        if url.startswith("https://html.duckduckgo.com/html/?q="):
            return BytesIO(search_html)
        assert url == "https://example.com/mosaic"
        return FakePage(url, page_html)

    monkeypatch.setattr("app.tools.builtin.safe_urlopen", fake_urlopen)

    search_call = create_tool_call(
        conversation.id, "search", {"query": "Mosaic project"}, task_id=task.id
    )
    search_result = execute_tool_call(approve_tool_call(search_call))
    assert search_result.status == "completed"
    source_url = search_result.data["results"][0]["url"]

    fetch_call = create_tool_call(
        conversation.id, "web_fetch", {"url": source_url}, task_id=task.id
    )
    fetch_result = execute_tool_call(approve_tool_call(fetch_call))
    assert fetch_result.status == "completed"
    assert "Mosaic preserves task state" in fetch_result.data["content"]

    report = (
        "# Relatório sobre o Mosaic\n\n"
        "O Mosaic preserva o estado das tarefas e verifica os artefatos produzidos.\n\n"
        "## Referências\n"
        f"- [Mosaic source]({source_url})"
    )
    pending = run_agent(task.id, lambda context: {"type": "final", "content": report})
    assert pending["status"] == "awaiting_approval"

    output_call = next(
        call for call in list_tool_calls(conversation.id)
        if call.task_id == task.id
        and call.tool_name == "filesystem"
        and call.arguments.get("operation") == "create"
        and call.arguments.get("path") == "Relatorio.md"
    )
    write_result = execute_tool_call(approve_tool_call(output_call))
    assert write_result.status == "completed"
    update_task(task.id, status="executing")
    completed = run_agent(
        task.id,
        lambda context: pytest.fail("A verified research report must finish without another model call"),
    )

    assert completed["status"] == "completed"
    assert completed["artifact"]["path"] == "Relatorio.md"
    assert completed["artifact"]["verified"] is True
    reopened = (workspace / "Relatorio.md").read_text(encoding="utf-8")
    assert source_url in reopened
    persisted_plan = get_task(task.id).plan
    steps = {step["id"]: step for step in persisted_plan["steps"]}
    assert [step["kind"] for step in persisted_plan["steps"]] == [
        "research_sources", "draft_content", "create_artifact"
    ]
    assert steps["research_sources"]["status"] == "completed"
    assert steps["research_sources"]["sources"][0]["url"] == source_url
    assert steps["research_sources"]["sources"][0]["tool_result_id"] == fetch_result.id
    assert steps["research_sources"]["cited_urls"] == [source_url]
    assert steps["draft_content"]["output_sha256"] == hashlib.sha256(reopened.encode("utf-8")).hexdigest()
    assert steps["create_artifact"]["artifact_verified"] is True


def test_tool_observation_is_bounded_and_marks_truncation():
    result = SimpleNamespace(status="completed", data={"content": "x" * 20_000}, error=None)
    observation = _tool_context(1, result)
    assert len(observation["content"]) < 13_000
    assert "observação truncada pelo Core" in observation["content"]


def test_agent_returns_native_tool_result_in_protocol_shape():
    task = _task()
    observed = []

    def decide(context):
        observed.append(context)
        if len(observed) == 1:
            return {
                "type": "tool_call",
                "tool": "calculator",
                "arguments": {"expression": "2 + 3"},
                "_native_message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "calculator",
                            "arguments": {"expression": "2 + 3"},
                        }
                    }],
                },
            }
        assert any(message.get("role") == "assistant" and "tool_calls" in message for message in context)
        tool_result = next(message for message in context if message.get("role") == "tool")
        assert tool_result["tool_name"] == "calculator"
        assert "5" in tool_result["content"]
        return {"type": "final", "content": "O resultado é 5."}

    result = run_agent(task.id, decide)

    assert result["status"] == "completed"
    assert len(observed) == 2


def test_agent_runs_tool_then_returns_final():
    task = _task()
    decisions = iter([
        {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "2 + 3"}},
        {"type": "final", "content": "O resultado é 5."},
    ])
    result = run_agent(task.id, lambda context: next(decisions))
    assert result["status"] == "completed"
    assert result["iterations"] == 2
    assert get_task(task.id).status == "completed"

def test_agent_passes_tool_observation_to_next_decision():
    task = _task()
    observed = []
    def decide(context):
        observed.append(list(context))
        if len(observed) == 1:
            return {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "7 * 6"}}
        assert any(message["role"] == "system" and "42" in message["content"] for message in context)
        return {"type": "final", "content": "42"}
    result = run_agent(task.id, decide)
    assert result["status"] == "completed"
    assert len(observed) == 2

def test_agent_stops_for_approval_required_tool():
    task = _task()
    result = run_agent(
        task.id,
        lambda context: {
            "type": "tool_call",
            "tool": "filesystem",
            "arguments": {"operation": "create", "path": "Resumo.md", "content": "# Resumo"},
        },
    )
    assert result["status"] == "awaiting_approval"
    assert get_task(task.id).status == "awaiting_approval"
    call = get_tool_call(result["tool_call_id"])
    assert call.status == "pending"
    assert list_tool_results(call.id) == []

def test_agent_respects_iteration_limit():
    task = _task()
    result = run_agent(task.id, lambda context: {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "1 + 1"}}, iteration_limit=2)
    assert result["status"] == "failed"
    assert result["iterations"] == 2
    assert get_task(task.id).status == "failed"

def test_agent_can_be_cancelled_before_tool_execution():
    task = _task()
    calls = 0
    def decide(context):
        nonlocal calls
        calls += 1
        update_task(task.id, status="cancelled")
        return {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "1 + 1"}}
    result = run_agent(task.id, decide)
    assert result["status"] == "cancelled"
    assert calls == 1


def test_agent_stops_consecutive_duplicate_failed_tool_call():
    task = _task()
    repeated = {
        "type": "tool_call",
        "tool": "calculator",
        "arguments": {"expression": "1 +"},
    }
    decisions = iter([repeated, repeated])

    result = run_agent(task.id, lambda context: next(decisions))
    calls = [call for call in list_tool_calls(task.conversation_id) if call.task_id == task.id]

    assert result["status"] == "failed"
    assert "loop" in result["error"].lower()
    assert len(calls) == 1
    assert calls[0].status == "failed"


def test_agent_blocks_consecutive_duplicate_successful_tool_call():
    task = _task()
    decisions = iter([
        {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "7 * 6"}},
        {"type": "tool_call", "tool": "calculator", "arguments": {"expression": "7 * 6"}},
        {"type": "final", "content": "O resultado é 42."},
    ])
    result = run_agent(task.id, lambda context: next(decisions))
    calls = [call for call in list_tool_calls(task.conversation_id) if call.task_id == task.id]
    assert result["status"] == "completed"
    assert len(calls) == 1
