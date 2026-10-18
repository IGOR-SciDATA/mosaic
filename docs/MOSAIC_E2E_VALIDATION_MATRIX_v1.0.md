# Mosaic — Matriz de validação E2E v1.0

**Status:** CI verde no commit integrado `331f3a8b713031fc5b042b4e9a009bc921f8f97b`; cobertura automatizada parcial, não certificação de universalidade.  
**Evidência de integração:** [GitHub Actions #39113375125](https://github.com/IGOR-SciDATA/mosaic/actions/runs/39113375125) — 226 testes backend aprovados, 1 aviso de depreciação e build frontend aprovado (18/10/2026).
**Regra:** um cenário só conta como aprovado quando o pedido passa pelo fluxo persistido, a política é aplicada, o resultado é reaberto/verificado e o estado final é consultável. Um teste unitário de ferramenta não substitui o cenário completo.

## Cenários e evidências

| Cenário | Evidência automatizada atual | Estado |
|---|---|---|
| Saúde da API e inicialização | `backend/tests/test_health.py` | Coberto por teste existente |
| Task via HTTP → aprovação → PDF → Artifact → eventos consultáveis; rejeição e cancelamento HTTP sem escrita | `backend/tests/test_harness_e2e.py` | **Testado** no CI verde #39113375125; worker determinístico, não provider real |
| Criação/reabertura de Markdown, PDF, DOCX, XLSX e PPTX | `backend/tests/test_artifact_tool.py` | **Testado** na cadeia integrada; reabertura e validação por formato cobertas por testes |
| Evidência invalidada após alteração do arquivo | `backend/tests/test_artifact_tool.py` | **Testado** na cadeia integrada |
| Três Tasks dependentes, perfis e integração sequencial | `backend/tests/test_task_coordinator.py` | **Testado** na cadeia integrada; coordenação sequencial, sem paralelismo |
| Provider explícito por `Model.provider`, sem fallback silencioso | `backend/tests/test_provider_factory.py`, `backend/tests/test_agent_harness_integration.py` | **Testado** com provider simulado; somente Ollama está registrado | 
| Dependências e proveniência persistidas no plano da Task | `backend/tests/test_agent.py::test_markdown_summary_flow_reads_source_creates_and_reopens_verified_artifact` | **Testado**: hashes, IDs de ToolCall/ToolResult e evidência do artefato |
| Busca web e clima: proveniência, timeout/erro do provider | `backend/tests/test_web_weather_tools.py` | **Testado** com fixtures HTTP; smoke de rede real permanece pendente |
| Contexto isolado entre conversas | `backend/tests/test_context_isolation.py` | Teste existente |
| Replay de eventos e paginação/cursor | `backend/tests/test_task_events.py` | Testes existentes; reinício real de processo ainda pendente |
| Rejeição de aprovação | `backend/tests/test_action.py`, `backend/tests/test_tools.py`, `backend/tests/test_harness_e2e.py` | **Testado** em componentes e fluxo HTTP de rejeição |
| Cancelamento durante execução e aprovação pendente | `backend/tests/test_agent_controls.py`, `backend/tests/test_task_events.py` | Cobertura de componentes; matriz de crash/restart pendente |
| Pesquisa → relatório Markdown: search → web_fetch → citação URL → artefato reaberto e verificado | `backend/tests/test_agent.py::test_web_research_report_fetches_source_and_persists_cited_url` | **Testado** no CI com fixtures determinísticas; rede pública real permanece pendente |
| Construção de sistema web completo (arquitetura, API, UI, testes e QA) | Não há prova E2E suficiente nesta matriz | Pendente |
| Reconciliação no startup de Tasks órfãs, ToolCalls/Actions em execução e preservação de aprovação pendente | `backend/tests/test_recovery.py` | **Testado** deterministicamente; crash real de processo ainda pendente |
| E2E visual claro/escuro em navegador real | Build frontend no CI #39113375125 | **Pendente**; build não comprova contraste nem interação visual |
| Avaliação de acesso a modelos por interfaces web | `docs/MOSAIC_WEB_MODEL_ACCESS_EVALUATION_v1.0.md` | **Testado documentalmente**; automação de sessões de consumo não aprovada nem implementada |

## Portas de aceite

1. **Aprovado no CI no commit atual desta validação:** `233 passed, 1 warning` e build frontend aprovado no [GitHub Actions #39118831291](https://github.com/IGOR-SciDATA/mosaic/actions/runs/39118831291), commit `0914d86ec2093ab005ab99cc6d02b193feff3e7a`.
2. Nenhuma aprovação implícita; rejeição e cancelamento mantêm estados terminais corretos.
3. Cada artefato final tem caminho dentro do workspace, hash, registro persistido e verificação após reabertura.
4. Eventos podem ser consultados depois da conclusão; falhas não são reportadas como sucesso. A reconciliação de estado no startup tem teste determinístico, mas ainda não simula crash real entre processos.
5. Resultados de pesquisa e clima preservam fonte/horário/limitações; testes com fixtures não são descritos como validação de rede real.
6. Reinício real do processo, Ollama real, pesquisa em rede pública real, sistema web completo e revisão visual/acessibilidade em navegador continuam explicitamente pendentes até testes dedicados serem executados.

## Limites conhecidos

- CI executa testes backend e build frontend; não inicializa Ollama nem valida provedores externos em rede real.
- A suíte não equivale a benchmark de modelos nem prova desempenho universal.
- Testes E2E usam respostas determinísticas para isolar o Core; a validação com o modelo local escolhido é uma etapa distinta.
- Não habilitar execução paralela nesta fase. O coordenador permanece sequencial.
