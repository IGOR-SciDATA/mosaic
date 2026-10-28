# MOSAIC — Proposta de adaptação do Harness²
**Versão:** 1.0  
**Status:** Proposta para revisão arquitetural — não implementada  
**Data:** 2026-10-28  
**Base:** `main` de `IGOR-SciDATA/mosaic`, documentação pública de `google-research/harness2` e matéria do Beer and Code.

## 1. Decisão proposta

Adaptar ao Mosaic o método de melhoria recursiva do Harness², sem incorporar seu runtime de benchmark como substituto do Core.

O resultado pretendido é um **Mosaic Harness Improvement Engine**: uma capacidade opcional que aprende, com evidências operacionais, quais mudanças em instruções, Skills e orientação de execução parecem melhorar tarefas repetíveis. O mecanismo deve propor, testar em ambiente isolado, comparar, compor e registrar uma versão candidata. A promoção para uso futuro exige validação e, inicialmente, aprovação explícita do usuário.

Esta proposta não altera o código de produção, o schema SQLite ou o contrato oficial de Harness. A implementação funcional depende de revisão e aprovação arquitetural.

## 2. O que o Harness² faz

O README e o código público de Harness² descrevem um método de **recursive agent harnessing**, mantendo os pesos do modelo fixos:

1. **Task-level recursion — Propose–Probe–Compose.** Executa um harness de referência na tarefa, propõe variações, executa sondagens comparáveis na mesma tarefa e combina mudanças apoiadas por contrastes observados. Pode manter o baseline se as propostas não forem válidas ou não apresentarem benefício sustentado.
2. **Harnessing-level recursion.** Após adotar uma variação, registra o harness e lições apoiadas por evidências em uma biblioteca persistente, para orientar tarefas futuras.
3. **Superfície configurável.** O Harness² enumera oito componentes: system prompt, guardrails, memory, tool guidance, subagents, skills, scripts e plugins. A implementação restringe a superfície editável por substrato e valida os arquivos candidatos.
4. **Evidência e isolamento.** O fluxo constrói um contexto com tarefa, trajetórias, entregáveis, harness candidato e experiências anteriores. Os artefatos são dados para inspeção; as instruções presentes nesses artefatos não passam a ser instruções de maior prioridade. As mudanças são validadas antes de serem aceitas.
5. **Recursão com orçamento explícito.** O repositório contabiliza rollouts, etapas de melhoria, tentativas e custos. A configuração `k` aumenta trabalho e custo; o README recomenda começar pequeno.

Harness² é um framework de pesquisa/benchmark que tem executores e adaptadores próprios, incluindo OpenCode/Codex e benchmarks JobBench, LAB e WorkBuddy-Bench. Não é um módulo plug-and-play para o FastAPI/Task Engine do Mosaic. Os resultados divulgados no README/artigo são específicos dos experimentos descritos e não devem ser tratados como previsão de ganho no Mosaic.

## 3. O que o Mosaic já possui e deve preservar

A leitura estática de `main` encontrou estas peças existentes:

