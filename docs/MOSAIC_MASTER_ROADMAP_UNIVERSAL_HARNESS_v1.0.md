# MOSAIC — Master Roadmap: Harness Universal

**Versão:** 1.0  
**Status:** Roadmap normativo de implementação; baseline estático parcialmente auditado; validação dinâmica pendente  
**Data:** 2026-10-17  
**Repositório:** `IGOR-SciDATA/mosaic`  
**Objetivo:** conduzir o Mosaic, incrementalmente, de seu Core atual a um Harness confiável, extensível e capaz de concluir tarefas variadas — inspirado nos princípios operacionais observáveis de ferramentas como Claude Code, sem copiar sua implementação proprietária.

---

## 1. Decisões arquiteturais fixas

Estas decisões prevalecem sobre sugestões de implementação que as contradigam.

1. **O Core não escolhe automaticamente o modelo.** O usuário escolhe o modelo para cada conversa. O Harness usa esse modelo em todas as tarefas daquela conversa, salvo alteração explícita do usuário ou configuração explícita por tarefa. Não implementar roteamento automático, ranking de modelos, fallback silencioso ou troca por tipo de tarefa.
2. **Modelo, Agent, Conversation, Task e Skill são conceitos diferentes.**
   - **Model:** modelo configurado e disponível.
   - **Conversation:** histórico e contexto conversacional, com o modelo escolhido pelo usuário.
   - **Agent profile:** identidade operacional da conversa (nome, papel, instruções e referências às Skills habilitadas).
   - **Task:** unidade persistente e retomável de trabalho.
   - **Skill:** procedimento especializado versionado, reutilizável e controlado pelo usuário.
3. **Persistir as configurações por conversa.** O perfil do Agent, instruções como `AGENTS.md`/`AGENT.md`, Skills habilitadas e configuração relevante devem sobreviver a reinicializações. Alterações futuras não podem reescrever silenciosamente o contexto de uma tarefa já iniciada.
4. **Snapshot por tarefa.** Ao iniciar uma Task, registrar uma cópia imutável ou referência imutável verificável (versão + hash + conteúdo recuperável) do perfil, das instruções e das Skills efetivamente incluídas. Uma tarefa em execução não muda de instruções porque o usuário editou o perfil.
5. **Harness universal, ferramentas especializadas.** A universalidade está no ciclo de execução, na coordenação, no contexto, no estado e na validação — não em uma ferramenta gigante que tenta fazer tudo.
6. **Task é a unidade geral de trabalho.** Subtarefas também são Tasks persistidas, relacionadas à tarefa coordenadora por dependências e resultados. Não criar um segundo Task Engine.
7. **Core é dono do estado e da política.** Frontend e modelo não autorizam ações nem declaram sucesso sozinhos.
8. **Skills e instruções não concedem permissões.** Toda ação passa pela política de ferramentas e pelo mecanismo de aprovação existente.
9. **Persistência local primeiro.** Manter FastAPI, React/Vite, SQLite, filesystem/workspaces e providers locais como base do MVP. Não introduzir infraestrutura distribuída sem evidência mensurável de necessidade.
10. **Não declarar conclusão sem evidência.** A Task só termina quando critérios definidos foram verificados ou quando termina explicitamente em falha, cancelamento ou bloqueio.

## 2. Fontes de verdade e precedência

- Documentação versionada: contratos, decisões arquiteturais e roadmap.
- GitHub: implementação efetivamente existente.
- Testes e execução reproduzível: evidência do comportamento do código.

Precedência dos contratos:
1. Decisões explícitas do MASTER e requisitos de segurança.
2. [Harness Contract v1.2](MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md) para execução e ciclo do Harness, até ser substituído.
3. [RAGNES Context System Contract v1.0](MOSAIC_RAGNES_CONTEXT_SYSTEM_CONTRACT_v1.0.md) para contexto, recuperação e compactação.
4. [Frontend UX Contract v1.0](MOSAIC_FRONTEND_UX_IMPLEMENTATION_CONTRACT_v1.0.md) para interface e estados visíveis.
5. Este roadmap para a ordem macro das fases.
6. [Plano de Implementação Passo a Passo](MOSAIC_IMPLEMENTATION_EXECUTION_PLAN_v1.0.md) para tarefas operacionais e critérios de aceite.
7. MVP Implementation Contract v1.0 para entidades e schema, após canonização no repositório e decisão explícita sobre divergências.
8. Código atual como verdade da implementação — nunca como justificativa para perpetuar falhas de segurança ou comportamento incompleto.

Se dois contratos entrarem em conflito, Chat 01 deve interromper a mudança afetada e solicitar decisão do MASTER; não deve inventar reconciliação silenciosa. Para a divergência conhecida do schema, seguir a decisão normativa registrada na seção 6 do Plano de Implementação Passo a Passo: manter task_events e _mosaic_meta como tabelas internas e alinhar as entidades de domínio ao contrato MVP, incluindo artifacts e settings.

