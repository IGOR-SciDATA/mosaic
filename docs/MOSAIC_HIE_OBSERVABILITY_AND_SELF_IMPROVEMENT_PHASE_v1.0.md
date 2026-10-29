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