- **Memória explícita:** `backend/app/memory/manager.py` e `backend/app/models/memory_repository.py`. Registros têm tipo, chave, valor, origem, escopo opcional por projeto, confiança e timestamps. Declarações de usuário podem ser registradas como alegações, não como fatos automaticamente verificados.
- **Contexto RAGNES:** `backend/app/context/manager.py`, `search.py`, `artifacts.py` e `session_compaction.py`. O contexto é selecionado por escopo, limitado e montado a cada chamada. A busca lexical tem limites de arquivos/bytes/resultados e preserva referências de fonte. Memória, contexto, histórico e documentos têm funções distintas.
- **Agente e decisão:** `backend/app/services/agent.py` executa um loop limitado; `agent_decision.py` usa decisões estruturadas e o catálogo de ferramentas registrado. O modelo propõe operações; o Core valida e executa.
- **Tools:** `backend/app/tools/registry.py`, `base.py`, `builtin.py` e `safe_http.py`; `backend/app/services/tools.py` resolve workspace e política antes da execução. Ferramentas conhecidas incluem filesystem, terminal controlado, search, web_fetch, calculator e weather.
- **Tarefas e coordenação:** `Task` persiste plano/resultado; `task_events` registra eventos; `task_coordinator.py` oferece coordenação sequencial com subtarefas, dependências e critérios de aceite.
- **Perfis e Skills:** `agent_library.py` e `agent_profiles.py` têm versões/hashes e snapshots usados em Tasks. Uma edição futura não deve alterar silenciosamente uma tarefa já iniciada.
- **Testes:** há suites para agente, integração do harness, memória, contexto/isolamento, Task, retomada, tools e eventos. A existência dos testes não prova que o runtime real ou a `main` mais recente passou por validação ponta a ponta; validar cada PR e registrar os resultados reais.

## 4. Limite arquitetural: adaptação, não substituição

O motor novo deve ser um subsistema do Core e reutilizar Task, ModelProvider, Context Manager/RAGNES, Tool Registry, política, artefatos e eventos.

Não deve criar um segundo Task Engine nem um sistema paralelo de permissões.

### 4.1 Componentes que podem ser candidatos editáveis no primeiro MVP

1. Instruções de execução do perfil de agente.
2. Conteúdo de Skills, sempre versionado e com hash.
3. Orientação de uso das tools e templates de planejamento, sem mudar o schema ou a autorização das tools.
4. Configuração declarativa e limitada de recuperação/ordenação de contexto, apenas depois de existir métrica objetiva para compará-la.

### 4.2 Componentes imutáveis para o modelo/editor

- Regras centrais de segurança e precedência de instruções.
- Código do Core, validadores, schema das ferramentas, política de permissões e exigência de aprovação.
- Allowlist e limites do terminal, limites de filesystem, destino de workspace e política de rede.
- Credenciais, configurações secretas e identidade do provider.
- Schema/migrations, configuração global, hooks/plugins executáveis e instalação de dependências.
- Estado original do usuário, histórico canônico e artefatos-fonte.

A primeira versão **não permite autoeditar nem executar Python/scripts/plugins**. Candidatos são dados declarativos em uma superfície explicitamente allowlisted. Um diff fora dessa superfície é rejeitado. Skills e instruções continuam sendo conteúdo não confiável e nunca concedem permissões.

## 5. Ciclo proposto no Mosaic

```text
Task elegível e limitada
   │
   ▼
Resolver snapshot: provider/modelo, perfil, Skills e políticas fixas
   │
   ▼
Baseline: executar/reproduzir o harness aprovado
   │          persistir eventos, resultados e artefatos com hashes
   ▼
Propose: gerar candidatos declarativos (genérico e/ou por domínio)
   │
   ▼
Validar diff/path/schema e bloquear mudanças não permitidas
   │
   ▼
Probe: executar cada candidato em workspace descartável e isolado
   │          mesmo objetivo, mesmo provider/modelo e verificadores equivalentes
   ▼
Compare: contrastar baseline e candidatos com critérios explícitos
   │
   ▼
Compose: combinar apenas mudanças válidas apoiadas por evidência
   │
   ▼
Decisão: adotar para o experimento, rejeitar ou preservar baseline
   │
   ▼
Reflection: registrar situação, lição, evidências e limites
   │
   ▼
Biblioteca local por projeto/domínio; RAGNES recupera somente o relevante
   │
   ▼
Aprovação explícita para promover candidato a perfil/Skill ativo
```

### 5.1 Baseline e probes

