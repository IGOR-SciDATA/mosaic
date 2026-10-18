# MOSAIC — Sequência Mestre de Implementação por Fases

**Versão:** 1.0  
**Data:** 2026-10-18  
**Autoridade:** MASTER  
**Aplicação:** sequência vigente para Chat 01; preserva o Core, o Task Engine e as decisões arquiteturais aprovadas.

> Este documento registra a sequência definida pelo MASTER em 2026-10-18 e prevalece sobre a numeração/ordem das fases em planos e roadmaps anteriores. Os documentos anteriores continuam úteis para detalhes técnicos quando não houver conflito. Uma autorização explícita para executar a sequência completa permite avançar fase a fase sem nova confirmação intermediária; não permite ignorar critérios de aceite ou inventar decisões arquiteturais.

## Princípios invariáveis

- `MODEL ≠ ACCESS`
- `MEMORY ≠ TRUTH`
- `HISTORY ≠ MODEL MEMORY`
- `CONTEXT ≠ FULL HISTORY`
- `TOOL CALL ≠ TOOL EXECUTION`
- `SKILL ≠ PERMISSION`
- `TASK = GENERAL UNIT OF WORK`
- `HARNESS ≠ SECOND CORE`
- `MOSAIC OWNS STATE`
- `VERIFICATION ≠ MODEL ASSERTION`

O Core é dono de estado, política, permissões, execução e conclusão. Reutilizar o Task Engine, Harness, Context Manager, persistência, eventos e registro de ferramentas. O modelo da conversa deve ser respeitado sem roteamento automático ou fallback silencioso. Não adicionar tabelas, dependências ou infraestrutura sem necessidade demonstrada e contrato compatível.

## Protocolo para cada fase

1. Inspecionar o código e os contratos relevantes.
2. Identificar o problema concreto e as evidências.
3. Definir escopo mínimo, arquivos e critérios de aceite.
4. Implementar somente o escopo da fase.
5. Executar testes e comandos aplicáveis.
6. Verificar runtime e artefatos quando aplicável.
7. Revisar segurança, estados, regressões e documentação.
8. Registrar comandos, resultados, falhas e limitações.
9. Não declarar conclusão sem evidência.

## Fases e critérios de aceite

### Fase 0 — Auditoria e baseline
Inspecionar branches, commits, PRs, contratos, schema, Task, ToolCall, ToolResult, Artifact, Setting, `task_events` e `_mosaic_meta`. Executar suíte backend, build frontend, smoke tests disponíveis e fluxo integrado. Reconciliar schema conforme contrato MVP e decisão aprovada, preservando dados e tabelas internas.

**Aceite:** baseline com comandos reais, resultados, lacunas e plano da fase seguinte; testes não executados permanecem explicitamente pendentes.

### Fase 1 — Preservar e automatizar o fluxo Markdown
Automatizar o cenário de leitura de um `.md`, resumo, criação de outro `.md`, releitura do artefato e validação de conteúdo. Distinguir callback determinístico de teste de execução real de provider.

**Aceite:** regressão reproduzível cobrindo leitura, escrita aprovada, releitura e critérios mínimos de conteúdo.

### Fase 2 — Segurança e consistência de estado
Validar permissões no backend, isolamento do workspace, limites de ferramentas e transições de Task, Action, ToolCall e ToolResult. Tratar falhas, cancelamento e efeitos colaterais sem sucesso declarado pelo modelo/UI.

**Aceite:** testes para caminhos permitidos, bloqueados e falhos, com estados finais coerentes.

### Fase 3 — Harness integrado
Comprovar o ciclo pedido → contexto → decisão estruturada → política → ferramenta → resultado → observação → próxima etapa, respeitando o modelo selecionado na conversa.

**Aceite:** fluxo integrado executado, com resultados reais e sem chamadas repetidas sem necessidade.

### Fase 4 — Eventos, aprovação, cancelamento e retomada
Reutilizar eventos persistidos, registrar transições e decisões, reconectar por cursor e retomar Tasks sem duplicar efeitos colaterais.

**Aceite:** eventos coerentes com o estado oficial e retomada demonstrada nos cenários aplicáveis.

### Fase 5 — Observabilidade e autoverificação
Registrar fatos operacionais correlacionados, duração, erros, códigos de saída e métricas disponíveis. Priorizar validadores determinísticos, critérios prévios, evidências com hash/versão e correções limitadas. Não registrar chain-of-thought, credenciais ou segredos.

**Aceite:** sucesso e falhas induzidas demonstrados, verificações registradas e limites de tentativa/custo respeitados.

### Fase 6 — Contexto, memória e continuidade
Recuperar contexto relevante por projeto, conversa e tarefa; distinguir histórico, memória, estado e conhecimento com proveniência; controlar orçamento de contexto e preservar decisões, arquivos, fontes e próximos passos.

**Aceite:** recuperação contextual demonstrada com referências de origem.

### Fase 7 — Perfis especializados e coordenação
Usar perfis de arquitetura, backend, frontend, pesquisa, documentação e QA quando úteis, no mesmo Core e Task Engine. Começar sequencialmente com subtarefas persistidas, dependências, entradas, saídas e critérios de aceite.

**Aceite:** tarefa composta com pelo menos três subtarefas dependentes, resultados persistidos e integração verificada.

### Fase 8 — Ferramentas gerais e pesquisa
Auditar as ferramentas existentes; completar pesquisa web com fontes realmente acessadas e referências rastreáveis; revisar a ferramenta de clima existente e tratar ambiguidades, erros e indisponibilidade sem inventar resultados.

