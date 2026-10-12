import json
import re
from typing import Any

from app.identity import MOSAIC_IDENTITY
from app.memory.manager import get_global_memories, get_project_memories
from app.models.conversation_repository import get_conversation
from app.models.message_repository import list_messages
from app.models.task_repository import list_tasks
from app.models.tool_call_repository import list_tool_calls
from app.models.tool_result_repository import list_tool_results

RECENT_HISTORY_LIMIT = 20
ACTIVE_TASK_STATUSES = {
    "pending",
    "planning",
    "awaiting_approval",
    "executing",
    "validating",
}

_IDENTITY_QUESTION = re.compile(
    r"\b(?:quem\s+(?:é|e)\s+voc[eê]|quem\s+(?:é|e)\s+o\s+mosaic|"
    r"o\s+que\s+(?:é|e)\s+voc[eê]|qual\s+(?:é|e)\s+sua\s+identidade|"
    r"fale\s+sobre\s+voc[eê])\b",
    re.IGNORECASE,
)


def _is_identity_question(content: str | None) -> bool:
    return bool(content and _IDENTITY_QUESTION.search(content))


def _task_context(conversation_id: int) -> dict[str, Any] | None:
    tasks = list_tasks(conversation_id=conversation_id)
    active = [task for task in tasks if task.status in ACTIVE_TASK_STATUSES]
    if not active:
        return None

    task = active[-1]
    return {
        "id": task.id,
        "type": task.type,
        "mode": task.mode,
        "status": task.status,
        "plan": task.plan,
        "result": task.result,
    }


def _tool_result_messages(conversation_id: int) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    for tool_call in list_tool_calls(conversation_id):
        if tool_call.id is None:
            continue

        for result in list_tool_results(tool_call.id):
            if result.status == "completed":
                payload = json.dumps(result.data, ensure_ascii=False)
            else:
                payload = json.dumps({"error": result.error}, ensure_ascii=False)

            messages.append({
                "role": "tool",
                "content": (
                    f"Mosaic tool result [{tool_call.tool_name}] "
                    f"({result.status}): {payload}"
                ),
            })

    return messages


def build_context(conversation_id: int) -> list[dict[str, str]]:
    """Build deterministic MVP context without sending unbounded full history."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")

    all_messages = list_messages(conversation_id)
    context: list[dict[str, str]] = []

    current_user = next(
        (
            message
            for message in reversed(all_messages)
            if message.role == "user"
        ),
        None,
    )

    # Identity and behavioral rules belong to Mosaic Core, not the selected model.
    context.append({
        "role": "system",
        "content": (
            MOSAIC_IDENTITY + "\n\n"
            "Você gera respostas em nome do Mosaic; não se apresente como um modelo genérico nem negue a identidade operacional descrita acima.\n"
            "O Mosaic Core controla identidade, histórico e memórias; o modelo não deve alegar que sua memória interna é a fonte desses dados.\n"
            "Trate memórias como informações registradas, não como verdade automaticamente confirmada.\n"
            "Uma alegação do usuário deve continuar identificada como alegação do usuário. Ao responder perguntas factuais, diferencie o conhecimento factual disponível daquilo que o usuário pediu para guardar.\n"
            "Use memórias somente quando forem relevantes para responder à pergunta atual; não introduza alegações anteriores em respostas sem relação com elas.\n"
            "Ao responder quem é você, explique apenas a identidade e o funcionamento do Mosaic; não mencione memórias do usuário, fatos históricos ou assuntos anteriores sem solicitação.\n"
            "Não invente datas de criação, lançamento ou disponibilidade do Mosaic. Se perguntarem uma data que não esteja registrada em fonte confiável, diga que não tem essa informação confirmada.\n"
            "Quando uma memória relevante estiver disponível no contexto, mencione-a quando pertinente sem substituir o fato por ela.\n"
            "Não diga que verificou fontes externas se nenhuma fonte ou ferramenta de verificação foi fornecida nesta solicitação."
        ),
    })
    context.extend(
        {"role": message.role, "content": message.content}
        for message in all_messages
        if message.role == "system"
    )

    if conversation.project_id is not None:
        from app.models.project_repository import get_project

        project = get_project(conversation.project_id)
        if project is not None and project.state:
            context.append({
                "role": "system",
                "content": "Mosaic project state:\n" + str(project.state),
            })

        memories = get_project_memories(conversation.project_id)
    else:
        memories = []

    # Identity questions need the canonical identity, not unrelated user/project memories.
    # Keep memory retrieval out of this turn instead of relying only on model instructions.
    if _is_identity_question(current_user.content if current_user else None):
        memories = []
    else:
        # Global memories are shared across conversations; project memories stay isolated.
        memories = get_global_memories() + memories
    if memories:
        memory_lines = [
            f"- [{memory.type}] {memory.key}: {memory.value}"
            for memory in memories
        ]
        context.append({
            "role": "system",
            "content": "Mosaic memory (records, not verified facts):\n" + "\n".join(memory_lines),
        })


    history = [
        {"role": message.role, "content": message.content}
        for message in all_messages
        if message.role in {"user", "assistant", "tool"}
        and (current_user is None or message.id != current_user.id)
    ]
    context.extend(history[-RECENT_HISTORY_LIMIT:])

    task = _task_context(conversation_id)
    if task is not None:
        context.append({
            "role": "system",
            "content": "Mosaic current task:\n" + json.dumps(
                task,
                ensure_ascii=False,
            ),
        })

    context.extend(_tool_result_messages(conversation_id))

    if current_user is not None:
        context.append({
            "role": "user",
            "content": current_user.content,
        })

    return context