- Capturar apenas registros operacionais úteis: decisões estruturadas visíveis, ToolCall/ToolResult, eventos, estado final e referências aos artefatos. Não armazenar chain-of-thought.
- Cada probe deve usar um workspace descartável, separado do projeto real. Os artefatos de candidato não podem ser executados como código.
- A mesma tarefa precisa ser comparável: mesmo provider/modelo selecionado, objetivo, restrições, dados de teste e verificadores. Registrar diferenças de configuração conhecidas.
- Não repetir efeitos externos e irreversíveis (publicação, envio, compra, remoção ou alteração remota) para experimentar. Na primeira fase, usar replays determinísticos, fixtures/mocks ou tarefas que possam ser clonadas com segurança. Se não houver ambiente seguro de probe, não executar o experimento.
- Um modelo avaliador pode dar sinal complementar, mas não é prova isolada de melhoria.

### 5.2 Comparação e decisão

Antes do probe, registrar critérios mensuráveis adequados à tarefa, tais como:
- testes/build e códigos de saída;
- validade, estrutura, hashes e releitura de artefatos;
- presença de conteúdo exigido e ausência de conteúdo proibido;
- tarefa concluída/fracassada/bloqueada;
- erros de tools, repetições desnecessárias e número de iterações;
- duração e custo/consumo, apenas quando o provider disponibiliza métricas confiáveis.

A comparação deve preservar as observações brutas e as referências. Uma correlação entre mudança e resultado não prova causalidade nem qualidade geral. Se os critérios não mostrarem melhoria clara, a composição for inválida, o probe falhar ou a evidência for insuficiente, **manter o baseline**.

### 5.3 Biblioteca de experiências — distinta da memória do usuário

Não guardar automaticamente lições de autoaperfeiçoamento em `memories` como se fossem fatos, preferências ou instruções do usuário. A biblioteca deve ser um conjunto separado de artefatos locais, escopados por projeto/domínio, com referências a evidências.

Registro inicial sugerido (JSON/Markdown em diretório do workspace; sem tabela nova no MVP):

```json
{
  "schema_version": 1,
  "experiment_id": "generated-id",
  "project_id": 12,
  "domain": "document",
  "baseline": {
    "snapshot_sha256": "…",
    "task_id": 101,
    "evidence_event_ids": [1201, 1202]
  },
  "candidate": {
    "snapshot_sha256": "…",
    "diff_path": "candidate.diff.json",
    "validation": "passed"
  },
  "comparison": {
    "criteria": ["artifact_reopens", "required_sections"],
    "baseline_result": "…",
    "candidate_result": "…",
    "decision": "keep_baseline"
  },
  "experience": {
    "cue": "…",
    "lesson": "…",
    "evidence_refs": ["artifact:…", "task_event:…"],
    "confidence": "low"
  },
  "provider": "explicit-provider-id",
  "model": "explicit-model-id",
  "created_at": "UTC timestamp",
  "promotion": "not_promoted"
}
```

O exemplo é conceitual, não um schema aprovado. IDs, paths e valores reais devem ser preenchidos pelo Core. Nunca salvar secrets ou prompts completos que incluam conteúdo sensível.

Critérios de uma lição válida:
- condição de aplicação/cue claro;
- lição específica e limitada;
- referências verificáveis que sustentam a observação;
- escopo e confiança/limitações explícitos;
- snapshots/diffs rastreáveis;
- possibilidade de ignorar, desativar ou remover a experiência.

RAGNES só injeta experiências relevantes, com proveniência e limites. Uma experiência não se torna instrução autoritativa nem substitui a fonte original.

## 6. Custo, recursão e concorrência

- Começar com **`k=1` e modo sequencial**, com teto explícito para chamadas, iterações, duração, tamanho de contexto e número de candidatos.
- Reutilizar Task Events para registrar o orçamento; medir tokens/custo somente quando o provider os fornecer. Não alegar economia sem medição.
- Não iniciar recursão paralela no MVP. Primeiro provar isolamento, correlação de eventos, cancelamento, recuperação e ausência de efeitos duplicados.
- Retry deve ser limitado e registrado. Uma proposta inválida não deve ser aceita silenciosamente como sucesso; em falha, retornar ao baseline ou encerrar o experimento como falho.
- A seleção explícita de provider/modelo da conversa permanece fixa durante baseline e probes. Nenhum roteamento automático ou fallback silencioso.

