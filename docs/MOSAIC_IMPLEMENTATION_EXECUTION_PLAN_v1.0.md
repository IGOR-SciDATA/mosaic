# MOSAIC — Plano de Implementação Passo a Passo

**Versão:** 1.0  
**Status:** Guia normativo de execução para o agente de implementação  
**Autoridade:** MASTER / Arquitetura  
**Escopo:** consolidar a fundação existente e evoluir o Harness universal, a experiência agêntica e o frontend sem reescrever o Core.

---

## 1. Objetivo

Este documento converte a arquitetura do Mosaic em uma sequência executável de trabalho. O agente de implementação deve seguir as etapas na ordem definida, trabalhar em incrementos pequenos e apresentar evidências antes de avançar.

O resultado esperado é um Mosaic capaz de concluir tarefas gerais com rastreabilidade: pesquisar na internet e citar fontes realmente consultadas; criar e validar documentos, planilhas e apresentações; desenvolver projetos de software com especialidades coordenadas; preservar contexto e retomar tarefas; e apresentar plano, estado, evidências e artefatos em uma interface clara. O Harness é o mecanismo de execução desse produto, não o objetivo final isolado. Para orientar a implementação a partir dessa visão, consultar também [o Prompt Normativo do Agente de Propósito Geral](MOSAIC_UNIVERSAL_AGENT_IMPLEMENTATION_PROMPT_v1.0.md).

**Não implementar todas as etapas em um único PR.** Cada etapa deve ter seu próprio escopo, testes, resumo de diff e critério de aceite. O MASTER valida a etapa antes da seguinte.

## 2. Fontes de verdade e precedência

1. Decisões explícitas do MASTER e regras de segurança.
2. Contrato oficial do Harness.
3. Contrato RAGNES.
4. Contrato de UX.
5. Roadmap Mestre, que define a ordem macro.
6. Contrato MVP de implementação, após ser canonizado em docs/.
7. Este plano operacional.
8. Código atual como evidência do comportamento implementado; código existente não autoriza ignorar segurança ou requisitos aprovados.

Se dois documentos contradisserem um ao outro, o agente deve parar somente a parte afetada, apontar os trechos em conflito e solicitar decisão. Não inventar schema, campos, estados, permissões ou infraestrutura.

## 3. Regras de trabalho obrigatórias

Para cada etapa:

1. Ler os contratos e inspecionar os arquivos afetados.
2. Identificar comportamento existente antes de alterar.
3. Propor o menor diff que cumpra o objetivo.
4. Implementar somente o escopo autorizado.
5. Executar testes direcionados e a suíte relevante.
6. Executar build ou smoke test quando aplicável.
7. Inspecionar o diff final e procurar regressões.
8. Registrar comandos executados, resultados reais e limitações.
9. Entregar ao MASTER resumo, arquivos alterados, testes, evidências e decisões pendentes.
10. Não iniciar a próxima etapa sem validação.

Nunca declarar um teste aprovado se não foi executado. Nunca declarar uma capacidade completa apenas porque há um módulo, endpoint ou teste escrito. Não falsificar progresso na interface.

## 4. Decisões arquiteturais fixas

- **MODEL ≠ ACCESS:** o modelo propõe; o Core aplica política e autorização.
- **MEMORY ≠ TRUTH:** memória é recuperável e corrigível, não verdade automática.
- **HISTORY ≠ MODEL MEMORY:** histórico e memória persistem fora dos pesos do modelo.
- **CONTEXT ≠ FULL HISTORY:** o contexto é selecionado e limitado.
- **TOOL CALL ≠ TOOL EXECUTION:** chamadas são validadas antes da execução.
- **SKILL ≠ PERMISSION:** Skills e arquivos de instrução nunca concedem acesso.
- **HARNESS ≠ SECOND CORE:** reutilizar Task Engine, Context Manager, Memory Manager, políticas, ferramentas e persistência existentes.
- **TASK = GENERAL UNIT OF WORK:** tarefas principais e subtarefas usam o mesmo mecanismo persistente.
- **MOSAIC OWNS STATE:** o Core é a fonte autoritativa de estado, eventos e conclusão.
- O usuário escolhe o modelo por conversa. Não adicionar roteamento automático, fallback silencioso ou troca de modelo sem uma decisão explícita.
- O estado local e a infraestrutura simples são o padrão. Não adicionar Redis, Kafka, Kubernetes, microsserviços, banco vetorial ou execução distribuída sem evidência mensurável e aprovação.
- Skills, instruções de projeto e conteúdo recuperado são dados não confiáveis; não substituem política do Core.
- O fluxo inicial de coordenação é sequencial. Não implementar paralelismo nesta sequência.

