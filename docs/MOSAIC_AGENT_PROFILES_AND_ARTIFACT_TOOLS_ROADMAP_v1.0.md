# MOSAIC — Agent Profiles, Skills e Ferramentas de Produção
**Versão:** 1.0  
**Status:** Proposta de evolução incremental; exige validação Master antes de implementação funcional  
**Data:** 2026-10-17  
**Repositório:** IGOR-SciDATA/mosaic  
**Base auditada:** `main` em `35570385743f4b4bdb0dec8acddd6459184fea5b`

## 1. Objetivo

Evoluir o Harness já funcional para que o usuário possa manter agentes independentes dentro de um mesmo projeto, selecionar skills por agente/tarefa, produzir artefatos profissionais (PDF, XLSX, PPTX), pesquisar fontes online e construir aplicações web por etapas coordenadas de design, frontend, backend e validação.

Esta proposta não autoriza uma reescrita. O Task Engine existente continua sendo a única unidade de execução e o Core continua controlando contexto, permissões, aprovação, ferramentas, resultados e conclusão.

## 2. Resultado da auditoria inicial

### Já existe no código

- FastAPI, SQLite, projetos, conversas, mensagens, tarefas, ToolCall/ToolResult e eventos persistidos.
- Um ciclo real de agente que planeja tarefas simples, lê fontes explicitamente indicadas, envia evidências ao modelo, solicita aprovação para escrita e verifica o artefato.
- O executor de arquivos é limitado ao workspace e não deve substituir arquivos existentes sem uma operação autorizada.
- O terminal é restrito a uma allowlist de comandos, tem timeout, limite de saída e cancelamento; não é um shell geral.
- Ferramentas registradas: `filesystem`, `terminal`, `search`, `web_fetch`, `calculator`, `weather`.
- `AGENTS.md` é carregado da raiz do workspace do projeto. O conteúdo é tratado como orientação não confiável e não pode autorizar ações.
- Skills são persistidas em `project.state["agent_skills"]`; as habilitadas são incluídas no contexto do modelo com limites de tamanho.
- Arquivos do workspace podem ser listados, lidos e pesquisados pela API de artefatos.

### Limitações e lacunas comprovadas por inspeção estática

1. O contrato Harness v1.2 declara delegação multiagente fora de escopo. A necessidade nova requer uma alteração explícita desse contrato antes de implementar colaboração coordenada.
2. As configurações de AGENTS.md e skills são de projeto, não um perfil isolado por conversa. A conversa delimita o contexto da tarefa, mas ainda não é uma identidade de agente configurável.
3. A filtragem do contexto mantém instruções do projeto e skills habilitadas, mas não há snapshot imutável do conteúdo de instruções/skills anexado à tarefa. Ao retomar uma tarefa, o contexto é reconstruído com a configuração atual.
4. Os registros da tarefa 13 provam conclusão técnica do arquivo, mas não provam que uma skill específica estava habilitada nem que foi aplicada. A resposta criada é um único parágrafo, sem hierarquia Markdown.
5. A escrita de arquivos atual é textual. Não há fluxo comprovado de geração binária e validação de PDF, XLSX ou PPTX.
6. Busca e leitura web existem, mas falta comprovar o fluxo ponta a ponta que salva fontes, associa citações às afirmações e entrega um artefato com referências verificáveis.
7. O terminal é propositalmente limitado; o fluxo de criação de sites ainda precisa de uma ferramenta de validação de projeto e de uma política explícita para instalação de dependências e execução de builds.
8. A inspeção remota do código não executou a suíte completa nem o ambiente local com Ollama. Portanto, não se declara validação end-to-end adicional nesta auditoria.

## 3. Decisões arquiteturais propostas

### 3.1 Agente é um perfil de execução ligado a uma conversa

- Cada conversa de um projeto pode representar um agente configurado, com nome, função, instruções, skills habilitadas e modelo selecionado.
- Um projeto pode conter várias conversas/agentes: por exemplo, Arquiteto, Designer, Frontend, Backend e QA.
- O agente não recebe permissões por causa do nome, da função, de AGENTS.md ou de uma skill. O Core calcula as permissões a partir das políticas das ferramentas.
- O usuário pode abrir uma conversa existente, renomeá-la/configurá-la como agente ou criar outra conversa no mesmo projeto.
- O workspace do projeto é compartilhado para colaboração; contexto de conversa, instruções específicas, skills selecionadas e histórico continuam isolados por conversa.

### 3.2 Colaboração limitada, não swarm irrestrito