## 3. O que já existe — baseline a verificar

O repositório já possui uma fundação relevante, mas presença de módulos ou testes unitários não comprova um fluxo funcional de ponta a ponta.

### 3.1 Base declarada nos contratos e auditorias anteriores

- Frontend React + Vite e Core/API FastAPI.
- SQLite e workspaces em filesystem.
- Entidades de domínio previstas: Project, Conversation, Message, Memory, Task, Action, Artifact, Model, ToolCall, ToolResult e Setting.
- Abstrações de ModelProvider/Ollama.
- Context Manager, Memory Manager, Project Manager e Task Engine.
- Action/Permission layer, Tool Registry, ToolCall/ToolResult e ciclo de Agent.
- APIs de conversas, mensagens, projetos e tarefas em diferentes estágios.
- Contratos para Harness, RAGNES, UX, Skills, instruções de projeto e roadmap de implementação.
- O documento de perfis de Agent e ferramentas de artefatos está versionado em `docs/MOSAIC_AGENT_PROFILES_AND_ARTIFACT_TOOLS_ROADMAP_v1.0.md`; ele é uma proposta de evolução, não prova de implementação funcional.

### 3.2 Estado após inspeção estática de 2026-10-18

O [Relatório de Auditoria da Fase 0](MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md) contém inventário e evidências por arquivo. Resumo:

- O provider está conectado ao endpoint de tarefas via `create_provider_decider`; o fluxo integrado completo ainda não foi executado nesta auditoria.
- Os serviços de ferramentas contêm validação/aprovação e os testes cobrem casos negativos de filesystem, terminal e URLs; os testes não foram executados nesta auditoria.
- `task_events`, endpoints de listagem e stream SSE existem; reconexão do frontend e retomada após reinício ainda precisam de demonstração E2E.
- O frontend contém implementação de workspace e estados de aprovação; build e jornadas visuais não foram executados.
- Perfis operacionais por conversa e snapshots imutáveis por Task não estão comprovados como completos.
- A coordenação de subtarefas persistidas com dependências reais não está comprovada como completa.
- O bootstrap SQLite cria `task_events` e `_mosaic_meta`, mas não cria as tabelas `artifacts` e `settings` listadas no contrato MVP. A divergência deve ser decidida antes de qualquer alteração de schema.
- O MVP Implementation Contract v1.0 é citado por contratos, mas não está versionado no caminho esperado em `main`.
- O documento de perfis e ferramentas de artefato está versionado em `docs/MOSAIC_AGENT_PROFILES_AND_ARTIFACT_TOOLS_ROADMAP_v1.0.md`; sua presença é uma proposta documental, não evidência de que todos os artefatos ou perfis estejam implementados.
- Pytest, build frontend, smoke test Ollama e E2E não foram executados nesta auditoria; não há execução de workflow retornada para o commit de referência.

**Regra:** não inferir conclusão de fase a partir de arquivos existentes ou PRs mesclados. Cada capacidade exige teste relevante, integração e evidência reproduzível.

## 4. Arquitetura-alvo

```text
React UI
  ├── Chat + seleção explícita do modelo
  ├── Configuração do Agent por conversa
  ├── Editor/visualizador de AGENTS.md e Skills
  ├── Workspace de arquivos e artefatos
  └── Timeline de execução + aprovações + resultados
             │ REST / SSE
             ▼
FastAPI / MOSAIC CORE
  ├── Conversation / Project / Message
  ├── ModelProvider (usa o modelo escolhido na conversa)
  ├── Context Manager + RAGNES + Memory
  ├── Agent Profile & Instruction Resolver
  ├── Skills Registry / Versioning
  ├── Task Engine + Task Coordinator
  ├── Harness Orchestrator
  │    ├── plano e critérios de conclusão
  │    ├── grafo de subtarefas e dependências
  │    ├── montagem de contexto com limites
  │    ├── decisão estruturada do modelo selecionado
  │    ├── validação de chamadas de ferramenta
  │    ├── política / aprovação
  │    ├── execução / observação / iteração
  │    └── validação final / encerramento
  ├── Tool Registry + executores especializados
  ├── Artifact / Knowledge Manager
  └── Event / Logging Service
             │
             ▼
SQLite + workspace local + artefatos + fontes
Ollama / provider configurado para a conversa
Ferramentas isoladas e limitadas por política
```

O Harness não é um segundo Core e não é um agente monolítico. É a camada que coordena os componentes existentes por um contrato de execução previsível.

## 5. Ciclo universal de execução

