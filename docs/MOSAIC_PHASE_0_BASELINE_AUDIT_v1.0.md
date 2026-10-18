# MOSAIC — Relatório de Auditoria do Baseline (Fase 0)

**Versão:** 1.0  
**Data:** 2026-10-18  
**Escopo:** inspeção estática de `main`, documentação versionada e evidências de testes/CI acessíveis pelo GitHub  
**Commit de referência:** `29f6af8e6ed1af9cb0a0160889c4d7ea56bd6912`  
**PR de documentação:** [#56 — README e guia](https://github.com/IGOR-SciDATA/mosaic/pull/56)  
**Resultado do snapshot original:** baseline estático produzido no commit indicado abaixo. Veja a atualização dinâmica posterior no início deste relatório; ela supersede as conclusões históricas sobre execução de testes e canonização do contrato.

---

> **Atualização dinâmica — 2026-10-18:** o contrato MVP está versionado em seu caminho canônico e a decisão de schema foi registrada na seção 6 do Plano de Implementação. A branch `codex/phase0-full-validation-ci` adicionou criação idempotente das tabelas `artifacts` e `settings`, preservando `task_events` e `_mosaic_meta`, com testes de schema e reinitialização. O GitHub Actions executou a suíte backend completa no commit de código `4dac3ad1c7cb7041c78f5293ff1274c207cc28d9`: **197 passed, 1 warning**; o job de build frontend também passou. Execução: [workflow run 39107873440](https://github.com/IGOR-SciDATA/mosaic/actions/runs/39107873440).
>
> Essa evidência corresponde à branch de validação, ainda não integrada à `main`. Não houve smoke test com Ollama/provider real, validação E2E real nem execução local nesta sessão, pois o clone falhou por DNS. A regressão Markdown mais completa está na [PR #63](https://github.com/IGOR-SciDATA/mosaic/pull/63) e ainda precisa passar no CI. As seções abaixo registram a auditoria estática histórica do commit `29f6af8`; as afirmações antigas de contrato ausente e schema ainda sem decisão não descrevem mais a branch de validação atual.

---

## 1. Resumo executivo

O repositório contém mais do que um chat básico: há uma aplicação React/Vite, API FastAPI, persistência SQLite, conversas/projetos/memórias/modelos, tarefas, ações, chamadas e resultados de ferramentas, eventos de tarefa e um ciclo de Agent com ferramentas registradas. Também existem testes unitários/de serviço para partes importantes do ciclo.

Entretanto, a documentação não está pronta para ser entregue ao implementador como uma única ordem sem reconciliação. Foram identificados bloqueios documentais e gaps de validação que podem induzir implementação divergente:

1. O **MVP Implementation Contract v1.0** é referenciado pelo Harness, RAGNES e UX, mas não está versionado em `main` no caminho citado. O arquivo foi disponibilizado como anexo de trabalho, mas isso não é uma fonte versionada no repositório.
2. O schema SQLite atual não cria todas as entidades listadas no contrato MVP: `artifacts` e `settings` não aparecem no bootstrap inspecionado; há uma tabela adicional `task_events` e metadados internos `_mosaic_meta`. Isso exige decisão explícita, não alteração automática.
3. O Roadmap Mestre ainda descreve Fase 0 como próximo passo e o guia de desenvolvimento contém uma sequência própria que diverge do roadmap mestre. O código já inclui componentes de tarefas, ferramentas, eventos e fluxo de Agent; não se deve presumir que as fases foram aprovadas nem recomeçar sua implementação sem reconciliar o estado.
4. Foram encontrados testes relevantes, mas a auditoria não executou pytest, build do frontend nem smoke test com Ollama. A busca de execuções de workflow para o commit de referência não retornou execuções e os caminhos comuns de workflow `.github/workflows/tests.yml` e `.github/workflows/ci.yml` não existem.
5. A existência de APIs, eventos e componentes frontend não prova, isoladamente, o fluxo completo de execução, aprovação, reconexão, retomada após reinício e conclusão validada.

**Decisão recomendada:** não enviar ainda uma ordem ampla para implementar todas as fases. Primeiro tornar os contratos canônicos e coerentes; depois executar a validação dinâmica mínima da Fase 0 e autorizar apenas o próximo incremento definido pelo MASTER.

---

## 2. Método e limites da auditoria

Foram inspecionados arquivos versionados diretamente em `main`, incluindo:

- `backend/app/main.py`
- `backend/app/db/database.py`
- `backend/app/services/agent.py`
- `backend/app/services/tools.py`
- `backend/app/tools/builtin.py`
- `backend/app/api/tasks.py`
- `backend/app/api/tool_calls.py`
- `backend/tests/test_agent.py`
- `backend/tests/test_tools.py`
- `backend/tests/test_action.py`
- `backend/tests/test_task.py`
- `backend/tests/test_task_events.py`
- `frontend/src/App.jsx`
- `frontend/package.json`
- contratos Harness v1.2, RAGNES v1.0, UX v1.0, Roadmap Mestre e Guia de Desenvolvimento.

A auditoria foi **estática e remota**. Não foi feito checkout executável do repositório nesta sessão. Portanto, nenhuma afirmação de teste aprovado é feita. A inspeção de código mostra a implementação declarada no commit de referência, não comprova seu comportamento em runtime.

---

## 3. Inventário observado

### 3.1 Backend e API

`backend/app/main.py` registra rotas de conversas, mensagens, projetos, memórias, modelos, tarefas, chamadas de ferramentas, ações e chat, além de `/health`. A API é FastAPI e inicializa o banco no lifespan.

A API de tarefas contém criação/listagem de Tasks, endpoints de eventos e stream SSE, além de lógica de início e decisão/execução de ferramentas. A API de ToolCall expõe chamadas e seus resultados persistidos.

**Conclusão:** existe uma superfície de API significativa; a cobertura e integração dos endpoints precisam ser demonstradas por testes executados e jornadas ponta a ponta.

### 3.2 Persistência SQLite

O bootstrap inspecionado cria:

- `_mosaic_meta`
- `models`
- `projects`
- `memories`
- `conversations`
- `messages`
- `tasks`
- `actions`
- `tool_calls`
- `tool_results`
- `task_events`

O schema inclui estados de Task, Action e ToolCall, chaves estrangeiras e índices. Há compatibilidade incremental explícita para adicionar colunas `configuration` e `enabled` em `models`.

**Divergência a resolver:** o contrato MVP lista também `Artifact` e `Setting` como entidades persistentes, mas não há tabelas `artifacts` ou `settings` no bootstrap inspecionado. A representação de artefatos em arquivos/workspace pode atender parte do objetivo, mas isso não resolve automaticamente a divergência contratual. Não criar essas tabelas sem uma decisão documentada sobre o contrato/schema.

### 3.3 Agent e ferramentas

A inspeção de `backend/app/services/agent.py` mostra um ciclo de Agent com callback de decisão, contexto de objetivo, limite de iteração, observação de ferramentas e verificação de artefato. A API de tarefas usa `create_provider_decider`, conectando a decisão do Agent ao provider configurado na conversa.

O registro de ferramentas observado nos testes inclui:

- `filesystem`
- `terminal`
- `search`
- `web_fetch`
- `calculator`
- `weather`

Os testes de ferramenta incluem verificação de argumentos, chamada não executável antes de aprovação, persistência de resultados, traversal e symlink escape no filesystem, allowlist/limites de terminal e validação de URLs públicas. Isso é evidência de **cobertura de teste escrita**, não de aprovação, pois os testes não foram executados nesta auditoria.

### 3.4 Eventos e observabilidade

O schema contém `task_events`; os testes inspecionados verificam persistência ordenada, redaction de campos sensíveis, cursor e limite de eventos. A API expõe listagem e stream de eventos com suporte a cursor/Last-Event-ID.

**Ainda não comprovado:** a experiência completa de reconexão no frontend, a retomada após reinício e a consistência entre evento, estado persistido e resultado final em todos os caminhos de execução.

### 3.5 Frontend

O frontend usa React 19 e Vite 7. O `package.json` define `dev`, `build` e `preview`; não declara script de teste automatizado. A aplicação `App.jsx` tem uma implementação extensa e inclui elementos para tarefas e aprovação, mas não foi possível validar visualmente ou executar as jornadas nesta auditoria.

### 3.6 Testes e CI

Arquivos inspecionados incluem:

- `backend/tests/test_agent.py`
- `backend/tests/test_tools.py`
- `backend/tests/test_action.py`
- `backend/tests/test_task.py`
- `backend/tests/test_task_events.py`

O caminho `backend/tests/test_harness.py` não foi encontrado. Os arquivos de workflow `.github/workflows/tests.yml` e `.github/workflows/ci.yml` também não foram encontrados; a consulta de workflow runs para o commit de referência retornou uma lista vazia.

Isso não prova que não existam outras formas de CI ou mais testes em outros caminhos, mas significa que **não há evidência de execução de CI disponível nesta auditoria**.

---

## 4. Matriz de capacidade

| Capacidade | Evidência estática | Situação após Fase 0 |
|---|---|---|
| API FastAPI e rotas centrais | `app/main.py` e módulos de API | Existe no código; runtime não verificado |
| Persistência SQLite de Core/Tasks/Tools/Events | `database.py` | Existe; schema diverge do contrato MVP |
| Provider associado à conversa | API de Tasks + `create_provider_decider` | Caminho de integração existe; E2E não verificado |
| Ciclo de Agent | `services/agent.py` e testes | Implementação existe; testes não executados |
| Ferramentas e política de aprovação | registry, services, builtins e testes | Implementação/testes existem; segurança precisa de validação dinâmica |
| Eventos e SSE | `task_events`, API e testes | Implementação existe; reconexão/retomada E2E não verificada |
| Perfis de Agent por conversa | Não comprovado como configuração completa por conversa | Gap planejado |
| Snapshot imutável de instruções/Skills por Task | Não comprovado na implementação inspecionada | Gap planejado |
| Coordenador de subtarefas com dependências reais | Plano de Task existe; grafo coordenado não comprovado | Gap planejado |
| RAGNES completo | Context Manager e trabalho incremental existentes | Implementar por estágios e medir; não presumir K0–K5 completos |
| Artefatos persistidos como entidade e validadores por formato | Tabela `artifacts` ausente; escrita textual de workspace existe | Contrato/schema a reconciliar; PDF/XLSX/PPTX não comprovados |
| Build/testes executados | Sem resultados de execução nesta auditoria | Pendente |
| CI contínuo | Workflow run vazio e caminhos usuais ausentes | Pendente de confirmar/configurar |

---

## 5. Bloqueios documentais

### B1 — Contrato MVP sem caminho canônico no repositório (bloqueador)

Harness, RAGNES e UX citam `Mosaic_MVP_Implementation_Contract.md`, mas esse caminho não existe em `main`. O documento anexado ao contexto de trabalho não substitui uma versão versionada e acessível ao implementador.

**Ação necessária:** adicionar o contrato aprovado ao repositório no caminho canônico, corrigir todas as referências e registrar explicitamente qualquer emenda posterior. Não alterar schema enquanto esse ponto não estiver resolvido.

### B2 — Divergência entre entidades do contrato e schema (bloqueador para mudanças de banco)

O contrato lista `Artifact` e `Setting`; o bootstrap atual não cria essas tabelas. `task_events` e `_mosaic_meta` existem no código, embora não estejam na lista inicial de entidades.

**Ação necessária:** o MASTER decide se Artifact é representado por metadados + filesystem ou por tabela própria, qual o papel de Setting e se task_events é uma emenda oficial. O implementador não deve escolher silenciosamente.

### B3 — Roadmap e guia possuem sequências concorrentes (bloqueador de coordenação)

O Roadmap Mestre determina a ordem integrada e o Guia de Desenvolvimento possui uma sequência de implementação própria, com perfis/formatos de artefato antes de fases de integração e UX. Isso pode induzir o dev a trabalhar fora da fase autorizada.

**Ação necessária:** uma única sequência normativa: Roadmap Mestre. O guia deve explicar como executar cada fase, não criar outra ordem.

### B4 — Status dos contratos não está normalizado

Harness v1.2 é o contrato oficial do Harness; o Roadmap Mestre organiza a sequência; RAGNES e UX descrevem contratos-alvo com implementação faseada. Os metadados e as referências devem dizer claramente o que é decisão aprovada, alvo arquitetural e implementação comprovada.

**Ação necessária:** manter status distintos e evitar tratar todos os documentos como se cada capacidade já estivesse implementada.

---

## 6. Ordem recomendada para o implementador

Antes de autorizar a próxima implementação ampla:

1. **Canonizar o MVP contract** em `docs/` e corrigir referências quebradas.
2. **Resolver por decisão do MASTER** a divergência `Artifact`/`Setting`/`task_events`; não migrar schema por inferência.
3. **Reconciliar Roadmap Mestre e Guia**, usando o roadmap como única ordem normativa e identificando os componentes que já existem.
4. Executar no checkout do implementador:
   - `python -m pytest` na pasta `backend`;
   - `npm run build` na pasta `frontend`;
   - smoke test do backend e do provider local quando Ollama estiver disponível;
   - testes integrados para início de Task, decisão do provider, aprovação/rejeição, execução de ferramenta, persistência de ToolResult, evento, conclusão, reconexão e retomada após reinício.
5. Registrar comandos, ambiente, commit, resultados, falhas e testes não executados. Não declarar a Fase 0 aprovada enquanto esses resultados estiverem ausentes.

Depois disso, o MASTER deve autorizar **um único próximo incremento**, com critérios de aceite claros. Não iniciar simultaneamente perfis, todas as ferramentas de artefato, RAG avançado e paralelismo.

---

## 7. Parecer de prontidão

**A documentação ainda não está pronta para ser enviada como ordem irrestrita de implementação.** A visão e os princípios são coerentes; o bloqueio está na reconciliação entre contratos, schema e sequência operacional, além da ausência de evidência de execução dos testes.

É possível enviar ao dev uma tarefa limitada de preparação/validação com estes critérios:

- não alterar schema nem criar entidades;
- canonizar o contrato MVP e suas referências;
- reconciliar Roadmap Mestre e Guia;
- executar e registrar a suíte/build/smoke test;
- devolver o relatório de divergências para decisão do MASTER antes de começar a próxima fase funcional.

A Fase 0 estará **dinamicamente validada** somente após as verificações executáveis serem realizadas e documentadas.


---

## Adendo — fluxo funcional reportado após a auditoria estática (2026-10-18)

Após a redação desta auditoria, o usuário confirmou a conclusão manual de uma tarefa na versão atual: o agente leu um arquivo `.md`, resumiu seu conteúdo e criou um novo arquivo `.md` com o resumo. O fluxo foi acompanhado até a conclusão e o usuário confirmou o artefato de saída.

Esta informação complementa, mas não invalida, o escopo original de auditoria estática. A auditoria inicial não executou testes automatizados/build/E2E. O fluxo acima é **evidência manual reportada pelo usuário**, e não um teste executado por esta auditoria. Deve ser reproduzido e convertido em teste de regressão pelo implementador.