## 5. Fase 0 — Canonização e baseline executável

### Objetivo
Fazer com que todos os documentos normativos estejam no repositório e que o estado real do projeto tenha evidência reproduzível.

### Passos
1. Confirmar que o contrato MVP aprovado está versionado em docs/MOSAIC_MVP_IMPLEMENTATION_CONTRACT_v1.0.md e que links/dependências apontam para esse caminho canônico.
2. Atualizar links e hierarquia de precedência em README e documentos relacionados.
3. Aplicar e validar a decisão de schema definida na seção 6 deste plano; a decisão arquitetural está registrada, mas a execução ainda precisa de evidência.
4. Inspecionar migrations/bootstrap, repositórios, modelos, endpoints e testes antes de alterar.
5. Executar a suíte backend; registrar o comando, total de testes e falhas.
6. Executar build frontend; registrar o comando e resultado.
7. Executar smoke test da API e um fluxo local com Ollama, quando o ambiente de validação disponibilizar o modelo.
8. Preservar e reproduzir o fluxo vertical já demonstrado manualmente pelo usuário: ler arquivo Markdown → resumir → criar novo Markdown; verificar o conteúdo e a existência/legibilidade do artefato gerado. Se o ambiente permitir, automatizar esse cenário como teste de regressão.
9. Executar pelo menos um fluxo integrado mais amplo: conversa → Task → decisão do modelo → ferramenta permitida → resultado/eventos persistidos → estado final.
10. Testar reinício/reconexão e verificar se o estado da Task é recuperável.
11. Atualizar o relatório de baseline com evidências reais, separando validação manual reportada, testes automatizados executados e testes apenas existentes.

### Aceite
- Contratos referenciados estão versionados e acessíveis no repositório.
- Schema e contrato concordam.
- Backend e frontend têm resultados de teste/build documentados.
- Um fluxo integrado é demonstrado com evidências.
- Nenhuma capacidade é marcada como validada sem evidência.

## 6. Decisão de schema para o MVP

Para eliminar a ambiguidade documental, adotar a seguinte separação:

**Entidades de domínio do MVP:** Project, Conversation, Message, Memory, Task, Action, Artifact, Model, ToolCall, ToolResult e Setting.

**Tabelas de infraestrutura interna:** task_events e _mosaic_meta. Elas não substituem entidades de domínio.

**Decisão:** manter task_events para eventos persistidos e _mosaic_meta para metadados de inicialização/migração, e alinhar o schema de domínio ao contrato MVP aprovado, incluindo artifacts e settings. Não remover dados existentes nem recriar o banco destrutivamente.

### Passos de schema
1. Comparar DDL atual e contrato MVP campo a campo.
2. Preparar migração incremental e idempotente para tabelas/campos ausentes.
3. Preservar chaves, relações, índices e dados existentes.
4. Definir e testar comportamento de inicialização em banco vazio e banco existente.
5. Testar upgrade repetido sem duplicação nem perda de dados.
6. Atualizar testes de repositório e documentação do schema.

### Aceite
- Banco novo e banco existente inicializam corretamente.
- Migração repetida não duplica estruturas nem apaga dados.
- Todas as entidades normativas estão representadas sem transformar tabelas internas em entidades de domínio.
- Testes de persistência e migração passam.

## 7. Fase 1 — Integridade de estado, políticas e segurança

### Objetivo
Garantir que toda transição de Task/Action/ToolCall seja válida, persistida e autorizada pelo Core.

