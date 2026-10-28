# MOSAIC — Implementação do Harness Improvement Engine (HIE)

Você está no Chat de Implantação do Mosaic. O MASTER aprovou a arquitetura conceitual do Harness Improvement Engine e autorizou iniciar somente a auditoria HIE-0.

## Documentos obrigatórios
Leia integralmente:
1. `docs/MOSAIC_HARNESS_IMPROVEMENT_ENGINE_ARCHITECTURE_v1.0.md`
2. `docs/MOSAIC_HARNESS2_ADAPTATION_PROPOSAL_v1.0.md` (originado na PR #101)
3. `docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md`
4. `docs/MOSAIC_RAGNES_CONTEXT_SYSTEM_CONTRACT_v1.0.md`
5. `docs/MOSAIC_MASTER_PHASED_IMPLEMENTATION_SEQUENCE_v1.0.md`
6. `docs/MOSAIC_AGENT_PROFILES_AND_ARTIFACT_TOOLS_ROADMAP_v1.0.md`
7. Contratos atuais de Task, Task events, Artifact, perfil/Skills, provider/model selection, workspace, política/aprovação e recuperação.

Referências externas:
- https://github.com/google-research/harness2
- https://github.com/google-research/harness2/blob/main/docs/EXPERIMENTS.md
- https://arxiv.org/abs/2610.14224

## Regras arquiteturais inegociáveis
- HIE é subsistema opcional do Core; não é um segundo Core nem um segundo Task Engine.
- Mosaic continua dono de estado, memória, contexto, permissões, execução, eventos e conclusão.
- Reutilize Task, Task Events, Artifact, ModelProvider, RAGNES, Tool Registry e a implementação existente de perfis/Skills sempre que os contratos reais suportarem isso.
- Não misture experiências de melhoria com Memory do usuário.
- Não edite ou execute código, scripts, plugins, guardrails, políticas, permissões, schema/migrations, segredos ou configuração do provider.
- Candidatos são dados declarativos estritamente allowlisted; não concedem permissões.
- Promoção para perfil/Skill ativo exige aprovação humana explícita vinculada ao hash exato do diff e à versão ativa.
- Tasks em execução preservam snapshots originais.
- Sem auto-promoção, paralelismo, swarm ou fallback/model routing silencioso.
- Feature desligada por padrão.
- Começar com k=1 e sequência única, com budgets rígidos e cancelamento.
- Não repetir efeitos colaterais externos em probes.
- Sem claims de melhoria sem evidência; testes não executados devem ser marcados como pendentes.
- Não adicionar tabela SQLite, dependência ou infraestrutura sem necessidade demonstrada e decisão aprovada.

## HIE-0 — Ação imediata; somente auditoria
Não altere código, schema, configuração, docs ou branches nesta fase.

Inspecione a main atual e registre:
1. Arquivos/classes/funções reais de Task lifecycle, Task events, Artifact, agent profiles, Skills, ModelProvider selection, RAGNES/context assembly, workspace confinement, tool policy/approval e recuperação.
2. Como snapshots de Skills/perfis já são criados e retomados; identifique lacunas verificadas.
3. Como eventos são persistidos e correlacionados a uma Task.
4. Como artefatos são registrados/reabertos e como o workspace pode ser copiado com segurança.
5. Como o modelo/provider é fixado para a conversa/Task, e quais metadados de execução estão disponíveis.
6. Quais testes cobrem baseline/probe, isolamento, recuperação, cancelamento, approval e artefatos.
7. Conflitos ou lacunas entre implementação atual, PR #101 e arquitetura HIE v1.0.
8. Escolha um único tipo de tarefa determinística e side-effect-free para o primeiro teste (ex.: geração e validação de Markdown em fixture descartável).
9. Defina critérios mensuráveis antes de executar candidatos.
10. Liste caminhos que podem ser editáveis na primeira versão, com allowlist precisa; todos os demais devem ser proibidos.
11. Defina budgets mínimos propostos para calls, candidatos, tokens/contexto, wall-clock, retries e output, sem inventar telemetria que provider não expõe.
12. Informe exatamente os arquivos que seriam criados/alterados em HIE-1 e HIE-2, com justificativa mínima.

### Entregável HIE-0
Apresente:
- mapa de arquivos e funções com evidência;
- matriz “presente no código / testado / validado ponta a ponta / pendente”;
- gaps concretos e risco;
- fluxo de execução do caso de teste;
- allowlist/prohibited list proposta;
- budgets propostos;
- testes e comandos exatos;
- diff mínimo por fase;
- critérios de aceite;
- perguntas arquiteturais ainda abertas, sem decidir pelo MASTER.

Não declare testes executados se só leu código. Se não puder executar uma suíte, informe o bloqueio e avance com a auditoria estática, deixando o resultado como não verificado.

**Pare após o relatório HIE-0 e aguarde aprovação explícita do MASTER. Não implemente HIE-1 ou qualquer outra fase antes dessa aprovação.**

## Plano após a auditoria (não executar ainda)

### HIE-1 — Candidate format, snapshot e validator
Formato declarativo versionado, serialização estável, SHA-256, allowlist de paths/keys, limites de tamanho, diff e validação estrita. Testar hash divergente, schema inválido, path traversal/symlink, unknown keys, valores excessivos e alterações proibidas. Não ativar candidato.

### HIE-2 — Orquestração e registros
Reutilizar Task/events/artifacts/workspace. Estado e ciclo mínimos com feature off by default, k=1, sequência única, budgets, cancelamento e tratamento de interrupção. Nenhuma promoção.

### HIE-3 — Baseline e probe isolado
Criar workspace descartável usando fixtures/cópia segura; baseline/candidato usam o mesmo provider/model, entradas e critérios. Garantir projeto canônico inalterado.

### HIE-4 — Compare + Compose
Critérios previamente definidos, verificadores determinísticos e evidência referenciada. Resultado incerto mantém baseline.

### HIE-5 — Biblioteca de experiências + RAGNES
Cue, lição, evidência, escopo, confiança, versão/hash e proveniência. Nunca inserir no Memory do usuário. Isolamento de projetos/domínios.

### HIE-6 — Revisão humana, promoção e rollback
Mostrar diff e evidências. Aprovação ligada ao hash exato e versão ativa; promover via mecanismo existente de perfil/Skill; preservar versão anterior e rollback exato. Tasks em andamento imutáveis.

### HIE-7 — Avaliação e habilitação controlada
Conjunto reprodutível de tarefas, provider/model fixos quando possível, registrar verificações, regressões, custo/latência somente quando mensuráveis. Continuar opt-in. Nenhum paralelismo sem novo contrato.

Em cada fase:
1. Entregar PR ou conjunto pequeno e revisável de commits.
2. Executar testes reais e informar comando/resultado.
3. Conferir regressão do Harness normal.
4. Demonstrar critérios de aceite.
5. Documentar limitations e evidências.
6. Parar para revisão do MASTER antes da próxima fase.

**Instrução final: comece agora apenas pela HIE-0. Nenhuma alteração de código.**