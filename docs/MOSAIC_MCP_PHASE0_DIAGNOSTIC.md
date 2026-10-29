# Fase 0 — Diagnóstico da interoperabilidade MCP

**Repositório:** `IGOR-SciDATA/mosaic`  
**Branch de trabalho:** `feat/mcp-plugin-interoperability-phase1`  
**Base inspecionada:** `main` em 29/10/2026  
**Status:** diagnóstico concluído parcialmente; implementação incremental prossegue na Fase 1.

## Contratos e documentos

- `docs/MOSAIC_MCP_AND_COMMUNITY_PLUGINS_RESEARCH_v1.0.md`: encontrado em `research/mcp-plugin-support`, SHA `2ccc2e502cf74706fc9a6f6c7d35c0e0676ab898`.
- `docs/MOSAIC_GITHUB_MCP_REFERENCE_IMPLEMENTATION_v1.0.md`: encontrado na mesma branch, SHA `11e397ad8162173145ef744d618750cbf597e633`.
- `docs/MOSAIC_CLAUDE_PLUGIN_COMPATIBILITY_RULE_v1.0.md`: encontrado em `main`, SHA `f8c75cf78443b6b28885822394c03afe4b79be41`.
- `docs/PHASE1_TOOL_HARDENING.md`: encontrado em `main`.
- `docs/MOSAIC_AGENT_PROFILES_AND_ARTIFACT_TOOLS_ROADMAP_v1.0.md`: encontrado em `main`.
- `docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md`: encontrado em `main`.
- `ARQUITETURA.txt` e `Mosaic_MVP_Implementation_Contract.md`: não estão disponíveis na raiz das branches verificadas do repositório; foram fornecidos como arquivos no contexto de trabalho, então devem ser consultados a partir desses anexos ao validar contratos.
- A validação remota da referência atual do plugin oficial GitHub encontrou `.mcp.json` com um servidor HTTP em `https://api.githubcopilot.com/mcp/` e header `Authorization: Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}`; o manifesto de plugin define nome `github`, descrição e autoria GitHub. Essa configuração é específica do plugin e será consumida como dado, nunca executada como script.

## Arquitetura encontrada

- `backend/app/tools/base.py`: abstração `Tool`, validação de argumentos baseada em um subconjunto de JSON Schema e política via `permission_policy`/`policy_for`.
- `backend/app/tools/registry.py`: registro síncrono singleton; rejeita nomes duplicados.
- `backend/app/tools/__init__.py`: registra ferramentas nativas ao importar o pacote.
- `backend/app/services/tools.py`: ponto central para validação de política, aprovação, execução, persistência de ToolResult e eventos vinculados à Task.
- `backend/app/services/agent_decision.py`: entrega somente ferramentas registradas ao provider e valida decisões do modelo.
- `backend/app/api/tasks.py`: Tasks são persistidas e executadas via worker do Core; há eventos e estado de aprovação para ToolCall.
- `backend/app/services/agent_library.py`: perfis e Skills já persistem em `Project.state`; `/agent @skill` gera snapshot com hashes e as Skills entram como orientação não confiável, sem permissões.
- `backend/app/main.py`: routers explicitamente registrados; a integração de API precisará ser adicionada ao padrão existente.
- Não foi identificado arquivo `backend/requirements.txt` com SDK MCP; o arquivo atual lista FastAPI/pytest e bibliotecas de artefatos. A introdução de dependência deve ser mínima e versionada.
- Não existe `backend/app/api/tools.py` na referência consultada; ToolCalls são geridas por outros módulos e o fluxo real fica em `services/tools.py`.

## Riscos e decisões

1. O registro global é estático na inicialização. Para descoberta dinâmica de ferramentas, o adaptador deve resolver servidor/ferramenta por namespace e atualizar catálogo sob controle; não registrar cegamente qualquer nome entregue por servidor.
2. A execução de ferramentas é síncrona; usar o cliente MCP síncrono compatível com a pilha atual ou encapsular cuidadosamente a chamada, sem introduzir um novo executor de Tasks.
3. O atual verificador de schema aceita tipos/limites básicos. A camada MCP precisa recusar schemas incompatíveis ou validar um subconjunto explicitamente documentado, antes de qualquer chamada.
4. A configuração de endpoint deve validar HTTPS para hosts remotos, bloquear SSRF/hosts locais por padrão, não executar comandos do pacote, nunca persistir tokens em texto claro e não enviar segredo ao modelo.
5. Escritas devem permanecer no caminho normal ToolCall -> política -> aprovação -> execução; o status de aprovação não pode ser bypassado pelo adaptador.
6. O plugin atual usa transporte HTTP remoto e token em variável de ambiente de referência; nenhuma credencial foi fornecida para testar autenticação real.
7. Skills existentes não concedem acesso. A integração MCP deve integrar-se ao catálogo de ferramentas e ao snapshot atual de agente/Skill.

## Plano por incrementos

### Fase 1 (este PR)
- Adicionar resolvedor/parser seguro para `.claude-plugin/plugin.json` e `.mcp.json` (JSON estático, sem interpolação/execução automática).
- Definir metadados neutros de conexão e ferramentas.
- Adicionar cliente HTTP MCP com negociação, `tools/list`, `tools/call`, limites, timeout e redaction sem guardar credenciais.
- Criar adaptador `Tool` que passa pelo registro e pela política do Core.
- Adicionar testes unitários com servidor HTTP fake para handshake, descoberta, chamada, auth-error, timeout, schema inválido e limite de resposta.
- Não declarar teste real GitHub concluído sem token válido e chamada real ao endpoint oficial.

### Fases seguintes
- Persistir configuração/estado de conexão usando mecanismo existente adequado, com segredo fora do SQLite.
- API e interface para configurar/conectar/listar ferramentas habilitadas.
- Aplicar allowlist por tarefa e snapshots de ferramentas para evitar tool catalog obsoleto.
- E2E real de leitura; depois política de escrita, branch, checkout/edição controlada e PR com aprovações separadas.
- Documentar componentes de plugin que não são suportados (hooks, scripts, comandos, LSP); marketplace fora do escopo.

## Critérios para este incremento
- Parsing valida e rejeita manifesto/configuração inválidos.
- Cliente fala com endpoint MCP em HTTP e interpreta erro sem expor Authorization.
- Adapter chama ferramenta apenas se connection e tool estiverem habilitadas.
- Invocação passa por Tool Registry e aprovação do Core.
- Testes unitários determinísticos executam sem depender de tokens externos.
