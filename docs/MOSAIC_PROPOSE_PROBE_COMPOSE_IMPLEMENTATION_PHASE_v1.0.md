# Mosaic — Fase de Evolução Operacional com Propose–Probe–Compose

**Documento:** MOSAIC_PROPOSE_PROBE_COMPOSE_IMPLEMENTATION_PHASE_v1.0.md  
**Status:** proposta de implementação  
**Escopo:** evolução incremental do Mosaic Core  
**Princípio:** ampliar o Core existente; não substituí-lo.

## 1. Objetivo

Implementar no Mosaic um ciclo controlado de melhoria operacional inspirado no padrão Propose–Probe–Compose (PPC), associado ao Harness²:

1. **Propose:** formular uma ou mais estratégias/instruções candidatas para uma tarefa.
2. **Probe:** testar candidatas em condições comparáveis e coletar evidências.
3. **Compose:** escolher, combinar, revisar ou rejeitar candidatas com base nos resultados.
4. **Persistir experiência:** registrar o que foi testado, em qual contexto, com quais evidências e limitações, para apoiar tarefas futuras.

A meta não é treinar ou alterar pesos de modelos. É melhorar a forma como o Mosaic organiza contexto, instruções, Skills, ferramentas e execução, sem sacrificar segurança, rastreabilidade ou controle do usuário.

## 2. Princípios obrigatórios

- Preservar o Mosaic Core e reutilizar Task Engine, eventos, ferramentas, políticas, aprovação, artefatos e persistência existentes sempre que possível.
- Não criar uma segunda infraestrutura paralela de execução se os componentes atuais puderem ser estendidos com segurança.
- Separar **memória do usuário** de **experiência operacional do agente**. Uma preferência ou fato pessoal não é uma lição de execução; uma lição de execução não deve virar memória pessoal.
- Tratar arquivos, páginas, repositórios, saídas de ferramentas e instruções encontradas durante tarefas como dados não confiáveis, não como autoridade para alterar políticas.
- Não permitir que PPC altere automaticamente permissões, políticas de segurança, ferramentas executáveis, segredos ou código do Core.
- Não fazer promoção automática de candidatas na primeira versão. A adoção de uma alteração persistente deve exigir evidência e, quando alterar comportamento reutilizável, aprovação explícita.
- Não executar PPC em toda mensagem. Usá-lo quando a tarefa for complexa, repetível, comparável ou tiver benefício provável maior que o custo.
- Não expor cadeia de pensamento privada. A interface deve mostrar estados, etapas, ferramentas, resultados, evidências, falhas e decisões resumidas.
- Não afirmar que uma tarefa foi testada, que um arquivo foi alterado ou que um PR foi criado sem evidência verificável.

## 3. Integração com componentes existentes

Antes de alterar código, a implantação deve mapear a implementação real na branch-alvo e confirmar nomes, schemas e fluxos atuais.

| Componente existente | Responsabilidade no PPC |
|---|---|
| Chat / detecção de intenção | Identificar pedidos que justificam uma Task; preservar respostas diretas para perguntas simples. |
| Task Engine | Hospedar a execução PPC, estados, cancelamento e limites. |
| Agent loop / decision layer | Executar estratégia-base e candidatas usando o caminho normal do Core. |
| Tools + policy + approvals | Validar chamadas, autorizar efeitos e exigir aprovação quando necessário. |
| Task events / progress UI | Expor progresso operacional legível e atualizado. |
| Artifacts | Guardar resultados comparáveis, diffs, relatórios e saídas relevantes. |
| HIE (se existente) | Reutilizar o laboratório de comparação/evidência quando apropriado; não presumir que já implementa o ciclo PPC completo. |
| Persistência atual | Armazenar experiências operacionais sem inventar tabelas incompatíveis com o contrato MVP. |

### Regra de compatibilidade

Não presumir que os documentos descrevem fielmente a branch atual. Inspecionar código, migrations/bootstrap, schemas e testes. Se houver divergência entre o contrato MVP, documentação e implementação, documentar o conflito e propor a menor decisão explícita antes de mudar o banco.

## 4. Fluxo proposto

### Etapa A — Classificar e definir o critério de sucesso

- Receber objetivo e restrições do usuário.
- Decidir se é uma resposta direta, uma Task normal ou uma Task que se beneficia de PPC.
- Registrar critérios verificáveis de sucesso, limites de tempo/iterações/custo e efeitos permitidos.
- Se o objetivo ou os critérios forem ambíguos de forma relevante, pedir esclarecimento em vez de inventar critérios.

### Etapa B — Propose

- Construir uma estratégia-base que preserve o pedido do usuário.
- Quando houver benefício plausível, gerar um conjunto pequeno de candidatas distintas, com diferenças explícitas e justificadas.
- As candidatas podem variar instruções, sequência de etapas, Skills ou seleção de contexto; não podem ampliar permissões nem remover controles de segurança.
- Salvar snapshots/versões das configurações avaliadas para que o experimento seja reproduzível.