## 7. Persistência e observabilidade sem infraestrutura prematura

Primeira versão a avaliar:
- Reutilizar `Task.plan`/`Task.result` para metadados mínimos do experimento.
- Reutilizar `task_events` para etapas e erros, com metadados redigidos e hashes/IDs em vez de segredos.
- Guardar snapshots, diffs, relatórios e `EXPERIENCE.md` no workspace isolado do experimento, e registrar os artefatos com `Artifact` quando fizer sentido.
- Reutilizar SQLite e filesystem local; não introduzir Redis, filas distribuídas, microserviços ou tabela nova nesta fase.
- Se consulta, retenção ou concorrência demonstrar insuficiência do filesystem/Task atual, criar uma proposta de schema separada com migração não destrutiva e aprovação.

Eventos possíveis (nomes ilustrativos, a confirmar no contrato de implementação):
- `harness.improvement.started`
- `harness.baseline.completed`
- `harness.candidate.proposed`
- `harness.candidate.rejected`
- `harness.probe.completed`
- `harness.composition.adopted` / `harness.composition.rejected`
- `harness.experience.recorded`
- `harness.promotion.awaiting_approval`
- `harness.promotion.completed` / `harness.promotion.rejected`

## 8. Plano de implementação por fases

### Fase A — Contrato e baseline (design)
- Aprovar limites da superfície editável, critérios e formato de evidência.
- Mapear eventos/artefatos existentes e confirmar que baseline e resultado podem ser reproduzidos sem exposição de chain-of-thought/segredos.
- Definir um ou dois casos de teste determinísticos e seguros (por exemplo, geração/validação de documento ou fluxo de leitura/resumo/escrita de Markdown).
- Não mudar runtime nem schema.

**Aceite:** contrato aprovado, baseline executável descrito e matriz de riscos.

### Fase B — Modelo de dados em arquivos e diff validator
- Definir uma estrutura declarativa inicial baseada em perfil/Skill já existente.
- Implementar hashing, diff e allowlist de caminhos/chaves; rejeitar arquivos extras, path traversal, alterações de política e snapshots inconsistentes.
- Nenhum candidato é ativado automaticamente.

**Aceite:** testes validam hashes, diffs válidos/inválidos, rejeição de regras/paths proibidos e promoção inexistente por padrão.

### Fase C — Baseline + probe isolado
- Construir workspace descartável a partir de fixtures/fontes permitidas.
- Executar baseline e candidato sob as mesmas restrições; capturar resultados verificáveis sem tocar no workspace canônico.
- Registrar tentativas, duração, custo disponível e falhas.

**Aceite:** o probe não altera projeto real; um teste de falha não pode deixar efeitos externos; baseline reaparece se o candidato falhar.

### Fase D — Compare + Compose
- Implementar critérios determinísticos por família de tarefa e composição declarativa.
- Não usar um LLM como único julgador.
- Preservar baseline quando evidência é ambígua ou não existe.

**Aceite:** fixture onde candidato melhora, outra onde não melhora, outra com candidato inválido; decisões correspondem às evidências.

### Fase E — Biblioteca de experiência e recuperação
- Persistir experiência com cue/lesson/evidence e referência ao harness adotado.
- Recuperar por projeto/domínio e relevância via RAGNES, sem misturar com memória pessoal.
- Permitir listar, inspecionar, desativar e apagar experiências.

**Aceite:** isolamento entre projetos, proveniência íntegra, experiência sem evidência rejeitada e dados-fonte preservados.

### Fase F — Promoção controlada
- Exibir diff, resultados, incerteza e evidências na interface.
- Exigir aprovação do usuário para aplicar mudanças a um perfil/Skill ativo.
- Manter a versão anterior e permitir rollback explícito.