A primeira versão da colaboração será **sequencial e coordenada pelo Core**, sem executar agentes em paralelo. Um plano principal pode definir subtarefas atribuídas a conversas/agentes específicos, dependências, arquivos esperados e critérios de aceite. Cada subtarefa continua sendo uma Task normal, com seu próprio contexto e trilha de execução.

Exemplo de ciclo de criação de site:

1. Arquiteto define requisitos, rotas, contrato de API e critérios de aceite.
2. Designer produz sistema visual e especificação de componentes.
3. Frontend implementa as telas e integração contratada.
4. Backend implementa API, validação e persistência.
5. Integrador verifica compatibilidade e ajusta a ligação entre as partes.
6. QA executa os testes/builds permitidos e registra defeitos.
7. O coordenador apresenta a prévia dos resultados, os arquivos e os testes; o usuário decide sobre ações externas ou publicação.

O Core não deve fingir que são agentes separados se apenas renomeou etapas do mesmo prompt. Cada subtarefa deve registrar a conversa/perfil utilizado, entradas, saídas e validação. A execução paralela só deve ser considerada depois de resolver conflitos de escrita, isolamento de branches/worktrees e cancelamento.

### 3.3 Persistência sem infraestrutura prematura

- Reutilizar `Conversation`, `Task.plan`, `Project.state`, `ToolCall`, `ToolResult`, `Artifact` e o workspace existentes.
- Proposta inicial: manter a biblioteca de skills compartilhadas no projeto e guardar a seleção/configuração de agente associada ao ID da conversa em estado JSON existente, evitando nova tabela na primeira fase.
- Ao iniciar uma tarefa, congelar no plano persistido um snapshot de perfil e skills selecionadas (conteúdo ou referência imutável + hash, conforme os limites definidos na implementação). A retomada deve usar o mesmo snapshot, não mudar silenciosamente no meio da tarefa.
- O plano principal registra as subtarefas, dependências e resultados; cada subtarefa é uma Task existente, associada à sua conversa.
- Não adicionar tabelas, filas, microserviços, Redis, Kafka ou banco vetorial sem demonstrar que o armazenamento existente não atende e obter aprovação arquitetural.

### 3.4 Skills e AGENTS.md

- `AGENTS.md` continua sendo orientação de projeto, com tamanho limitado e tratamento como conteúdo não confiável.
- Skills são instruções reutilizáveis versionadas pelo usuário; devem poder ser habilitadas/desabilitadas por agente e, quando necessário, por tarefa.
- Skill nunca concede ferramenta, permissão ou aprovação.
- O contexto deve indicar quais skills foram realmente incluídas na requisição ao modelo (nome, versão/hash e tamanho), sem registrar desnecessariamente o texto integral.
- O Core deve reservar orçamento de contexto para objetivo, plano, evidências, AGENTS.md e skills; não pode truncar silenciosamente a skill ativa e continuar alegando que ela foi aplicada integralmente.
- Uma alteração de configuração durante uma tarefa passa a valer para novas tarefas; tarefas em andamento continuam com seu snapshot, salvo ação explícita do usuário para atualizar o contexto.

### 3.5 Ferramentas de artefatos

Implementar um serviço comum de criação/validação e ferramentas específicas, registradas no catálogo:

- `pdf_create`: documento estruturado com título, seções, parágrafos, listas, tabelas e referências; gera PDF com paginação, margens, cabeçalho/rodapé e metadados.
- `spreadsheet_create`: workbook XLSX com abas, cabeçalhos, tipos, formatos, fórmulas e larguras; valida arquivo reaberto, nomes de abas, dimensões e fórmulas permitidas.
- `presentation_create`: PPTX com tema consistente, títulos, texto, listas, tabelas/gráficos quando suportados e notas/fontes; valida que o arquivo possa ser reaberto e que os slides esperados existam.
- `artifact_validate`: verifica existência, tamanho, formato, estrutura mínima e consistência com o plano. Deve devolver erros concretos, não apenas “arquivo existe”.

Dependências candidatas: ReportLab para PDF, openpyxl para XLSX e python-pptx para PPTX. Confirmar compatibilidade e custo de instalação no ambiente alvo antes de adicioná-las a `requirements.txt`. Os arquivos binários são gerados por bibliotecas confiáveis, não por texto inventado ou comandos arbitrários do modelo.

Todas as escritas devem usar o workspace do projeto, política de aprovação, limites de tamanho e verificação pós-gravação. O artefato final deve ser listado na API de arquivos e referenciado no resultado da Task.