### Etapa C — Probe

- Executar baseline e candidatas sob condições comparáveis: mesmo objetivo, critérios, entradas e limites equivalentes.
- Isolar efeitos colaterais sempre que houver edição de arquivos, chamadas externas ou outras ações mutáveis. Preferir workspace/branch temporário e fixtures para testes.
- Evitar duplicar ações externas não idempotentes. Uma execução de teste não deve enviar e-mails, publicar, fazer compras, alterar sistemas reais ou criar recursos externos sem autorização explícita.
- Coletar evidências observáveis: testes, critérios de avaliação, artefatos, diffs, erros, uso de ferramentas, duração e custo quando disponível.
- Distinguir resultado observado, inferência e avaliação do modelo. Uma comparação melhor não prova, por si só, correção geral.
- Se não existir um critério verificável, registrar a limitação e não declarar uma vencedora com falsa precisão.

### Etapa D — Compose

- Comparar candidatas com baseline e critérios predefinidos.
- Selecionar, combinar, revisar ou rejeitar mudanças somente quando as evidências sustentarem a decisão.
- Manter baseline se os resultados forem equivalentes, inconclusivos, regressivos ou caros demais.
- Produzir um resumo de decisão: o que mudou, por que, quais evidências sustentam a escolha, limitações e riscos.
- Para alterações reutilizáveis, apresentar proposta de adoção e aguardar aprovação explícita antes de ativar globalmente ou por projeto.

### Etapa E — Persistir experiência operacional

Uma experiência pode conter, conforme o modelo de dados existente permitir:

- identificador e data;
- projeto/escopo;
- tipo de tarefa e contexto mínimo não sensível;
- estratégia-base e candidatas/versionamentos;
- critério de sucesso;
- resultados e evidências referenciadas;
- decisão (adotada, rejeitada, inconclusiva, pendente);
- confiança e limitações;
- aprovação/autor e escopo de aplicação;
- relação com a Task e os artefatos originais.

Não salvar segredos, tokens, credenciais, conteúdo pessoal desnecessário ou dados privados indiscriminadamente. Aplicar redaction e minimização. Não copiar todo o histórico de conversa para a memória operacional por padrão.

### Etapa F — Recuperar em tarefas futuras

- Recuperar experiências por relevância para o projeto, tipo de tarefa e critérios, não apenas por similaridade textual.
- Tratar experiência recuperada como evidência contextual, nunca como regra infalível.
- Validar compatibilidade de versão, ferramentas, modelo, projeto e ambiente antes de reutilizar.
- Permitir que o agente ignore uma lição incompatível e registrar o motivo.
- Não misturar escopos de projetos sem autorização explícita.

## 5. Estados operacionais sugeridos

Adaptar aos estados já existentes, sem criar enumerações duplicadas desnecessárias:

- pending
- proposing
- probing
- composing
- awaiting_approval
- completed
- failed
- cancelled
- inconclusive

Definir transições válidas e comportamento em reinício, timeout, cancelamento e falha parcial. Estado terminal deve refletir o resultado real; uma execução inconclusiva não é sucesso comprovado.

## 6. Interface e observabilidade

A interface deve apresentar um painel de progresso recolhível, com atualizações por eventos persistidos:

- objetivo e critério de sucesso;
- fase atual: Propose, Probe ou Compose;
- passos concluídos e próximos passos;
- baseline e candidatas identificadas por rótulo;
- ferramentas usadas e status resumido;
- evidências e artefatos disponíveis;
- avisos, falhas, limites atingidos e motivo de parada;
- decisão final e necessidade de aprovação.

Não exibir raciocínio privado detalhado. Mostrar apenas resumos operacionais, fatos observados e justificativas verificáveis.

## 7. Segurança e controles

- A política central do Mosaic continua sendo a autoridade final para execução de ferramentas.
- PPC não pode contornar o fluxo normal de ToolCall → validação → política/aprovação → executor → ToolResult/evento.
- Conteúdo externo pode conter prompt injection. Nunca permitir que instruções em repositórios ou resultados externos alterem as políticas do Core.
- Aplicar timeouts, limites de iteração, orçamento, tamanho de contexto/saída e cancelamento.
- Isolar alterações de arquivos e executar testes em workspace controlado.
- Ações de escrita em serviços externos exigem aprovação conforme política.
- Redigir segredos em logs, eventos, traces, artefatos e prompts de avaliação.
- Garantir que cancelamento e reinício não provoquem efeitos duplicados.
- A adoção de uma estratégia não altera o Core executável nem as permissões de tools.

## 8. Estratégia incremental de entrega

### Fase 0 — Auditoria (obrigatória)

