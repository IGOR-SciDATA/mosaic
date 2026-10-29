# Mosaic — auditoria integrada HIE + frontend

**Data:** 2026-10-29  
**Branch de trabalho:** `feat/hie-frontend-integrated`  
**PR:** #121 (Draft)  
**Regra:** este documento registra evidência observada; descrições de PR não são prova de runtime.

## Escopo da auditoria

Consultados o prompt integrado e o contrato HIE na branch documental `docs/hie-frontend-implementation-phase`, os requisitos de interface anexados, as descrições de PRs #101–#116 e #119, os comentários e reviews da #119, os arquivos de `main`, os arquivos da branch experimental e os resultados de GitHub Actions disponíveis.

A #119 estava com CI falho no commit `085169ed40abaf9e8d6e8ee3d1a51e130ed3c786`: frontend build passou; backend teve 315 testes aprovados e uma falha em `test_conversation_hie_is_disabled_by_default_and_persisted`. Run: https://github.com/IGOR-SciDATA/mosaic/actions/runs/40918780150. Esse resultado é histórico daquele commit.

## Matriz PR → código → evidência → lacuna

| PR | Escopo observado na descrição | Evidência/estado da integração | Lacuna/risco |
|---|---|---|---|
| #101 | Proposta arquitetural | Documentação; sem runtime declarado | Validar que as decisões continuam alinhadas ao Core atual. |
| #102 | Validador declarativo de candidato | A descrição define schema allowlisted, hash e snapshot | Conferir testes e integração na cadeia final; não executar candidato como código. |
| #103 | Orquestração sequencial | Serviço HIE em branch incremental | Comprovar limites no ponto real de execução e lifecycle do Core. |
| #104 | Fixture descartável | Utilitário de workspace isolado descrito | Conferir symlink, traversal, limites durante cópia e cleanup. |
| #105 | Limites de fixture e budget | Endurecimento incremental descrito | Budget de provider ainda não é provado pelo objeto de configuração sozinho. |
| #106 | Adapter de fixtures | Cópias independentes de fixture descritas | Não equivale a provider real nem a sandbox de sistema operacional. |
| #107 | Comparação integrada | Teste com doubles descrito | Não prova E2E com provider real. |
| #108 | Semântica de falha/comparação | Testes de empate, regressão e falha descritos | Conferir estado persistido e ausência de promoção em falha. |
| #109 | Falha de event logging | Falha fechada no evento inicial descrita | Validar os pontos de persistência do lifecycle integrado. |
| #110 | Hash/identidade do registro | Registro selado descrito | Hash não substitui autenticação, autorização ou transação. |
| #111 | Evidência como Core Artifact | Persistência via Artifact descrita | Validar consistência arquivo/metadata e budgets agregados. |
| #112 | Contrato de conclusão HIE | Documentação | Reconciliar com código e capacidades efetivamente expostas. |
| #113 | Segurança de evidências | Symlinks, temporários e budget agregado descritos | Confirmar que o código final contém essas proteções. |
| #114 | Enforcement real de budget | Integração em fronteiras de provider/tool descrita | Não presumir que esse branch esteja integrado à #119 ou à main. |
| #115 | Fixture com provider real | Caminho mínimo descrito | Testes com doubles não são smoke test de provider real. |
| #116 | Mapa visual UML | Documentação de fluxos e dependências | O mapa precisa corresponder ao código final, não ao alvo arquitetural. |
| #119 | Opt-in, experimento persistido, UI e lifecycle | Código presente na branch experimental; não presente integralmente na main consultada | CI histórico falhou; budget, recovery, transações, frontend e dependências precisam de validação atual. |

## Componentes canônicos encontrados na main

- `ModelProvider` e registro explícito de providers.
- Repositórios de conversas, Tasks, eventos e projetos.
- Perfis de agente armazenados em `Project.state`.
- Recuperação de Tasks interrompidas no startup.
- API de conversas que permite `project_id` opcional.
- React/Vite no frontend.