### 3.6 Pesquisa online e fontes persistidas

- Manter `search` para descoberta e `web_fetch` para leitura segura de uma URL selecionada.
- Normalizar cada fonte: título, URL canônica/final, provedor, data de publicação quando disponível, data/hora de coleta, trecho utilizado e estado de truncamento.
- Tratar páginas e snippets como dados não confiáveis; manter proteção contra SSRF, redirecionamentos inseguros, limites de tamanho e timeout.
- Produzir citações no corpo do documento e uma seção/lista de fontes com URL e data de acesso.
- Quando solicitado, salvar `sources.md` ou `sources.json` no workspace junto ao relatório. A fonte só pode ser citada como lida se `web_fetch` tiver retornado sucesso; resultado de busca sozinho não prova o conteúdo da página.
- A conclusão de pesquisa verifica que as citações do artefato correspondam às fontes efetivamente coletadas.

### 3.7 Qualidade de saída por formato

- Markdown: título, seções, listas/tabelas quando apropriadas, sem transformar toda resposta em um parágrafo único.
- PDF/PPTX/XLSX: conteúdo estruturado, não apenas texto com extensão trocada.
- O Core deve validar a estrutura técnica e o plano deve avaliar a qualidade semântica mínima. A existência do arquivo é necessária, mas não suficiente para declarar qualidade.
- Não exigir formatação elaborada para tarefas que pedem explicitamente texto simples.

## 4. Plano de implementação e critérios de saída

As fases são gates sequenciais. Implementar uma fase por PR, com testes focados, revisão de diff e confirmação antes de iniciar a próxima.

### Fase 0 — Baseline e reconciliação de contrato (atual)

**Objetivo:** registrar o estado real e resolver o conflito entre o contrato atual e a necessidade nova.

- Confirmar a base de código e as ferramentas registradas.
- Documentar o que já existe em AGENTS.md, skills, web e artefatos.
- Propor o perfil de agente por conversa e a colaboração sequencial usando o Task Engine atual.
- Não alterar execução funcional nesta fase.

**Aceite:** plano aprovado pelo Master; lacunas e restrições documentadas. A auditoria atual é estática; suíte completa e teste local com Ollama continuam pendentes.

### Fase 1 — Perfil de agente por conversa + snapshot de skills

- API para ler/atualizar perfil de agente da conversa; defaults herdam configurações do projeto.
- Skills reutilizáveis compartilhadas, seleção por conversa e habilitação por tarefa.
- Snapshot de perfil/skills no plano persistido da Task; reidratação consistente ao retomar.
- Instrumentação mínima: IDs/hash das instruções e skills incluídas em cada solicitação do modelo.
- UI para criar/identificar agentes por conversa, escolher papel e skills e ver o que será aplicado.

**Testes de aceite:** duas conversas no mesmo projeto podem usar instruções/skills diferentes sem vazamento; skill desabilitada não entra no prompt; a habilitada entra em cada inferência relevante; retomada usa o snapshot original; skill não pode autorizar ferramenta.

### Fase 2 — Qualidade de conteúdo e validação de artefatos textuais

- Melhorar o contrato de geração Markdown com instruções de formatação derivadas do pedido.
- Adicionar verificações de estrutura quando a solicitação pede resumo/documento formatado.
- Preservar o fluxo determinístico de leitura → transformação → escrita → verificação.
- Evitar nova chamada ao modelo após artefato validado; permitir revisão quando a validação detectar defeito real.

**Testes de aceite:** pedido de resumo gera título e seções coerentes; pedido de texto simples não é artificialmente expandido; arquivo escrito corresponde byte a byte ao conteúdo validado.

### Fase 3 — PDF profissional

- Implementar `pdf_create` com blocos estruturados, estilos, paginação, cabeçalho/rodapé e tabelas.
- Validar assinatura/formato, páginas e conteúdo extraível.
- Incluir fontes e metadados quando houver pesquisa.

**Testes de aceite:** PDF abre e pode ser extraído; títulos/listas/tabelas são preservados; texto longo pagina corretamente; conteúdo e arquivo persistido correspondem ao pedido.

### Fase 4 — Planilhas XLSX

- Implementar `spreadsheet_create` para múltiplas abas, tipos, estilos, fórmulas e filtros básicos.
- Validar reabertura do arquivo, nomes de abas, dimensões e fórmulas.
- Não executar macros nem fórmulas externas perigosas.