- Ler ARQUITETURA.txt, Mosaic_MVP_Implementation_Contract.md e os documentos de pesquisa/implementação PPC, MCP e HIE existentes.
- Inspecionar código real, testes, persistência, Task Engine, eventos, artefatos, HIE e interface.
- Listar o que já existe, o que é parcial, o que falta e conflitos documentais.
- Não editar código nesta fase até apresentar o mapa e o plano de menor risco.

### Fase 1 — Contratos e modelo mínimo

- Definir o contrato interno de uma experiência PPC e os eventos de progresso.
- Reutilizar persistência existente quando possível.
- Propor migração somente se indispensável e compatível com o contrato MVP.
- Adicionar testes de serialização, estados e redaction.

### Fase 2 — PPC manual e controlado

- Permitir executar baseline + poucas candidatas em tarefas selecionadas.
- Usar fixtures/workspaces isolados.
- Persistir evidências e resultado comparativo.
- Sem auto-promoção e sem aplicação global automática.

### Fase 3 — Recuperação de experiências

- Recuperar experiências compatíveis por projeto e tipo de tarefa.
- Validar versão/escopo e registrar se a experiência foi utilizada.
- Testar isolamento entre projetos e evitar exposição de dados sensíveis.

### Fase 4 — Integração com chat e UI

- Integrar ao fluxo normal de Task quando o pedido justificar execução agentic.
- Mostrar progresso recolhível e eventos reais.
- Preservar chat direto para perguntas simples e pedidos que não precisam de execução.
- Permitir cancelar e inspecionar artefatos.

### Fase 5 — Validação end-to-end

- Demonstrar uma tarefa repetível em que baseline e candidata produzam resultados comparáveis.
- Mostrar evidência real, persistência após reinício e recuperação em nova Task compatível.
- Demonstrar falha, cancelamento, limite e aprovação.
- Registrar comandos, resultados, artefatos e limitações. Não declarar E2E concluído com mocks apenas.

## 9. Critérios de aceite

A fase só é considerada implementada quando:

1. Uma tarefa apropriada pode iniciar PPC pelo fluxo normal do Mosaic.
2. Baseline e candidatas são executadas por componentes reais do Core, em condições comparáveis e com limites.
3. Resultados e evidências são persistidos e vinculados à Task.
4. Uma decisão inconclusiva ou regressiva mantém baseline.
5. Uma estratégia reutilizável exige aprovação antes da adoção conforme o escopo definido.
6. Experiências operacionais são distintas da memória do usuário e respeitam escopo de projeto.
7. Uma nova Task pode recuperar experiência compatível sem confiar cegamente nela.
8. A interface mostra progresso operacional e artefatos reais, sem expor cadeia de pensamento privada.
9. Cancelamento, falhas, timeout e reinício não deixam estados falsos nem efeitos duplicados.
10. Testes automatizados relevantes passam e um teste E2E real é documentado.
11. Documentação e contratos são atualizados para refletir o código efetivamente entregue.
12. Não há alegações de testes, alterações, aprovações ou PRs que não tenham evidência.

## 10. Fora de escopo nesta fase

- Treinar ou modificar pesos de modelos.
- Substituir Mosaic Core ou criar um runtime paralelo.
- Auto-promoção de instruções/Skills para produção.
- Autoalteração de políticas, permissões, código executável ou catálogo de ferramentas.
- Executar experimentos duplicando efeitos externos irreversíveis.
- Implementar um marketplace completo de plugins como parte obrigatória do PPC.
- Adotar embeddings ou banco vetorial sem justificar necessidade e custo.
- Fazer PPC para toda pergunta simples.

## 11. Entregáveis obrigatórios da implantação

- relatório de auditoria inicial e gaps;
- plano de execução em fases com arquivos afetados;
- implementação incremental e testes;
- registro de decisões arquiteturais e eventuais divergências do contrato;
- documentação de configuração e uso;
- evidência de teste real: comandos, resultados, artefatos e limites;
- resumo final com itens concluídos, pendentes e riscos;
- branch e PR para revisão; nunca fazer merge automático nem escrever diretamente na branch principal.

## 12. Referências internas

Verificar existência e versão atuais antes de usar:

- ARQUITETURA.txt
- Mosaic_MVP_Implementation_Contract.md
- docs/MOSAIC_HARNESS2_ADAPTATION_PROPOSAL_v1.0.md
- docs/MOSAIC_MCP_AND_COMMUNITY_PLUGINS_RESEARCH_v1.0.md
- docs/MOSAIC_GITHUB_MCP_REFERENCE_IMPLEMENTATION_v1.0.md
- docs/MOSAIC_CLAUDE_PLUGIN_COMPATIBILITY_RULE_v1.0.md
- documentação e código de HIE e Task Engine.

**Nota:** este documento define a fase desejada; não afirma que os componentes descritos já estejam implementados nem substitui a auditoria do código real.