**Aceite:** ferramentas executadas no fluxo real, com resultados e evidências verificáveis.

### Fase 9 — Artefatos profissionais
Gerar e validar Markdown, PDF, DOCX, XLSX e PPTX. Reabrir cada arquivo e validar estrutura e conteúdo. Para software, executar testes, build e integração aplicáveis.

**Aceite:** artefatos reais gerados, reabertos e verificados.

### Fase 10 — Identidade brasileira e interface
Preservar identidade visual tecnológica brasileira; implementar tema claro/escuro com tokens semânticos e preferência persistida pelo mecanismo aprovado. Expor Tasks, etapas, aprovações, evidências, falhas e artefatos sem progresso fictício.

**Aceite:** estados reais visíveis, temas funcionais e acessibilidade verificada.

### Fase 11 — Investigação de acesso a modelos via web
Investigar alternativas autorizadas para aproveitar acesso web do usuário. Avaliar viabilidade, termos, segurança, persistência e limites. Não presumir que URL de conversa permita ler ou continuar sessão; não armazenar cookies/credenciais em texto aberto nem contornar proteções.

**Aceite:** relatório de alternativas e riscos. Integração funcional exige autorização explícita separada.

### Fase 12 — Avaliação ponta a ponta e autonomia limitada
Criar cenários reproduzíveis por família; medir sucesso, falhas, tentativas, duração e consumo disponível; avaliar redução de retrabalho; verificar regressões, recuperação, limites e efeitos colaterais. Ampliar autonomia somente com evidências.

**Aceite:** matriz de capacidades com estados comprovados e limitações explícitas.

## Estados oficiais de progresso

- **Planejado:** requisito definido, sem implementação comprovada.
- **Presente no código:** implementação identificada, comportamento ainda não comprovado.
- **Testado:** comando/teste executado e resultado registrado.
- **Validado ponta a ponta:** fluxo real executado e critérios de aceite verificados.
- **Demonstrado manualmente:** execução reportada pelo usuário, sem presumir cobertura automatizada.

## Critérios gerais de economia e confiabilidade

Antes de chamar o modelo novamente, verificar se código convencional resolve a checagem. Corrigir localmente e repetir apenas verificações afetadas quando seguro. Não repetir operações com efeitos colaterais sem idempotência ou autorização. Não prometer economia de tokens sem medi-la.


## Aditivo do MASTER — biblioteca de agentes e providers (2026-10-18)

Este aditivo amplia a sequência vigente sem autorizar uma reescrita do Core.

### Fase 13 — Provider oficial via API
- Auditar o factory/registry e a interface `ModelProvider` atual.
- Preservar Ollama e acrescentar primeiro um provider de API oficial/documentada.
- Guardar credenciais apenas no backend por mecanismo seguro; nunca expor chave no frontend/logs.
- Respeitar seleção explícita do modelo/provider, timeout, limites, erros e custos; sem fallback silencioso.
- Aceite: testes de seleção, modelo desabilitado, provider desconhecido, timeout, erro de credencial e regressão Ollama. Smoke test real só quando houver credencial fornecida pelo usuário.

### Fase 14 — Biblioteca de agentes reutilizáveis por projeto
- Usuário cria/lista/edita/remove agentes em um projeto; cada perfil tem slug único, descrição, instruções e Skills versionadas.
- Invocação via `/slug` em qualquer conversa/tarefa do mesmo projeto; ativa o perfil na execução atual, sem criar outra conversa automaticamente.
- Reutilizar `Project.state` e estruturas existentes se forem suficientes; nenhuma tabela nova sem evidência e aprovação de schema.
- Persistir snapshot imutável/verificável do perfil e Skills na Task; retomada usa o snapshot original.
- Aceite: duas conversas no mesmo projeto usam o mesmo agente; projetos diferentes permanecem isolados; edição do perfil não altera Task já iniciada; comandos desconhecidos falham claramente.

### Fase 15 — WebChat adapter para aplicação própria/autorizada
- Criar um adaptador de navegador separado do provider de API, usando o contrato de execução comum sempre que adequado.
- Permitir configurar URL e seletores estáveis da aplicação controlada/autorizada pelo usuário.
- Usar perfil de navegador dedicado e persistente, com login manual do usuário; não copiar cookies/senhas do perfil pessoal padrão.
- Tratar sessão expirada, timeout, resposta vazia/incompleta, falha de seletor, rede, cancelamento e profile lock.
- Nunca automatizar chats de consumo de terceiros sem autorização documentada, nem contornar MFA/CAPTCHA, limites ou controles de acesso.
- Aceite: teste end-to-end contra chat próprio de demonstração, reinício com sessão persistida, logout/revogação e verificação de que credenciais não aparecem em logs.

### Fase 16 — Contexto econômico e retomada integrada
- Revisar orçamento por chamada, recuperação seletiva e checkpoint da Task.
- Medir tokens/calls quando o provider disponibilizar métricas; não prometer economia sem medição.
- Testar pausa, reinício, retomada com snapshot de agente/Skills e ausência de efeitos colaterais duplicados.
- Aceite: relatório de antes/depois para consumo mensurável e E2E de retomada com evidências.

As fases 13–16 são incrementais e não devem ser agrupadas em um único PR. Cada fase exige testes, revisão de segurança, documentação do estado real e validação explícita antes da seguinte.