### Passos
1. Mapear transições permitidas de Task, Action, ToolCall e ToolResult.
2. Centralizar validação de transições em serviços do Core, sem duplicar regras no frontend.
3. Garantir que uma ferramenta proposta não seja executada antes da validação e aprovação exigida.
4. Revalidar argumentos e escopo no ponto de execução.
5. Revalidar traversal e symlinks no filesystem; allowlist, timeout, limites e cancelamento do terminal; SSRF, IPs privados, redirecionamentos e esquemas no fetch web.
6. Garantir limites de tempo, tamanho de saída, quantidade de iterações e recursos.
7. Redigir segredos e dados sensíveis de logs e resultados.
8. Testar falhas parciais, chamadas duplicadas e submissões repetidas.

### Aceite
- Estados inválidos são rejeitados pelo Core.
- Nenhuma ferramenta protegida executa antes da autorização aplicável.
- Testes de segurança negativos e positivos passam.
- A interface reflete o estado autoritativo retornado pela API.

## 8. Fase 2 — Harness conectado ao modelo da conversa

### Objetivo
Provar o ciclo agêntico completo com o modelo selecionado pelo usuário, sem roteamento automático.

### Passos
1. Reutilizar o Task Engine e o Agent loop existentes.
2. Resolver o modelo a partir da configuração persistida da conversa.
3. Montar contexto delimitado por meio do Context Manager.
4. Solicitar ao provider uma decisão estruturada: resposta final ou proposta de chamada de ferramenta.
5. Validar estrutura, nome da ferramenta, argumentos, limites e estado da tarefa.
6. Aplicar política e aprovação antes da execução.
7. Executar a ferramenta pelo registro/executor existente.
8. Persistir ToolCall, ToolResult, eventos e resultado da Task.
9. Incluir a observação da ferramenta no próximo contexto e permitir nova iteração limitada.
10. Parar em conclusão, erro, cancelamento ou limite de execução.
11. Registrar identificador de provider/modelo, uso de ferramentas e motivo de encerramento quando disponível.

### Aceite
Um teste integrado prova pelo menos dois ciclos: o modelo propõe uma ferramenta, o Core valida/executa conforme política, o resultado é persistido e o modelo usa a observação para concluir. Também provar resposta sem ferramenta, falha do provider, chamada inválida, rejeição de aprovação e limite de iterações.

## 9. Fase 3 — Eventos, streaming, cancelamento e retomada

### Passos
1. Padronizar eventos persistidos para criação, planejamento, aprovação, início/fim de ferramenta, validação, conclusão, falha e cancelamento.
2. Garantir que SSE emita eventos já persistidos e não seja a única cópia do estado.
3. Implementar recuperação do estado atual após reconexão.
4. Implementar cancelamento cooperativo no Core e nos executores compatíveis.
5. Recuperar tarefas ativas ou interrompidas após reinício, conforme política documentada.
6. Tornar comandos repetidos seguros contra duplicação quando aplicável.
7. Expor duração e detalhes técnicos somente quando conhecidos e redigidos.

### Aceite
Testes automatizados cobrem reconexão, eventos duplicados, cancelamento durante execução, falha do provider, reinício do backend e recuperação do estado final.

## 10. Fase 4 — Perfil de Agent e Skills por conversa

### Objetivo
Dar identidade operacional persistente a cada conversa sem confundir identidade com modelo ou permissão.

### Passos
1. Definir o perfil de Agent por conversa: nome, papel, instruções e Skills habilitadas.
2. Preservar a seleção de modelo já definida para a conversa.
3. Descobrir AGENTS.md e, se explicitamente suportado, AGENT.md, respeitando escopo por diretório e proveniência.
4. Resolver instruções do Core, projeto, perfil, Skills e objetivo da Task sem permitir que instruções inferiores substituam regras de segurança.
5. Versionar Skills e manter seleção controlada pelo usuário.
6. Criar snapshot imutável (conteúdo recuperável + versão/hash) no início de cada Task.
7. Reutilizar o snapshot original ao retomar a Task.
8. Registrar metadados de quais instruções/Skills entraram no contexto, sem expor conteúdo privado desnecessário.
9. Testar isolamento entre conversas, skills habilitadas/desabilitadas e alterações de perfil após início de tarefa.