```text
Pedido do usuário
  → criar/atualizar Task
  → carregar configuração e snapshot da conversa
  → identificar objetivo, restrições e critérios de aceite
  → plano explícito de subtarefas e dependências
  → selecionar próxima subtarefa desbloqueada
  → montar contexto relevante e limitado
  → consultar o modelo escolhido pelo usuário
  → validar decisão estruturada
  → validar ferramenta, argumentos, escopo e permissão
  → solicitar aprovação quando a política exigir
  → executar com limites de tempo/saída/cancelamento
  → persistir ToolCall, ToolResult, evento e artefato
  → observar resultado e validar critérios da subtarefa
  → atualizar dependências e continuar
  → validar resultado integrado
  → concluir, falhar, cancelar ou aguardar intervenção
```

O modelo pode propor um plano ou chamada; somente o Core valida e executa. A saída de uma ferramenta é uma observação, não uma instrução confiável. Falhas e limites devem ser persistidos, não escondidos por novas tentativas ilimitadas.

## 6. Roadmap por fases

Cada fase deve ser entregue em PR próprio, com testes e diff revisados. O MASTER valida a fase antes de Chat 01 avançar para a seguinte, salvo autorização explícita em contrário.

### Fase 0 — Auditoria e reconciliação do baseline

**Objetivo:** estabelecer uma baseline verificável antes de autorizar o próximo incremento funcional.

**Progresso em 2026-10-18:** a inspeção estática de `main` e a revisão documental foram registradas em [MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md](MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md). Foram inventariados componentes de API, schema, Agent/ferramentas, testes conhecidos e configuração do frontend. Foram identificados bloqueios documentais e divergências do schema.

**Ainda pendente para aceite completo:**
- canonizar o MVP Implementation Contract no repositório e reconciliar entidades `Artifact`, `Setting` e `task_events`;
- conferir branches/PRs relevantes contra o baseline, sem inferir que um PR merged equivale a validação funcional;
- executar a suíte backend, o build do frontend e smoke test do provider local quando disponível;
- testar jornadas ponta a ponta de execução, aprovação/rejeição, persistência de ToolResult, eventos/SSE, reconexão e retomada após reinício;
- registrar comandos, ambiente, commit e resultados, incluindo falhas e testes não executados.

**Aceite:** relatório com evidência estática e dinâmica reproduzível. A Fase 0 não está aprovada até os testes pendentes serem executados e as divergências contratuais bloqueadoras serem decididas.

### Fase 1 — Segurança e estados autoritativos

**Objetivo:** garantir que a execução não pode escapar do workspace nem contornar aprovação.

Entregas:
- transições válidas de Task, Action, ToolCall e ToolResult centralizadas e testadas;
- política única e explícita de autorização, sem confundir Action com ToolCall;
- filesystem confinado ao workspace, proteção contra traversal e symlinks;
- terminal com allowlist/execução não interativa, timeout, limite de saída, encerramento de processos e cancelamento;
- web fetch separado de search, proteção contra SSRF/IPs privados, redirects e respostas excessivas;
- validação de schema/argumentos, idempotência quando aplicável, redaction de segredos;
- falha segura quando permissão, workspace ou estado são ambíguos.

Aceite: testes negativos para path traversal, comandos bloqueados, SSRF, argumentos inválidos, aprovação rejeitada, cancelamento e transições inválidas.

### Fase 2 — Harness integrado com modelo da conversa

**Objetivo:** provar o ciclo real sem roteamento automático.

Entregas:
- conectar o modelo selecionado na Conversation ao Harness por ModelProvider;
- protocolo de decisão estruturada e validada: resposta final, chamada de ferramenta ou pedido de esclarecimento/espera conforme contrato;
- ciclo decide → valida → executa → observa → decide, com limites de iteração, tempo, contexto e saída;
- persistência dos estados e retomada após falha ou reinício;
- erros do provider explícitos, sem troca silenciosa para outro modelo;
- testes com provider fake determinístico e smoke test com provider real quando disponível.

Aceite: tarefa simples completa com ferramenta real, resultado observado pelo mesmo modelo da conversa e resposta final baseada no resultado persistido.

### Fase 3 — Eventos, APIs e execução retomável

**Objetivo:** tornar cada execução observável e recuperável.

Entregas:
- eventos estruturados com timestamp, componente, evento, status, duração e IDs de Task/Conversation/ToolCall/Artifact;
- APIs de status, eventos, cancelamento, aprovações e resultados;
- SSE com reconexão e recuperação de eventos perdidos;
- logs redigidos e sem chain-of-thought privado;
- limites de armazenamento e tamanho de payload.

Aceite: execução continua visível após refresh/reconexão e seu histórico pode ser reconstruído a partir do estado persistido.

### Fase 4 — Agent por conversa, instruções persistentes e Skills versionadas

**Objetivo:** permitir que cada conversa mantenha sua própria configuração operacional.

