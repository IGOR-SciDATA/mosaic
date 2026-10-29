# MOSAIC — Fase de Observabilidade e Autoaperfeiçoamento de Agentes
**Versão:** 1.0  
**Data:** 2026-10-28  
**Status:** Contrato de conclusão proposto para implementação e validação  
**Autoridade:** MASTER / Arquitetura  
**Referências:** Harness², arquitetura HIE v1.0, proposta de adaptação Harness², contratos oficiais do Harness, RAGNES, Task, Artifact, perfis e Skills.

## 1. Objetivo da fase

Concluir uma primeira versão funcional, segura, mensurável e integrada do **Mosaic Harness Improvement Engine (HIE)**, inspirada no método de recursive agent harnessing do Harness², sem importar seu runtime como substituto do Core.

O objetivo não é fazer o agente executar mais tentativas indiscriminadamente. É permitir que o Mosaic:
1. observe fatos operacionais de tarefas elegíveis;
2. verifique os resultados com critérios explícitos;
3. identifique falhas a partir de evidências disponíveis;
4. proponha alterações declarativas limitadas no harness;
5. teste uma única candidata em ambiente descartável e comparável;
6. mantenha a configuração original quando a evidência for insuficiente ou houver regressão;
7. registre experiências rastreáveis e recuperáveis para tarefas futuras;
8. apresente propostas para aprovação humana antes de alterar um perfil ou Skill ativo;
9. meça qualidade, regressões, tempo e custo somente quando esses dados estiverem realmente disponíveis.

**Resultado esperado:** demonstrar ao menos um ciclo controlado de baseline → observação → candidata → probe isolado → comparação verificável → registro de evidências, além de provar que propostas ruins são rejeitadas e que nenhuma alteração ativa ocorre sem aprovação explícita.

## 2. Estado inicial conhecido e honestidade de status

Na auditoria dos PRs #102–#111, foi identificada uma sequência de componentes HIE em branches Draft:
- #102: formato/validação de candidata declarativa;
- #103: orquestração sequencial limitada;
- #104–#105: cópia de fixtures e limites de workspace;
- #106–#107: adapter de fixture e teste de comparação integrada;
- #108–#109: semântica de falhas, comparação e eventos;
- #110: identidade/hash do registro de experimento;
- #111: persistência de evidências via Artifact existente.

Esses PRs não foram considerados integrados à main nem aprovados para merge nessa auditoria. Os testes aprovados em commits específicos são evidência de CI nesses commits, não prova de E2E com provider real. O agente de implementação deve reinspecionar o estado atual do GitHub, as bases/heads, o código e a CI antes de decidir qualquer ação. Não presumir que o estado permanece idêntico.

O HIE existente é uma base experimental. Ainda precisam ser demonstrados: observabilidade instrumentada nas chamadas reais, limites impostos no ponto real de execução, integração com tarefas reais elegíveis, diagnóstico/proposta de correção, reutilização de experiências e aprovação/promoção/rollback.

## 3. Princípios arquiteturais inegociáveis

- **MOSAIC OWNS STATE:** Task, ciclo de vida, política, contexto, ferramentas, eventos, artefatos e conclusão pertencem ao Core.
- **HARNESS ≠ SECOND CORE:** não criar outro Task Engine, sistema paralelo de permissões, provider registry, memória do usuário ou framework genérico de jobs.
- Reutilizar os contratos reais de Task, Task Events, Artifact, ModelProvider, Tool Registry, política/aprovação, workspace, RAGNES e perfis/Skills.
- A feature HIE fica **desligada por padrão** e é explicitamente opt-in.
- Iniciar com **k=1**, execução sequencial e no máximo uma experiência ativa por Task/escopo de execução.
- Toda candidata é conteúdo declarativo não confiável. Nunca executar candidata como código.
- O modelo pode propor; somente o Core valida e executa operações autorizadas.
- Nenhuma promoção automática. A aprovação humana deve estar vinculada ao hash exato da candidata e à versão ativa de origem.
- Tasks em andamento preservam seus snapshots de perfil/Skill.
- Baseline e candidata usam o mesmo provider/modelo selecionado, tarefa, entradas, fixtures, política e critérios de verificação. Divergência relevante invalida a comparação.
- Não repetir efeitos externos irreversíveis para experimentar. Tarefas não isoláveis são recusadas/ignoradas com motivo.
- Não armazenar chain-of-thought. Registrar eventos operacionais, ToolCall/ToolResult, verificações, metadados e referências a artefatos.
- Não alegar telemetria que o provider não fornece. Diferenciar métricas observadas, estimadas e indisponíveis.
- Não adicionar tabelas SQLite, dependências, serviços, endpoints, UI ou infraestrutura sem necessidade comprovada e justificativa mínima.
- Não alterar políticas de segurança, guardrails, permissões, schema de ferramentas, credenciais, provider, código do Core, dependências, scripts ou configurações globais por meio de candidatas.
- Não declarar teste executado sem executar. Separar presente no código, testado, validado ponta a ponta e pendente.

