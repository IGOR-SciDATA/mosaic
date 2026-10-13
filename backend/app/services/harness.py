import json
from typing import Any

from app.context.manager import build_context
from app.models.conversation_repository import get_conversation
from app.models.repository import get_model
from app.models.task_repository import get_task
from app.services.agent import run_agent
from app.services.chat import _get_provider

_AGENT_PROTOCOL = """Você é o componente de decisão do Agent do Mosaic Core.
Responda somente com um objeto JSON válido, sem markdown ou texto fora do JSON.
Escolha exatamente um formato:
{"type":"tool_call","tool":"NOME_DA_FERRAMENTA","arguments":{}}
{"type":"final","content":"resposta final para o usuário"}
Não afirme que uma ferramenta foi executada antes de receber seu resultado.
Use uma ferramenta somente quando ela for necessária; caso contrário, responda final.
A execução e as permissões são controladas pelo Mosaic, não por você."""


def parse_agent_decision(raw: str) -> dict[str, Any]:
    """Parse and validate the small JSON decision protocol used by the Agent."""
    try:
        decision = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Agent model response must be valid JSON") from exc

    if not isinstance(decision, dict):
        raise ValueError("Agent decision must be a JSON object")

    decision_type = decision.get("type")
    if decision_type == "final":
        content = decision.get("content")
        if not isinstance(content, str):
            raise ValueError("Final agent decision requires string content")
        return {"type": "final", "content": content}

    if decision_type == "tool_call":
        tool = decision.get("tool")
        arguments = decision.get("arguments", {})
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("Tool call decision requires a tool name")
        if not isinstance(arguments, dict):
            raise ValueError("Tool call arguments must be a JSON object")
        return {"type": "tool_call", "tool": tool, "arguments": arguments}

    raise ValueError(f"Unsupported agent decision type: {decision_type}")


def run_task_agent(task_id: int, *, iteration_limit: int = 5) -> dict[str, Any]:
    """Run an Agent Task using its conversation's configured ModelProvider."""
    task = get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.mode != "agent":
        raise ValueError("Task must use agent mode")
    if task.conversation_id is None:
        raise ValueError("Agent task requires a conversation")

    conversation = get_conversation(task.conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")
    model = get_model(conversation.model_id)
    if model is None:
        raise ValueError("Model not found")
    if not model.enabled:
        raise ValueError("Configured model is disabled")

    provider = _get_provider(model.provider)
    def decide(context: list[dict[str, str]]) -> dict[str, Any]:
        messages = [
            *context,
            {"role": "system", "content": _AGENT_PROTOCOL},
        ]
        raw = provider.generate(
            messages=messages,
            model_name=model.model_name,
            configuration=model.configuration,
        )
        return parse_agent_decision(raw)

    return run_agent(task_id, decide, iteration_limit=iteration_limit)