Entregas:
- perfil de Agent por Conversation: nome, papel, instruções, modelo já escolhido na conversa e Skills habilitadas;
- persistir `AGENTS.md` e/ou `AGENT.md` do workspace/projeto, com escopo documentado e origem visível;
- descoberta determinística de instruções raiz e aninhadas; regras de precedência e conflito; conteúdo tratado como instrução não confiável até validado pelo Core;
- Skills versionadas, habilitadas/desabilitadas pelo usuário, com descrição, conteúdo, hash e limites de contexto;
- snapshot imutável por Task do perfil, instruções e versões/conteúdos de Skills realmente incluídos;
- mudanças de perfil/instruções/Skills afetam novas Tasks; tarefa ativa mantém seu snapshot, exceto ação explícita de reiniciar/atualizar snapshot;
- UI para editar, revisar origem, habilitar e inspecionar o que foi aplicado.

Persistência inicial: reutilizar estruturas existentes (por exemplo, configuração JSON de Conversation/Project) se atenderem aos requisitos de integridade, consulta e migração. Criar tabela nova somente com justificativa documentada; não introduzir schema por conveniência.

Aceite: duas conversas do mesmo projeto podem ter Agents/Skills diferentes; reiniciar o backend preserva as configurações; hash e snapshot da Task reproduzem instruções efetivamente usadas; Skills não concedem permissões.

### Fase 5 — Task Coordinator e decomposição real

**Objetivo:** transformar o plano em trabalho persistente, executável e verificável.

Entregas:
- plano estruturado com objetivo, critérios de aceite, subtarefas, dependências, entradas, saídas esperadas e riscos;
- cada subtarefa é uma Task persistida, ligada à tarefa coordenadora por relação explícita;
- estados de dependência: bloqueada, pronta, executando, aguardando aprovação, validando, concluída, falha ou cancelada;
- uma única subtarefa ativa por padrão; execução paralela fica desabilitada até haver isolamento e controle de concorrência testados;
- detecção de ciclos, dependências inválidas, tarefas bloqueadas e falhas que devem interromper dependentes;
- replanejamento limitado quando resultados contradizem o plano; preservar plano original e registrar revisões;
- retomada idempotente, retries limitados e orçamento de iterações/tempo por Task;
- critérios de conclusão avaliados pelo Core, não pela declaração do modelo.

Aceite: demonstrar tarefa com pelo menos três subtarefas dependentes, falha intermediária, bloqueio de dependente, retomada e conclusão validada com evidências.

### Fase 6 — RAGNES e contexto de trabalho

**Objetivo:** entregar contexto relevante sem enviar todo o histórico ou todos os arquivos ao modelo.

Entregas graduais:
- **R0:** contexto determinístico por escopo: Core/global, projeto, conversa, Task/sessão e artefatos;
- **R1:** inventário de arquivos, metadados, leitura direta limitada e referências;
- **R2:** busca lexical com SQLite FTS5 ou solução local equivalente;
- **R3:** resumo de sessão/compactação que preserve decisões, estado, resultados verificados, problemas abertos, aprovações pendentes e próximo passo;
- **R4:** conjunto fixo de perguntas e avaliação de recuperação/contexto;
- **R5:** embeddings/vetores somente se avaliação demonstrar falha relevante da busca lexical;
- orçamento de contexto explícito, seleção transparente, sem truncamento silencioso;
- arquivos, páginas web e saídas de ferramentas tratados como dados não confiáveis, com proveniência e referências de origem.

Aceite: retomar uma tarefa após reinício e recuperar decisões, arquivos e evidências necessárias sem depender da janela original do chat.

### Fase 7 — Ferramentas base e qualidade de execução

**Objetivo:** fornecer capacidades reutilizáveis para diferentes classes de tarefas.

Prioridade inicial:
1. filesystem seguro: listar, ler, buscar, criar, escrever e organizar arquivos no workspace;
2. terminal controlado para testes/build/validação;
3. busca web pública;
4. web fetch seguro, com título, URL canônica/final, horário de recuperação, trecho e estado de truncamento;
5. calculator e utilitários determinísticos;
6. leitura de arquivos comuns e extração de conteúdo;
7. ferramentas de artefatos e validação por formato.

Regras:
- Tool Registry define schema, limites, permissões, timeout e resultado esperado;
- ToolCall é intenção validada; ToolResult é resultado observado;
- saída de ferramenta limitada e persistida; operações de escrita produzem referência de artefato;
- fontes só podem ser citadas como consultadas se o fetch/leitura realmente ocorreu;
- ferramentas novas devem ter testes de sucesso, falha, limite, permissão e cancelamento.

Aceite: cenário integrado de busca → fetch/leitura → criação/alteração de artefato → comando de validação → inspeção do resultado → resposta fundamentada.