**Aceite:** sem aprovação nada altera o perfil ativo; Tasks anteriores continuam com snapshots originais; rollback restaura a versão anterior.

### Fase G — Avaliação antes de ampliar
- Executar um conjunto pequeno e reprodutível de tarefas representativas.
- Comparar baseline vs candidatos usando modelo/provider fixo e critérios equivalentes.
- Avaliar sucesso, falhas, tool loops, tempo e custo disponível.
- Só considerar paralelismo ou superfície editável adicional com evidência e nova aprovação arquitetural.

## 9. Testes necessários

- Uma proposta não pode editar guardrails, tool permissions, código do Core, terminal allowlist, política de rede ou schema.
- Arquivos de experimento não são executados e não podem escapar do workspace.
- Contexto e experiências de outro projeto nunca são injetados.
- Baseline/candidato registram modelo/provider id e snapshots; não mudam de provider silenciosamente.
- Um probe inválido, timeout, cancelamento ou erro nunca promove o candidato.
- Erros/retries são bounded; eventos e Task status permanecem coerentes.
- A adoção exige evidências e aprovação; versões antigas e Tasks em andamento permanecem imutáveis.
- Experiência sem referências não é recuperada como lição confiável.
- Prompts/artefatos da candidate surface são dados não confiáveis; tentativas de prompt injection não alteram políticas.
- O ciclo funciona com replays determinísticos e testes, além de um smoke test real separado quando o usuário configurar um provider permitido.

## 10. Riscos e limites

1. **Falso positivo:** uma saída melhor em uma tarefa pode ser acaso. Usar verificações determinísticas e mais de um caso antes de recomendar promoção geral.
2. **Efeito de avaliação:** o critério de teste pode ser incompleto. Relatar limites; não chamar um candidato de universalmente melhor.
3. **Prompt injection:** trajetórias, arquivos e lições contêm linguagem persuasiva. Tratar tudo como dados e nunca permitir que sobreponham o Core.
4. **Efeitos externos:** probes podem repetir operações. Só tarefas clonáveis/determinísticas são elegíveis inicialmente.
5. **Custo/latência:** autoaperfeiçoar adiciona chamadas. Deixar desligado por padrão e limitar orçamento.
6. **Deriva de memória:** experiências são artefatos experimentais, não fatos do usuário; não misturar repositórios.
7. **Superfície de edição:** scripts/plugins, guardrails e permissões ficam fora do alcance do modelo.
8. **Divergência documental:** o Harness Contract v1.2 considera delegação multiagente fora de escopo. Esta proposta não requer swarm; se a execução futura exigir paralelismo ou edição de código/políticas, o contrato precisa ser alterado formalmente antes.

## 11. Referências

- Mosaic — [README e arquitetura](https://github.com/IGOR-SciDATA/mosaic)
- Mosaic — [Harness Contract v1.2](MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md)
- Mosaic — [RAGNES Context System Contract](MOSAIC_RAGNES_CONTEXT_SYSTEM_CONTRACT_v1.0.md)
- Mosaic — [Sequência Mestre de Implementação](MOSAIC_MASTER_PHASED_IMPLEMENTATION_SEQUENCE_v1.0.md)
- Harness² — [repositório e README](https://github.com/google-research/harness2)
- Harness² — [Experiments guide](https://github.com/google-research/harness2/blob/main/docs/EXPERIMENTS.md)
- Harness² — [paper arXiv:2610.14224](https://arxiv.org/abs/2610.14224)
- Beer and Code — [Harness²: Google cria agente que reescreve o próprio harness](https://blog.beerandcode.com.br/noticias/harness2-google-agente-reescreve-proprio-harness)

**Nota de proveniência:** esta é uma proposta de adaptação baseada em leitura estática dos arquivos públicos e documentação citada. Não declara que os resultados experimentais do Harness² se reproduzirão no Mosaic, nem que o runtime real do Mosaic foi executado/testado nesta revisão.