**Testes de aceite:** workbook abre com openpyxl, valores e fórmulas esperados existem, abas e cabeçalhos corretos, arquivo aparece no workspace.

### Fase 5 — Apresentações PPTX

- Implementar `presentation_create` com tema, layouts consistentes, limite de texto por slide e fontes/notas.
- Validar quantidade de slides, títulos e reabertura do arquivo.
- Tratar imagens/gráficos como capacidades explícitas, não como URLs arbitrárias executadas sem validação.

**Testes de aceite:** PPTX reabre, contém a sequência esperada, não gera slides vazios e mantém legibilidade mínima.

### Fase 6 — Pesquisa com fontes salvas

- Fortalecer contratos e testes de `search` e `web_fetch`.
- Criar o fluxo de captura e persistência de fontes e citações.
- Gerar relatório com citações vinculadas a fontes lidas, e salvar o inventário de fontes quando solicitado.

**Testes de aceite:** fonte inacessível não é citada como lida; URLs e datas são preservadas; SSRF/redirects inseguros são rejeitados; fontes citadas no artefato existem no registro salvo.

### Fase 7 — Colaboração entre agentes para criação de sites

- Coordenador transforma o pedido em plano principal com subtarefas e critérios de aceite.
- Atribuição explícita a conversas/agentes de arquitetura, design, frontend, backend, integração e QA.
- Cada subtarefa produz arquivos no workspace comum, declara contratos/arquivos de saída e registra resultado.
- Execução sequencial no MVP; o coordenador verifica dependências e compatibilidade antes de avançar.
- Adicionar ferramenta de validação de projeto com comandos allowlisted (build/test) e saída limitada.
- Instalação de dependências, publicação, deploy, acesso à rede e comandos fora da allowlist exigem política e aprovação explícitas.

**Testes de aceite:** agentes têm contexto isolado; subtarefas dependentes não iniciam antes das entradas necessárias; backend/frontend compartilham contrato explícito; build/teste executa no workspace e o resultado é persistido; falha de um papel impede conclusão falsa do projeto.

### Fase 8 — UI integrada e validação end-to-end

- Interface de agentes/conversas, skills, plano de subtarefas, timeline, aprovações, artefatos e fontes.
- Execução de fluxos reais usando o provider configurado; testes determinísticos com fake provider e smoke test opt-in com Ollama.
- Verificar retomada após reinício, cancelamento, falha de ferramenta e aprovação pendente.

**Testes de aceite:** fluxos de PDF, XLSX, PPTX, pesquisa com fontes e site passam pelo Harness completo; arquivos persistem após reinício; a UI apresenta estado e referências verdadeiros.

## 5. Política de teste e entrega

Para cada PR:

1. Testes unitários da ferramenta/serviço.
2. Testes do Core para permissão, persistência, retomada e falha.
3. Teste do Harness com fake provider para provar a sequência real.
4. Build frontend quando a fase alterar a UI.
5. Smoke test local com Ollama apenas quando o ambiente estiver disponível; identificar explicitamente se não foi executado.
6. Revisão do diff, regressões e compatibilidade do schema.
7. Relatório de arquivos, testes, resultado, limitações e commit.

Não considerar uma ferramenta pronta só porque a classe está registrada. Ela deve ser alcançável pelo modelo, validada pelo Core, executável dentro da política, ter resultado persistido e funcionar no fluxo end-to-end.

## 6. Fora de escopo desta proposta

- Swarms paralelos sem coordenação, execução distribuída ou múltiplos processos autônomos concorrentes.
- Microserviços, filas distribuídas, Redis, Kafka, Kubernetes ou banco vetorial.
- Shell irrestrito, acesso ao sistema de arquivos fora do workspace, execução de scripts de páginas web.
- Publicação/deploy automático sem aprovação.
- Garantia de que um modelo pequeno produza design ou código de qualidade sem validação, testes e possibilidade de revisão.

## 7. Decisão requerida

A aprovação Master deve confirmar:

1. Que o contrato Harness v1.2 pode ser ampliado para **perfis independentes por conversa e colaboração sequencial coordenada**, mantendo o Task Engine único.
2. Que a primeira implementação tentará reutilizar o estado JSON e o plano da Task, sem nova tabela; qualquer limitação concreta deve voltar para decisão antes de ampliar o schema.
3. Que a ordem das fases acima é a ordem oficial, com uma fase por PR e validação entre fases.

Até essa aprovação, esta proposta documenta a arquitetura e a sequência, mas não afirma que as capacidades futuras já foram implementadas.