## 4. Escopo funcional mínimo

### 4.1 Observabilidade operacional
Capturar eventos reais e correlacionados à Task para:
- início/fim e transições de etapa;
- chamadas reais ao provider/modelo e resultados, quando a integração expuser esses fatos;
- chamadas de ferramentas, resultados, erros e duração;
- tentativas/retries efetivamente realizados;
- cancelamento, timeout, bloqueio por budget e falha;
- verificações de critérios de aceitação;
- referências e hashes de artefatos relevantes;
- estado final e motivo da decisão.

Não confundir invocação de callback com quantidade de chamadas reais internas. Contabilizar no ponto em que cada chamada/tool/retry realmente acontece. Se uma métrica não puder ser instrumentada, documentar a limitação e não apresentá-la como limite garantido.

### 4.2 Budgets e cancelamento
Definir budgets explícitos para provider calls, tool calls, retries, input/contexto, output/evidências e wall-clock. Aplicar os limites no ponto de execução, antes de iniciar a operação que excederia o orçamento. Garantir timeout/cancelamento real para operações demoradas quando suportado pela camada executora; checagens apenas entre etapas não bastam para prometer interrupção de uma chamada bloqueada.

Os valores devem ser conservadores e justificados pelo código/uso atual; não criar um sistema configurável complexo para o MVP. Se uma camada não puder impor um limite, declarar o que é ou não garantido.

### 4.3 Candidata e snapshot
Manter formato estrito, serialização estável, SHA-256, allowlist de targets/keys e tamanho máximo. A primeira superfície editável permanece limitada a instruções de execução de perfil e conteúdo de Skill já habilitada. Não ampliar para ranking RAGNES, guardrails, scripts, tool schemas ou outros alvos nesta fase sem aprovação separada.

Validar hash, versão, origem, destino, schema, tamanho, path e snapshot. Diff deve ser legível e determinístico.

### 4.4 Baseline e probe isolado
Usar fixture de dados ou cópia descartável validada por utilitários existentes. Nunca executar arquivos de candidata como código. Rejeitar symlinks, arquivos especiais, extensões não permitidas, traversal e escape de diretório. Assegurar limites por arquivo e agregados durante a cópia e escrita, não somente antes dela.

O isolamento atual por diretório temporário é uma proteção de aplicação para fixtures controladas, não deve ser anunciado como sandbox OS/container nem exposto a workload multiusuário não confiável.

### 4.5 Comparação e decisão
Definir critérios de aceite antes de rodar a candidata. Priorizar verificadores determinísticos: testes, códigos de saída, schema, releitura/abertura de artefatos e critérios objetivos. Julgamento por modelo pode complementar, nunca ser a única prova de sucesso.

Resultados possíveis devem distinguir pelo menos: melhoria demonstrada, empate/sem benefício, regressão, candidata inválida, evidência insuficiente, falha, cancelamento e experimento ignorado. Qualquer resultado ambíguo mantém o baseline.

