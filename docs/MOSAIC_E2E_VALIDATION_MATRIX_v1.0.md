# Mosaic — Matriz de validação E2E v1.0

**Status:** matriz executável em expansão; cobertura automatizada parcial, não certificação de universalidade.  
**Regra:** um cenário só conta como aprovado quando o pedido passa pelo fluxo persistido, a política é aplicada, o resultado é reaberto/verificado e o estado final é consultável. Um teste unitário de ferramenta não substitui o cenário completo.

## Cenários e evidências

| Cenário | Evidência automatizada atual | Estado |
|---|---|---|
| Saúde da API e inicialização | `backend/tests/test_health.py` | Coberto por teste existente |
| Task via HTTP → aprovação → PDF → Artifact → eventos consultáveis; rejeição e cancelamento HTTP sem escrita | `backend/tests/test_harness_e2e.py` | Sucesso, rejeição e cancelamento HTTP adicionados; aguarda CI |
| Criação/reabertura de Markdown, PDF, DOCX, XLSX e PPTX | `backend/tests/test_artifact_tool.py` | Coberto no branch de artefatos; verificar cadeia de PR |
| Evidência invalidada após alteração do arquivo | `backend/tests/test_artifact_tool.py` | Coberto no branch de artefatos |
| Três Tasks dependentes, perfis e integração sequencial | `backend/tests/test_task_coordinator.py` | Coberto no branch do coordenador; verificar cadeia de PR |
| Busca web e clima: proveniência, timeout/erro do provider | `backend/tests/test_web_weather_tools.py` | Coberto no branch de ferramentas; fixtures HTTP, não smoke real |
| Contexto isolado entre conversas | `backend/tests/test_context_isolation.py` | Teste existente |
| Replay de eventos e paginação/cursor | `backend/tests/test_task_events.py` | Testes existentes; reinício real de processo ainda pendente |
| Rejeição de aprovação | `backend/tests/test_action.py`, `backend/tests/test_tools.py` | Cobertura existente a revisar no fluxo HTTP completo |
| Cancelamento durante execução e aprovação pendente | `backend/tests/test_agent_controls.py`, `backend/tests/test_task_events.py` | Cobertura de componentes; matriz de crash/restart pendente |
| Pesquisa → relatório com referências e URLs reabertas | Não há prova E2E suficiente nesta matriz | Pendente |
| Construção de sistema web completo (arquitetura, API, UI, testes e QA) | Não há prova E2E suficiente nesta matriz | Pendente |
| Reconciliação no startup de Tasks órfãs, ToolCalls/Actions em execução e preservação de aprovação pendente | `backend/tests/test_recovery.py` | Coberto por teste determinístico; crash real de processo ainda pendente |
| E2E visual claro/escuro em navegador real | Build frontend apenas | Pendente; build não comprova contraste nem interação visual |

## Portas de aceite

1. Backend suite completa e build frontend verdes na mesma cadeia de commits.
2. Nenhuma aprovação implícita; rejeição e cancelamento mantêm estados terminais corretos.
3. Cada artefato final tem caminho dentro do workspace, hash, registro persistido e verificação após reabertura.
4. Eventos podem ser consultados depois da conclusão; falhas não são reportadas como sucesso. A reconciliação de estado no startup tem teste determinístico, mas ainda não simula crash real entre processos.
5. Resultados de pesquisa e clima preservam fonte/horário/limitações; testes com fixtures não são descritos como validação de rede real.
6. Reinício do processo, sistema web completo e revisão visual real continuam explicitamente pendentes até testes dedicados serem executados.

## Limites conhecidos

- CI executa testes backend e build frontend; não inicializa Ollama nem valida provedores externos em rede real.
- A suíte não equivale a benchmark de modelos nem prova desempenho universal.
- Testes E2E usam respostas determinísticas para isolar o Core; a validação com o modelo local escolhido é uma etapa distinta.
- Não habilitar execução paralela nesta fase. O coordenador permanece sequencial.