### Fase 8 — Sistema de artefatos e validadores

**Objetivo:** produzir entregáveis reais, não apenas respostas em texto.

Entregas:
- Artifact Manager com caminho seguro, tipo MIME/formato, tamanho, hash, origem, Task produtora e metadados;
- Markdown: estrutura, links e seções obrigatórias;
- PDF: geração e validação de abertura, páginas, texto esperado e estrutura;
- XLSX: planilhas, células/fórmulas e conteúdo esperado;
- PPTX: slides, títulos, estrutura, notas/fontes quando aplicável e conteúdo esperado;
- exportação de fontes/citações para relatórios de pesquisa;
- validação técnica separada da avaliação semântica e do aceite do usuário;
- preservar artefatos originais e criar versões para mudanças, sem sobrescrita silenciosa.

Bibliotecas devem ser adicionadas apenas na fase correspondente e com testes. Não instalar toda a stack de geração de arquivos antecipadamente.

Aceite: gerar, reabrir e validar pelo menos um artefato real de cada formato suportado; erros são mostrados e não mascarados como sucesso.

### Fase 9 — UI de trabalho agentic

**Objetivo:** tornar o fluxo utilizável, transparente e retomável.

Entregas:
- Chat continua sendo a entrada principal;
- seleção explícita do modelo na conversa e indicador claro do modelo em uso;
- configuração do Agent, instruções e Skills por conversa;
- Task Workspace com plano, subtarefas, dependências e estado;
- timeline de eventos e chamadas/retornos de ferramentas;
- cartões de aprovação com argumentos seguros e opções claras;
- arquivos, fontes, artefatos e validação do resultado;
- estados de erro, cancelamento, retomada e reconexão;
- observabilidade detalhada recolhida por padrão;
- interface em português, acessível e sem progresso falso, percentuais inventados ou controles inertes.

Aceite: usuário consegue acompanhar, aprovar, cancelar, retomar e inspecionar o resultado sem consultar logs do servidor.

### Fase 10 — Redesign e simplificação do frontend

**Objetivo:** revisar a experiência visual do Mosaic como um todo para que o frontend reflita o Harness real, seja confortável para conversas longas e não carregue elementos redundantes ou funcionalidades sem uso.

Entregas:
- auditoria de todas as telas, componentes, navegação, estados e chamadas de API; identificar conteúdo duplicado, seções pouco úteis, controles sem ação e fluxos inconsistentes;
- definir uma hierarquia visual clara: conversa como superfície principal, projetos e histórico acessíveis, configurações do Agent/Skills em locais previsíveis e execução detalhada disponível quando necessária;
- ampliar a área útil de chat, mensagens e tipografia de leitura, com largura de conversa confortável, espaçamento adequado e composer maior; adotar como referência a experiência de leitura e composição do ChatGPT sem copiar elementos de marca;
- reduzir ruído visual: remover ou recolher conteúdo pouco utilizado, metadados técnicos permanentes, painéis redundantes e informações repetidas; manter detalhes operacionais acessíveis sob demanda;
- desenhar comportamento responsivo para desktop e telas menores, com navegação e painéis que não comprimam a conversa;
- unificar componentes e padrões para estados vazios, carregamento real, erro, cancelamento, aprovação, retomada e conclusão;
- integrar a timeline, subtarefas, ferramentas, fontes e artefatos sem transformar o chat em um painel técnico poluído;
- assegurar que progresso e status venham do Core, que os textos sejam claros em português e que nenhum controle seja meramente decorativo;
- rever acessibilidade, contraste, foco, teclado, legibilidade e consistência visual;
- criar critérios visuais e funcionais verificáveis e comparar antes/depois com screenshots ou walkthrough reproduzível, quando disponíveis.

Princípios de UX:
- **Chat primeiro:** mensagens e entrada do usuário ocupam a maior parte da tela.
- **Detalhes sob demanda:** plano, logs, argumentos de ferramentas e metadados aparecem em painéis recolhíveis ou áreas dedicadas.
- **Menos, mas funcional:** remover ou simplificar elementos que não contribuem para compreender, controlar ou concluir o trabalho.
- **Sem esconder o essencial:** aprovação pendente, erro, tarefa em execução e resultado final devem continuar evidentes.
- **Sem simular capacidade:** não mostrar botões, progresso ou ações que o backend ainda não suporta.

Aceite:
- conversa visualmente ampla, com mensagens e campo de entrada confortáveis;
- fluxo coerente entre chat, projetos, Agent, Skills, tarefas, aprovações e artefatos;
- conteúdo redundante removido ou recolhido, sem perder capacidades necessárias;
- layout utilizável em desktop e telas menores;
- testes/build frontend aprovados e walkthrough das principais jornadas: conversa comum, execução agentic, aprovação, falha/cancelamento, retomada e inspeção de artefato.