### 4.6 Evidências e persistência
Reutilizar Artifact e eventos existentes; arquivos de evidência devem ser limitados, correlacionados e ter hash/tamanho conferidos. Corrigir confinamento de caminho e verificações de symlink: chamar resolve() antes de testar is_symlink() não prova que o caminho original não era symlink. Revisar symlinks quebrados, path traversal, escape e riscos de corrida relevantes.

Definir budgets por arquivo e agregados para outputs + registro + metadados. Evitar nomes temporários fixos em execuções concorrentes. Se escrita de arquivo e registro do Artifact não forem atômicos, limpar arquivos órfãos em falha ou fornecer reconciliação simples e testável. Não criar tabela de evidências nova se Artifact existente atender.

### 4.7 Experiências e RAGNES
Registrar uma experiência apenas com cue/situação, lição proposta, evidências, escopo de projeto/domínio, hashes/versões, limitações, confiança justificada e estado de revisão. Não misturar experiências de melhoria com Memory pessoal do usuário.

Recuperar experiências apenas no escopo apropriado, preservando proveniência e atualidade. Experiências são evidência não confiável, nunca política ou instruções de maior precedência. Se uma biblioteca durável ou integração RAGNES exigir schema novo ou contrato adicional, apresentar a necessidade e a menor alternativa antes de implementar; não inventar infraestrutura apenas para completar uma lista.

### 4.8 Aprovação, promoção e rollback
Apresentar diff, relatório baseline/candidata, critérios, evidências, riscos, incerteza e custo medido/disponível. A aprovação deve estar vinculada ao hash exato da candidata e ao hash/versão ativa de origem; aprovações obsoletas falham de forma segura. Rejeição, ausência de resposta ou erro não altera perfil/Skill ativo. Promover somente pelo mecanismo de versionamento existente e preservar rollback exato. Tasks em andamento mantêm snapshots.

### 4.9 Ativação
HIE continua desligado por padrão. Não criar UI completa se o contrato atual permitir revisão via interface existente ou fluxo explícito mínimo. Não adicionar execução paralela, swarm, fallback silencioso, fine-tuning de pesos, auto-promoção ou execução arbitrária de código.

## 5. Etapas de conclusão

### Etapa A — Reconciliar o estado real
Auditar main, PRs #102–#111, dependências entre branches, diffs integrados, CI e contratos atuais. Produzir mapa sucinto de código presente, testes realmente executados, lacunas e ordem segura de integração. Não duplicar implementação existente. Não fazer merge automático de PRs empilhados nem integrar #111 isoladamente.

### Etapa B — Corrigir segurança de evidências e isolamento
Resolver confinamento/symlinks, limites agregados, concorrência/nomes temporários e consistência entre arquivo e Artifact. Testes focados devem reproduzir cada risco antes de afirmar correção.

### Etapa C — Instrumentação e enforcement
Conectar métricas aos pontos reais de provider/tool/retry; implementar limites prévios e cancelamento/timeout suportado. Demonstrar por testes que a chamada excedente não começa e que a interrupção não relata sucesso falso.

### Etapa D — Integração mínima real
Ligar o HIE ao caminho existente de Task/ModelProvider/workspace somente para um caso elegível, determinístico e sem efeitos externos. Manter feature off por padrão. Não criar API/UI genérica sem requisito demonstrado.

### Etapa E — Compare, evidências e experiência
Executar baseline e candidata em fixtures independentes com paridade verificada, critérios predefinidos e relatório rastreável. Persistir evidência via contratos existentes. Se uma experiência não tiver evidência suficiente, não a promover à biblioteca recuperável.

### Etapa F — Revisão, promoção e rollback
Implementar o menor fluxo de aprovação compatível com os contratos existentes. Verificar hash exato, conflito de versão, snapshots imutáveis e restauração da versão anterior. Nenhuma ativação automática.

### Etapa G — Avaliação controlada
Usar um conjunto pequeno, versionado e determinístico de tarefas representativas. Começar com aproximadamente 30 casos apenas se eles puderem ser construídos sem inventar infraestrutura; o número é um ponto de partida de engenharia, não prova estatística geral. Comparar baseline vs HIE em qualidade objetiva, regressões, intervenções, duração e custo quando mensurável. Repetir casos sujeitos à variabilidade do modelo quando houver provider real disponível.