### Aceite
Duas conversas podem usar perfis e Skills diferentes sem vazamento de contexto. Tarefas retomadas preservam o snapshot original. Skills não alteram permissões.

## 11. Fase 5 — Coordenador sequencial de subtarefas

### Objetivo
Decompor trabalhos grandes em Tasks dependentes usando o mesmo Task Engine.

### Passos
1. Definir representação de subtarefas, dependências, responsável, entradas, saídas e critérios de aceite.
2. Persistir a tarefa coordenadora e cada subtarefa como Tasks normais.
3. Executar sequencialmente, aguardando validação das dependências.
4. Compartilhar somente artefatos e resultados explicitamente necessários; manter contexto e instruções isolados por conversa.
5. Verificar resultados reais antes de avançar ou marcar o conjunto como concluído.
6. Tratar falha, bloqueio, repetição e cancelamento sem declarar sucesso indevido.

### Aceite
Uma tarefa composta demonstra duas ou mais subtarefas sequenciais, dependência real, resultados persistidos e tratamento de falha sem conclusão falsa.

## 12. Fase 6 — RAGNES e qualidade de contexto

### Passos
1. Manter seleção determinística por escopo: Core/global, projeto, conversa, Task/sessão e artefatos/conhecimento.
2. Ler arquivos explicitamente selecionados dentro do workspace autorizado.
3. Inventariar arquivos e metadados com limites de tamanho e quantidade.
4. Usar busca lexical (SQLite FTS5 ou mecanismo já aprovado) antes de adicionar embeddings.
5. Preservar caminho, hash/versão, intervalo/trecho e origem dos resultados.
6. Compactar histórico de sessão sem apagar decisões ou resultados importantes; manter referência ao histórico completo.
7. Criar conjunto de avaliação para perguntas de recuperação e medir relevância, cobertura e custo de contexto.
8. Só propor embeddings, índice vetorial ou reranking se avaliações mostrarem lacuna material na busca lexical.

### Aceite
Testes demonstram isolamento por escopo, limites de contexto, proveniência, tratamento de conteúdo malicioso como dado não confiável e resultados mensuráveis de recuperação.

## 13. Fase 7 — Ferramentas e artefatos reais

### Passos
1. Definir contrato de cada ferramenta: schema, escopo, aprovação, timeout, limite de saída, erros e persistência.
2. Confirmar que filesystem, terminal, search e web_fetch podem ser chamados pelo Harness e passam pelas políticas do Core.
3. Consolidar calculadora e clima como ferramentas delimitadas, sem permitir que falhas sejam mascaradas.
4. Implementar ferramentas de criação/edição de Markdown e validadores de conteúdo.
5. Adicionar geração de PDF, XLSX e PPTX em incrementos separados, com bibliotecas apropriadas e validação após salvar.
6. Validar reabertura do arquivo, conteúdo essencial, tipo, tamanho e caminho dentro do workspace.
7. Registrar fontes consultadas e referências usadas em artefatos de pesquisa.
8. Expor artefatos pela API e pela interface, somente quando a operação estiver implementada.

### Aceite
Cada ferramenta é testada no ciclo completo, não apenas em teste unitário isolado. Arquivos de saída são reabertos e validados; falhas aparecem para o usuário.

## 14. Fase 8 — Frontend: legibilidade e fluxo de trabalho

### Objetivo
Fazer a interface parecer um workspace de IA coeso, com o chat como centro e os detalhes de execução disponíveis quando necessários.