### Fase 11 — Fluxos completos por tipo de tarefa

**Objetivo:** provar universalidade por cenários completos, não por lista de ferramentas.

Ordem de validação:
1. criar/editar arquivos e projeto de documentos;
2. pesquisar fontes e entregar relatório com referências verificáveis;
3. produzir PDF;
4. produzir planilha XLSX;
5. produzir apresentação PPTX;
6. construir pequeno sistema web com arquitetura, backend, frontend, testes, integração e QA;
7. retomar cada fluxo após reinício e recuperar artefatos/estado.

Cada cenário deve usar o mesmo Harness e Tasks/subtasks, variando apenas ferramentas, Skills e validadores. Critérios específicos do cenário devem ser registrados e testados.

Aceite: todos os cenários passam de pedido a entregável validado, com estado, fontes/arquivos e histórico persistidos. Não alegar capacidade universal além da matriz efetivamente testada.

### Fase 12 — Resiliência, avaliação e autonomia limitada

**Objetivo:** medir qualidade e aumentar autonomia com segurança.

Entregas:
- dataset local de tarefas de referência e resultados esperados;
- métricas: sucesso validado, falha, retrabalho, uso de ferramentas, tempo, custo computacional aproximado, contexto enviado e recuperação após interrupção;
- testes de regressão por modelo/provider selecionado, sem roteamento automático;
- limites de execução e retries configuráveis pelo Core;
- perfis de autonomia (assistido, controlado, autonomia limitada) como política backend, não apenas UI;
- testes de prompt injection, instruções maliciosas em arquivos/páginas e exfiltração;
- recuperação após crash, resultados parciais, aprovações pendentes e tarefas órfãs;
- runbook de instalação, configuração do provider escolhido, diagnóstico e recuperação.

Aceite: métricas e falhas reproduzíveis, limites aplicados pelo backend, nenhum bypass de permissão conhecido nos testes de segurança definidos.

### Fase 13 — Paralelismo controlado e extensibilidade (somente após validação)

**Objetivo:** ampliar throughput sem transformar o Mosaic em um swarm difícil de depurar.

Pré-condições obrigatórias:
- Task Coordinator confiável;
- dependências e isolamento testados;
- eventos, cancelamento e recuperação funcionais;
- workspace compartilhado com locking/conflito explícito;
- orçamento global e por Task;
- validação integrada e testes de regressão.

Entregas possíveis:
- execução paralela de subtarefas comprovadamente independentes;
- agentes especializados como perfis de conversa (arquitetura, frontend, backend, QA), coordenados sequencialmente no início;
- contratos de entrada/saída e critérios de aceite por subtarefa;
- revisão cruzada como tarefa explícita, não aprovação automática;
- fila local simples somente se concorrência real justificar.

Fora de escopo até aprovação explícita: swarm autônomo irrestrito, execução distribuída, microserviços, SaaS multi-tenant e marketplace de plugins.

Aceite: paralelismo demonstrado em subtarefas independentes, com conflitos detectados, cancelamento, limites e resultados determinísticos o bastante para depuração.

## 7. Modelo de persistência conceitual

A implementação exata depende da auditoria e do contrato de banco; o comportamento esperado é:

- **Conversation:** modelo escolhido pelo usuário, configuração do Agent, referências de instruções e Skills habilitadas.
- **Instruction source:** conteúdo, escopo, origem, hash e data de atualização para `AGENTS.md`/`AGENT.md`.
- **Skill version:** identificador, versão, conteúdo ou referência imutável, hash, metadados e estado de habilitação.
- **Task:** plano, critérios de aceite, parent/coordinator Task ou vínculo equivalente, status e resultado.
- **Task snapshot:** modelo/provider efetivamente selecionado na conversa, perfil, instruções e Skills realmente incluídos, hashes e timestamp.
- **ToolCall/ToolResult:** intenção validada, estado de autorização, execução e resultado real.
- **Artifact:** referência ao arquivo produzido, tipo, hash, Task produtora e validação.
- **Event:** eventos de ciclo de vida para timeline e diagnóstico.

Não adicionar todas essas estruturas como tabelas automaticamente. Primeiro verificar se os contratos e o schema atual suportam o comportamento com integridade suficiente. Se não suportarem, apresentar uma mudança de contrato pequena e justificada ao MASTER.

## 8. Critérios globais de qualidade

Uma capacidade só é considerada implementada quando:
- tem contrato/schema claro;
- possui teste de sucesso e falha;
- respeita escopo e autorização;
- persiste estado necessário;
- tem resultado observável na API/UI;
- é retomável quando o caso exige;
- valida o entregável com ferramenta apropriada;
- tem logs sem segredos ou chain-of-thought privado;
- funciona com o modelo escolhido na conversa, sem troca automática;
- é coberta por regressão e documentada.