A rota `backend/app/api/hie.py` não foi encontrada na `main` consultada; existe na branch experimental. Portanto, o código da #119 não foi tratado como já integrado à main.

## Matriz requisito → implementação → teste

| Requisito | Implementação na branch integrada | Teste previsto/alterado | Estado nesta auditoria |
|---|---|---|---|
| Capabilities consistentes | `backend/app/api/hie.py` | `backend/tests/test_hie_api.py` | Implementado; aguarda CI do head atual. |
| Budget de entrada antes da chamada | `backend/app/services/hie_experiments.py` | Teste que baixa limite e verifica zero chamadas | Implementado; aguarda CI do head atual. |
| Output cap de provider e evidência | Mesmo serviço; tokens via Ollama/Remote Inference | Saída excessiva rejeitada, sem truncamento pós-geração | CI no commit 4929c34: backend passou. |
| Timeout | `request_timeout_seconds` nos adapters existentes | Configuração passada ao provider | Limitação: timeout de rede não garante cancelamento rígido de wall-clock. |
| Recovery queued/running | `recover_interrupted_experiments` no startup existente | `backend/tests/test_hie_recovery.py` | Implementado sem replay; aguarda CI do head atual. |
| Aprovação/promoção/rollback | `hie_lifecycle.py` com transação SQLite e hash/versão | Concorrência, edição posterior e falha de auditoria | Implementado; aguarda CI do head atual. |
| Eventos de lifecycle | Reuso de `create_task_event(connection=...)` | Falha de evento durante promoção | Implementado; aguarda CI do head atual. |
| Conversa sem projeto | API de conversa existente e navegação do frontend | Teste backend de Task avulsa e build no commit 4929c34 | Backend e build passaram; teste de interface dedicado não existe. |
| Seletor de modelo | API de conversas existente; bloqueado durante streaming | Build no commit 4929c34 | Build passou; comportamento em navegador não foi testado. |
| Espaço de trabalho separado | Sidebar + componentes existentes de Biblioteca/Arquivos | Build pendente no head atual | Parcial; CRUD continua restrito ao que APIs existentes suportam. |
| Inspetor de contexto | Eventos de Task reais pela API existente | Build pendente no head atual | Parcial; payload exato não é registrado. |
| Dependência vulnerável | Vite 7.3.7 no package e lockfile | Run 40932800057: npm ci auditou 67 pacotes, 0 vulnerabilidades; build passou | Corrigida e verificada no commit 4929c34. |

## Limitações intencionais e riscos remanescentes

1. Não foi criada infraestrutura paralela de Tasks, filas, eventos ou providers.
2. Experimentos interrompidos em `running` recebem resultado desconhecido e não são repetidos automaticamente.
3. O inspetor exibe eventos reais e informa quando o payload exato não está instrumentado; não infere conteúdo enviado, truncado ou omitido.
4. A comparação `candidate_better` representa melhor resultado apenas nas fixtures determinísticas configuradas, não superioridade geral do agente.
5. O timeout configurado nos adapters é um timeout de requisição/rede, não promessa de interrupção forçada de toda chamada síncrona.
6. Não há promoção automática; somente instruções declarativas do perfil de agente de projeto são promovíveis.
7. Nenhum teste é considerado aprovado apenas por ter sido adicionado; a conclusão depende do CI do head final.
8. A criação automática de Tasks a partir do chat comum permanece limitada aos contratos reais já existentes; nenhum endpoint novo foi inventado nesta fase.

## Referências de CI

- CI histórico com falha na #119: https://github.com/IGOR-SciDATA/mosaic/actions/runs/40918780150
- CI integrado no head `43bf048e73d24ca9a9bc384208f11256c94c162d`: https://github.com/IGOR-SciDATA/mosaic/actions/runs/40933111465
- Resultado observado: `frontend-build` passou; `backend-tests` passou com 331 testes aprovados e 1 aviso. O job frontend instalou Vite 7.3.7 e reportou 0 vulnerabilidades npm.
- O head atual foi validado; não houve alteração de runtime depois da execução.