### Prioridades
1. Auditar todas as telas, rotas, componentes, estados e ações antes de redesenhar.
2. Manter a conversa como tela padrão; tarefas comuns não devem virar automaticamente uma execução de Agent.
3. Ampliar a área útil de chat e mensagens; reduzir espaços vazios, painéis redundantes e controles sem função real.
4. Melhorar tipografia: tamanho base legível, hierarquia consistente entre títulos, corpo, metadados e código, espaçamento de linha e largura de leitura.
5. Melhorar composer, mensagens longas, blocos de código, tabelas, listas, scroll e responsividade.
6. Unificar estados de carregamento, vazio, erro, reconexão e cancelamento.
7. Exibir timeline de Task com etapas reais; nunca inventar percentuais de progresso.
8. Exibir aprovação como cartão com ação, recurso-alvo, impacto e opções realmente suportadas pelo backend.
9. Manter detalhes técnicos recolhidos por padrão e disponíveis sob demanda.
10. Mostrar resultados e artefatos com ações funcionais.
11. Garantir acessibilidade por teclado, foco visível, contraste e rótulos.
12. Não expor controles para perfis, Skills ou autonomia se não houver suporte real no backend.

### Aceite
Build frontend passa. Testes de componentes ou fluxos, quando disponíveis, cobrem os estados principais. Uma revisão visual verifica desktop e viewport estreita. Os fluxos de conversar, iniciar tarefa, aprovar/rejeitar, cancelar, reconectar e abrir artefato funcionam com o backend.

## 15. Fase 9 — Fluxos ponta a ponta por tipo de tarefa

Validar, um por vez:
1. Conversa normal sem criação automática de Task.
2. Recuperação de memória/preferência em conversa posterior.
3. Recuperação de contexto de projeto e próximos passos.
4. Análise de arquivos selecionados.
5. Pesquisa web com fontes efetivamente consultadas.
6. Criação e validação de Markdown/PDF/XLSX/PPTX conforme ferramentas implementadas.
7. Tarefa de software dentro de workspace autorizado.
8. Falha de provider, falha de ferramenta, aprovação rejeitada, cancelamento e retomada.

Cada fluxo deve ter critérios de entrada, saída, evidências persistidas e teste automatizado sempre que viável.

## 16. Fase 10 — Autonomia limitada e resiliência

### Passos
1. Definir limites de iterações, tempo, ferramentas, bytes, recursos e escopo.
2. Aplicar perfis de autonomia no backend, nunca apenas na UI.
3. Preservar aprovação para ações com impacto conforme política.
4. Adicionar avaliação de sucesso, qualidade, taxa de falha, repetição, custo e recuperação.
5. Testar tarefas interrompidas e retomadas, resultados parciais e erros repetidos.
6. Documentar o que o sistema não pode fazer e como informa bloqueios.

### Aceite
Autonomia permanece dentro de limites explícitos e auditáveis. Nenhuma tarefa é concluída sem verificação de critérios definidos.

## 17. Paralelismo: fora do escopo imediato

Não implementar execução paralela de Agents nesta sequência. Só propor essa etapa após o MASTER validar:
- isolamento de contexto e configuração;
- ownership e conflitos de escrita no workspace;
- concorrência de estado e eventos;
- cancelamento e timeout;
- recuperação após falha;
- coordenação de dependências e validação;
- benefício mensurável sobre execução sequencial.

## 18. Definição de pronto para cada PR

Cada PR deve incluir:
- problema e objetivo;
- fase do roadmap atendida;
- arquivos/componentes afetados;
- decisão arquitetural utilizada;
- testes executados e saída resumida;
- build/smoke/E2E quando aplicável;
- riscos, limitações e trabalho restante;
- evidência de que o comportamento real corresponde ao objetivo.

Um PR deve alterar apenas uma fase/coerência coesa. Não misturar redesign completo, migração de schema, RAG avançado e autonomia em uma única mudança.

## 19. Modelo de relatório para o MASTER

~~~text
FASE:
OBJETIVO:
IMPLEMENTADO:
ARQUIVOS ALTERADOS:
DECISÕES APLICADAS:
TESTES EXECUTADOS:
RESULTADOS:
BUILD / SMOKE / E2E:
RISCOS E LIMITAÇÕES:
PENDÊNCIAS:
DIFF REVISADO: sim/não
PRONTO PARA VALIDAÇÃO DO MASTER: sim/não
~~~

**Ordem final:** consolidar contratos e baseline → segurança/estado → Harness → eventos/retomada → Agent/Skills → coordenação sequencial → contexto/RAGNES → ferramentas/artefatos → frontend → fluxos E2E → autonomia limitada. Uma fase por vez.