## 9. Regras de execução para Chat 01

1. Executar **uma fase por PR**.
2. Antes de implementar, inspecionar a branch atual e os contratos aplicáveis.
3. Não declarar testes executados se não foram executados.
4. Não expandir schema, dependências ou infraestrutura sem justificativa.
5. Não alterar automaticamente o modelo escolhido pelo usuário.
6. Não fazer tarefas paralelas antes da Fase 13 e de suas pré-condições.
7. Manter cada mudança pequena, reversível e acompanhada de testes.
8. Atualizar documentação e matriz de capacidades após cada fase.
9. Ao encontrar conflito arquitetural, parar e pedir decisão do MASTER.
10. O MASTER valida o diff, testes, riscos e coerência antes da próxima fase.

## 10. Primeiro próximo passo

**Concluir a validação dinâmica da Fase 0.** A inspeção estática e as divergências encontradas estão documentadas em [MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md](MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md). Antes da próxima fase funcional, canonizar o contrato MVP, decidir as divergências de schema e executar testes/build/smoke/E2E no checkout do implementador. O MASTER autoriza um único próximo incremento após revisar essas evidências.

## 11. Definição de sucesso do projeto

O Mosaic terá atingido o objetivo principal quando um usuário puder, em uma conversa com o modelo que ele escolheu, solicitar tarefas variadas, e o Core conseguir:

- persistir a configuração do Agent, instruções e Skills;
- transformar o pedido em Tasks e subtarefas com dependências;
- executar ferramentas especializadas sob política e aprovação;
- observar e validar resultados reais;
- produzir arquivos, pesquisas e projetos com evidência;
- retomar a execução após interrupções;
- apresentar plano, progresso factual, fontes, arquivos, falhas e resultado final;
- encerrar somente quando critérios de conclusão forem verificados.

A ambição é um Harness robusto e geral. A promessa de capacidade deve crescer conforme cresce a matriz de cenários testados — nunca antes.


## 12. Evidência de capacidade já demonstrada — 2026-10-18

O usuário confirmou que, na versão atual do protótipo, concluiu manualmente o seguinte fluxo pelo agente:

1. selecionar/fornecer um arquivo Markdown (`.md`);
2. o agente ler o arquivo;
3. resumir seu conteúdo;
4. criar um novo arquivo Markdown com o resumo;
5. acompanhar o fluxo até a conclusão e confirmar a criação do artefato.

Esta é uma evidência manual reportada pelo usuário e deve ser registrada como **fluxo funcional demonstrado no protótipo**. Ela demonstra uma primeira cadeia integrada de leitura de arquivo, transformação de conteúdo e escrita de artefato. Não prova, por si só, a robustez de retomada, segurança de todos os caminhos, execução com qualquer arquivo ou suporte a DOCX/PDF/PPTX/XLSX, pesquisa web ou projetos de software.

### Ação de continuidade

- Preservar o fluxo como cenário de regressão prioritário.
- Quando o ambiente de desenvolvimento estiver disponível, automatizar teste de leitura/resumo/escrita com fixture Markdown e validar o conteúdo do arquivo gerado.
- Não substituir o resultado manual reportado por uma afirmação de teste automatizado até que o teste seja implementado e executado.
- Atualizar o estado do README conforme novas evidências forem produzidas.


## 13. Avaliação arquitetural de propostas — 2026-10-18

Esta seção registra propostas novas avaliadas pelo MASTER. Ela complementa o roadmap, mas não altera silenciosamente contratos de schema, segurança, provider ou UX. A presença de uma proposta aqui não significa que a capacidade esteja implementada ou aprovada para execução imediata.

### 13.1. Acesso a modelos por interfaces web de terceiros

**Motivação reportada:** permitir que o usuário aproveite uma sessão/conta web que já possui, reduzindo ou evitando cobrança por chamadas de API.

**Decisão:** investigar como uma modalidade futura de acesso; não tratar automação de interfaces web de terceiros como provider aprovado nem como substituto equivalente à API.

Princípios obrigatórios para qualquer prova de conceito:

- Preservar `MODEL ≠ ACCESS`: o modelo lógico, o mecanismo de acesso e a execução permanecem conceitos separados.
- O usuário continua escolhendo explicitamente o modelo/acesso por conversa; não implementar roteamento, fallback ou troca silenciosa.
- O Core continua dono da Task, do estado, das aprovações, do histórico Mosaic e da validação do resultado.
- Persistir somente dados de sessão que sejam legitimamente acessíveis e necessários. A URL de uma conversa pode ser uma referência, mas não prova que o Mosaic consegue ler, retomar ou verificar seu conteúdo.
- Registrar a origem do resultado, timestamp, estado de recuperação e limitações. Não afirmar que uma resposta foi recuperada se o usuário ou uma integração autorizada não a tornou disponível ao Core.
- Não armazenar senhas, cookies, tokens de sessão ou dados de autenticação em texto aberto; não contornar CAPTCHA, controles de acesso, mecanismos anti-automação ou restrições do serviço.
- Antes de qualquer automação, avaliar termos aplicáveis, autorização explícita do usuário, estabilidade, privacidade, segurança, limites, manutenção e custo total. Uma assinatura web não deve ser presumida como autorização para automação programática.
- Se não existir mecanismo autorizado e tecnicamente confiável, manter a opção como fluxo assistido pelo usuário (por exemplo, abrir uma página e permitir que o usuário traga a resposta) ou não implementar a integração automática.
- Não introduzir uma tabela ou infraestrutura nova antes de demonstrar a necessidade. Primeiro avaliar se a abstração de acesso e os metadados existentes conseguem representar a modalidade sem comprometer integridade.

**Critérios para decidir se avança:** protótipo isolado, autorização e limites documentados, prova de ida/volta reproduzível, tratamento de sessão expirada/erro, persistência de proveniência e revisão de segurança. Só então o MASTER decide se vira um acesso suportado. Esta proposta não muda a escolha explícita de modelo por conversa nem autoriza dependência de scraping de UI.

### 13.2. Ferramenta meteorológica

**Decisão:** manter clima como ferramenta especializada candidata a validação funcional, integrada ao Tool Registry e ao ciclo universal existente; não criar um fluxo de execução paralelo.

Antes de implementar ou reescrever, Chat 01 deve inspecionar a ferramenta atual e determinar o que existe de fato. Se já houver implementação, reutilizar o código válido e preencher apenas lacunas.

Contrato comportamental esperado:

- aceitar uma localização fornecida pelo usuário, como cidade, bairro/região, estado ou país; esclarecer quando a localização for ambígua;
- diferenciar condições atuais de previsão e deixar explícito o período consultado;
- consultar fonte meteorológica real e registrar fonte, localização resolvida, horário de consulta e unidade usada;
- tratar geocodificação ambígua, indisponibilidade da fonte, timeout, limite de requisições e resposta incompleta sem inventar valores;
- persistir ToolCall/ToolResult/eventos conforme os contratos vigentes e devolver ao modelo o resultado observado;
- mostrar a fonte e a atualização ao usuário; nunca apresentar dados simulados como clima atual.

**Aceite:** testes determinísticos para localização válida, ambígua e inválida, erro/timeout da fonte e formatação; além de smoke/E2E com fonte real quando o ambiente permitir. Até a execução desses testes, a capacidade deve ser marcada como existente, implementada, testada ou validada conforme a evidência real — não presumida.

### 13.3. Identidade visual brasileira e temas claro/escuro

**Decisão:** incluir a identidade visual como trabalho de produto/frontend, sem bloquear a validação do Core nem antecipar uma logo ainda não definida.

Diretrizes:

- construir uma linguagem visual brasileira contemporânea, própria e tecnológica; evitar depender apenas de símbolos patrióticos literais;
- preparar tokens semânticos para cores, superfícies, bordas, foco, estados, tipografia e espaçamento, com variantes para tema claro e escuro;
- permitir alternância explícita entre claro/escuro e persistir a preferência usando o mecanismo de configuração já aprovado, sem adicionar schema desnecessário;
- garantir contraste, foco visível, navegação por teclado, legibilidade e estados equivalentes nos dois temas;
- manter os estados de Task, aprovação, erro, fontes e artefatos factuais e consistentes com o contrato de UX;
- desenvolver e aprovar a logo como artefato de design separado; não codificar a identidade em componentes de forma que dificulte sua substituição.

**Aceite:** revisão visual das jornadas principais nos dois temas, teste de persistência da preferência, contraste/foco e build frontend executado. A adoção da identidade não altera a arquitetura do Core.

### 13.4. Ordem e limites de escopo

Estas propostas não substituem os bloqueios da Fase 0, a política de segurança, a seleção explícita de modelo ou a validação E2E. A ordem recomendada é:

1. concluir a validação dinâmica e a reconciliação contratual pendentes da Fase 0;
2. preservar e automatizar o cenário de regressão Markdown → resumo → novo Markdown;
3. inspecionar e validar a ferramenta de clima existente, implementando somente as lacunas comprovadas;
4. definir a linguagem visual e implementar temas claro/escuro sob o contrato de UX;
5. conduzir uma investigação técnica separada sobre acesso por interfaces web, sem incorporá-la ao caminho crítico até demonstrar viabilidade, autorização e segurança.

Cada item funcional deve ter escopo e evidências próprios. Não introduzir mudanças de schema, novos serviços ou infraestrutura apenas para antecipar essas propostas.