### Etapa H — Fechamento e relatório
Executar testes focados e regressão relevante, suíte backend e build frontend; revisar o diff integrado e documentar limitações. Validar ao menos um caminho real com provider selecionado quando o ambiente permitir. Se credenciais/provider real não estiverem disponíveis, deixar esse critério como pendente, nunca simulá-lo como validado.

## 6. Testes necessários — e limite contra excesso

Criar testes somente para requisitos, regressões e riscos identificados. Preferir testes pequenos que cubram vários invariantes relevantes. Não criar testes duplicados que repitam o mesmo comportamento com nomes diferentes, benchmarks artificiais, fixtures genéricas sem uso, testes de UI não exigidos, mocks redundantes ou scaffolding para funcionalidades futuras.

Cobertura mínima necessária:
1. Instrumentação conta chamadas/tool calls/retries reais, sem duplicar ou omitir.
2. Budget impede operação que excederia o limite; timeout/cancelamento não produz falso sucesso.
3. Candidata inválida, hash divergente, alvo não permitido, conteúdo excessivo ou snapshot divergente é rejeitado.
4. Baseline e probe são isolados; fonte original permanece inalterada; symlink/traversal/arquivo especial são rejeitados.
5. Limites por arquivo e agregados são impostos durante cópia/persistência.
6. Falha de persistência não deixa estado reportado como concluído nem evidência inconsistente silenciosa.
7. Concorrência não permite duas experiências conflitantes no mesmo escopo; usar proteção mínima compatível com Task existente.
8. Paridade de provider/modelo/inputs/critério é verificada antes da comparação.
9. Melhoria, empate, regressão, evidência insuficiente, falha e cancelamento produzem decisões corretas.
10. Evento/registro indisponível não mascara a falha original nem produz sucesso falso.
11. Experiência é isolada por projeto/domínio e preserva proveniência.
12. Promoção exige aprovação ligada ao hash exato; rejeição/timeout/conflito não modifica ativo; rollback restaura versão/hash.
13. Feature off por padrão e Harness normal continua funcionando.
14. Ao menos um teste integrado usa o caminho real do Core com provider/tool de teste determinístico, sem confundir isso com E2E de provider real.

Não aumentar cobertura numérica como objetivo isolado. Todo teste novo deve mapear para um requisito, bug ou risco explícito.

## 7. Critérios de aceite finais

A fase só pode ser declarada **funcional e concluída** quando:
- [ ] O estado de PRs e dependências foi reconciliado; nada empilhado foi integrado de forma insegura.
- [ ] O HIE continua opt-in/off por padrão.
- [ ] Uma Task elegível produz trilha operacional correlacionada e métricas honestas.
- [ ] Budgets são aplicados no ponto real de execução e cancelamento/timeout tem comportamento demonstrado.
- [ ] Baseline e candidata executam em cópias independentes, com paridade comprovada e fonte canônica intacta.
- [ ] Uma candidata comprovadamente melhor vence por critérios predefinidos; candidata ineficaz/regressiva é rejeitada.
- [ ] Evidências têm hash, limites, referência Artifact e persistência consistente.
- [ ] Experiência recuperável tem evidências/proveniência e isolamento de escopo.
- [ ] Aprovação humana é vinculada ao diff hash e à versão ativa; promoção/rollback são comprovados.
- [ ] Harness comum, Tasks normais, política, memória e provider explícito não sofrem regressão.
- [ ] Testes focados, suíte backend e build frontend foram executados; resultados e comandos estão registrados.
- [ ] Pelo menos um cenário de ponta a ponta foi validado com o ambiente real disponível; limitações externas estão declaradas.
- [ ] O relatório final diferencia código, testes, CI e E2E e inclui métricas baseline/HIE quando realmente medidas.

Se algum critério não puder ser atendido por limitação ambiental ou contrato ausente, a fase deve ser reportada como **parcial**, com o bloqueio específico e sem alegar conclusão.

## 8. Fora de escopo

