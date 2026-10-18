"""Versioned, permission-neutral guidance profiles for persisted Task snapshots."""

import hashlib
from typing import Any

PROFILE_VERSION = "1.0"

PROFILE_INSTRUCTIONS: dict[str, str] = {
    "architecture": (
        "Mapear limites de módulos, contratos, fluxos e trade-offs. Preferir a menor mudança "
        "compatível com a arquitetura aprovada. Não inventar schema, infraestrutura ou permissões."
    ),
    "backend": (
        "Focar em API, serviços, persistência, estados e validação determinística. Preservar "
        "contratos e adicionar testes para caminhos de sucesso, falha e segurança."
    ),
    "frontend": (
        "Focar em React/Vite, acessibilidade e clareza. A interface deve refletir estados reais "
        "do Core e nunca inventar progresso, permissões ou conclusão."
    ),
    "research": (
        "Distinguir fatos, inferências e lacunas. Usar apenas fontes realmente acessadas, "
        "registrar referências rastreáveis e nunca inventar resultados ou citações."
    ),
    "documentation": (
        "Documentar comportamento observado e decisões aprovadas. Preservar terminologia, "
        "explicitar limitações e não descrever capacidades não comprovadas como concluídas."
    ),
    "qa": (
        "Validar critérios de aceite, estados, regressões e artefatos com evidências reproduzíveis. "
        "Não considerar afirmações do modelo como prova e não declarar testes não executados."
    ),
}

PROFILE_NAMES = frozenset(PROFILE_INSTRUCTIONS)


def create_agent_profile_snapshot(name: str) -> dict[str, Any]:
    """Create a stable per-Task snapshot; profile text never grants tool permissions."""
    if name not in PROFILE_INSTRUCTIONS:
        raise ValueError(f"Unknown agent profile: {name}")
    instructions = PROFILE_INSTRUCTIONS[name]
    digest_input = f"{PROFILE_VERSION}\n{name}\n{instructions}".encode("utf-8")
    return {
        "name": name,
        "version": PROFILE_VERSION,
        "instructions": instructions,
        "sha256": hashlib.sha256(digest_input).hexdigest(),
    }


def validate_agent_profile_snapshot(snapshot: Any) -> bool:
    if not isinstance(snapshot, dict):
        return False
    name = snapshot.get("name")
    version = snapshot.get("version")
    instructions = snapshot.get("instructions")
    digest = snapshot.get("sha256")
    if not all(isinstance(value, str) for value in (name, version, instructions, digest)):
        return False
    if name not in PROFILE_NAMES or version != PROFILE_VERSION:
        return False
    expected = hashlib.sha256(f"{version}\n{name}\n{instructions}".encode("utf-8")).hexdigest()
    return digest == expected and instructions == PROFILE_INSTRUCTIONS[name]