- Treinar ou alterar pesos de modelos.
- Execução paralela, swarm, múltiplos candidatos simultâneos ou k>1.
- Alteração automática de Core, políticas, permissões, guardrails, schema de ferramentas, scripts, plugins ou dependências.
- Auto-promoção ou alterações silenciosas em perfis/Skills ativos.
- Criar um segundo banco de memória, Task Engine, sistema de eventos, executor ou provider registry.
- UI de analytics completa, telemetria distribuída ou dashboard genérico.
- Testes de benchmark sem tarefas representativas e critério verificável.
- Afirmar ganhos percentuais antes de medi-los no Mosaic.

## 9. Referências

- [Harness² — repositório oficial](https://github.com/google-research/harness2)
- [Harness² — guia de experimentos](https://github.com/google-research/harness2/blob/main/docs/EXPERIMENTS.md)
- [Proposta de adaptação Harness²](MOSAIC_HARNESS2_ADAPTATION_PROPOSAL_v1.0.md)
- [Arquitetura HIE v1.0](MOSAIC_HARNESS_IMPROVEMENT_ENGINE_ARCHITECTURE_v1.0.md)
- [Prompt HIE anterior](MOSAIC_HARNESS_IMPROVEMENT_ENGINE_IMPLEMENTATION_PROMPT_v1.0.md)
- PRs HIE em avaliação: #102–#111. Verificar estado atual antes de agir.


---

# Aditivo v1.1 — Integração do HIE com a fase de experiência do frontend

**Data:** 2026-10-29  
**Status:** aditivo normativo para auditoria e implementação; não é evidência de conclusão.

## 10. Estado conhecido da cadeia HIE

A cadeia incremental documentada pelos PRs #101–#116 estabelece proposta, validação declarativa, orquestração sequencial, fixtures descartáveis, budgets, evidências e integração limitada com provider. O PR #119 adiciona um fluxo de experimentos persistidos, opt-in, probes baseline/candidato, aprovação humana, promoção/rollback e UI, mas permanece Draft e sua descrição indica validação automatizada pendente.

A descrição de um PR não substitui inspeção do código, status checks e testes executados. Antes de considerar esta fase pronta, auditar os PRs e a implementação atualmente presente em `main` e #119; registrar cada requisito como `comprovado`, `parcial`, `falhou` ou `não verificado`.

## 11. Requisitos integrados do produto/frontend

### 11.1 Conversas e Tasks sem projeto obrigatório

- Uma conversa deve poder começar sem projeto.
- O chat comum é o ponto principal para o usuário pedir trabalho. O Core decide, pelos contratos existentes, se a solicitação segue como conversa ou inicia uma Task; não exigir uma tela separada para criação de Task.
- Projeto é uma associação opcional e continua disponível.
- Conversas e Tasks devem ser persistidas e retomáveis pelo backend, sem histórico falso somente no frontend.
- Conversas/Tasks avulsas não podem herdar contexto de projeto por acidente.
- Se o backend exigir projeto para criar conversa ou Task, documentar o bloqueio e propor a menor mudança; não simular suporte.

### 11.2 Seletor de modelo no chat

- Exibir o modelo ativo próximo ao compositor.
- Carregar opções do backend e persistir a seleção no escopo correto da conversa, reutilizando o contrato existente.
- A troca aplica-se às próximas chamadas. Não migrar silenciosamente uma geração em andamento, não fazer fallback silencioso e não implementar roteamento automático nesta fase.
- Provider nunca é chamado diretamente pelo navegador.

### 11.3 Navegação e gestão

- Remover do layout principal o menu fixo dentro do chat que apresenta Contexto/Memória/Arquivos como módulos permanentes.
- Manter um inspetor opcional e recolhível chamado **Etapas e contexto**, para transparência operacional.
- Mover gestão/edição de agentes, Skills e navegação/visualização geral de arquivos para uma tela própria, acessível pelo menu lateral (nome provisório: **Espaço de trabalho**).
- Não remover anexos/upload necessários ao envio de uma mensagem sem distingui-los da navegação e gestão geral de arquivos.
- Mostrar apenas operações realmente suportadas pelas APIs e permissões existentes.

### 11.4 Etapas e contexto enviado ao LLM

- Mostrar eventos reais: solicitação, Task, fontes, seleção de contexto, chamada ao modelo, ferramentas, verificações e artefatos, quando instrumentados.
- Distinguir fonte encontrada, conteúdo lido, selecionado, enviado, parcial/truncado e omitido.
- Identificar proveniência e ordem de blocos quando disponíveis.
- Indicar explicitamente se o conteúdo é o payload exato ou uma prévia aproximada.
- Nunca apresentar evento reconstruído como execução comprovada; não expor cadeia de pensamento privada, credenciais ou instruções privilegiadas.
- Se a instrumentação não existir, indicar a lacuna e propor a menor alteração backend separadamente.

## 12. Lacunas de implementação HIE a validar prioritariamente

1. **Budgets no caminho real de probe:** verificar se o caminho de experimentos usa o enforcement do provider/tool já implementado. Truncar a saída depois da chamada não limita custo nem duração. Testar bloqueio antes da chamada, limites de entrada/saída, deadline e comportamento de chamadas síncronas em voo.
2. **Contrato de capacidades:** conferir que `supported_capabilities`, `unavailable_capabilities` e os testes representam o comportamento real, sem declarar promoção/rollback como suportados quando não são.
3. **Recuperação de estados:** definir e testar o comportamento em reinício/falha com experimento `queued` ou `running`; reutilizar recuperação de Tasks existente antes de propor infraestrutura nova.
4. **Atomicidade e concorrência:** testar aprovação obsoleta, alteração do perfil entre aprovação e promoção, duas promoções concorrentes e rollback após edição posterior.
5. **Opt-in:** desligado por padrão; configuração explícita da Task prevalece; se ausente, pode herdar da conversa; nenhuma herança pode ativar HIE implicitamente.
6. **Persistência/evidências:** validar orçamento agregado, hashes, paths/symlinks, temporários, falhas parciais entre Artifact e registro.
7. **Escopo de projeto:** a implementação atual pode exigir projeto com perfil de agente para executar HIE. Conversa/Task avulsa continua funcional; somente a ação HIE inelegível deve ser desabilitada com explicação.
8. **Alvo promovível:** nesta fase, promoção permanece limitada a instruções de perfil de projeto. Não ampliar para Skills ou perfil global sem decisão explícita.

## 13. Ordem obrigatória de execução

1. Auditoria sem edição de código; revisar PRs #101–#116 e #119, arquivos, commits, checks e testes.
2. Entregar matriz requisito → evidência → implementação → teste → lacuna/risco.
3. Corrigir primeiro integridade do budget, consistência do contrato de capacidades, lifecycle/recuperação e concorrência.
4. Implementar a experiência de frontend e gestão conforme contratos reais.
5. Instrumentar contexto apenas com aprovação explícita se exigir alteração de backend/segurança/persistência.
6. Executar testes focados do HIE, suíte backend, testes/build frontend e CI disponível.
7. Abrir/atualizar PR em branch dedicada; não fazer merge automático.
8. Reportar resultados reais, limites restantes e requisitos bloqueados.

## 14. Definição de pronto atualizada

A fase só pode ser declarada concluída quando:
- conversas e Tasks avulsas funcionam independentemente de projeto, ou a limitação backend estiver explicitamente bloqueada e aprovada;
- seleção explícita de modelo persiste e vale para próximas chamadas;
- chat não contém menu fixo de Contexto/Memória/Arquivos; gestão de agentes/Skills/arquivos tem tela própria;
- observabilidade distingue o que foi encontrado/lido/selecionado/enviado e payload exato versus aproximado;
- HIE continua opt-in, sequencial, isolado e sem promoção automática;
- budget está aplicado no caminho real de provider, contrato de capacidades é consistente, falhas/concorrência são testadas;
- CI/testes/build são citados com evidência verificável;
- nenhum componente do Core é duplicado e nenhuma capacidade não implementada é simulada.
