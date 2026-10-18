# MOSAIC — Relatório de execução das fases 0–12

**Data:** 18/10/2026  
**Repositório:** `IGOR-SciDATA/mosaic`  
**Branch:** `main`  
**Commit de código validado:** `8379157517adc6661b941f4c18be2f5d64259209`  
**CI:** [GitHub Actions #39118929224](https://github.com/IGOR-SciDATA/mosaic/actions/runs/39118929224)  
**Resultado:** 233 testes backend aprovados, 1 aviso; build frontend aprovado.

Este relatório segue a sequência normativa de `MOSAIC_MASTER_PHASED_IMPLEMENTATION_SEQUENCE_v1.0.md`. “Concluída” significa que o escopo implementável da fase tem código e evidência correspondente; não transforma smoke tests não executados em sucesso nem afirma validação ponta a ponta onde ela não ocorreu.

## Resumo por fase

| Fase | Estado | Evidência e limite explícito |
|---|---|---|
| 0 — Auditoria e baseline | Testado | Contrato MVP e schema reconciliados em documentação anterior; CI atual verde. Ollama real e reinício de processo não foram executados neste ambiente. |
| 1 — Fluxo Markdown | Testado | `test_markdown_summary_flow_reads_source_creates_and_reopens_verified_artifact`: leitura, resumo, aprovação, criação, reabertura, hash e evento de verificação. |
| 2 — Segurança e estados | Testado | Suíte cobre transições, aprovação, isolamento de workspace, validação de argumentos, limites e falhas. A suíte não substitui auditoria dinâmica de implantação. |
| 3 — Harness integrado | Testado com provider simulado | `test_agent_harness_integration.py` cobre decisão, ferramenta, resultado observado e conclusão usando o modelo selecionado. Registro explícito de providers adicionado; atualmente só Ollama é registrado. |
| 4 — Eventos, aprovação, cancelamento e retomada | Testado deterministicamente | Eventos, aprovação/rejeição, cancelamento e recuperação têm cobertura. Crash real entre processos e retomada após reinicialização permanecem pendentes. |
| 5 — Observabilidade e autoverificação | Testado | Eventos persistidos, metadados redigidos, hashes, reabertura e invalidação de evidência do artefato cobertos por testes. Uso/custo só é registrado quando o provider realmente o fornece. |
| 6 — Contexto, memória e continuidade | Testado | Testes de isolamento de contexto, estado de projeto, memória e histórico; evidência de fonte fica ligada a ToolCall/ToolResult. Avaliação de relevância em escala continua futura. |
| 7 — Perfis e coordenação | Testado | `test_task_coordinator.py` prova três Tasks dependentes, perfis versionados, resultados persistidos, critérios de aceite e integração sequencial no mesmo Task Engine. |
| 8 — Ferramentas gerais e pesquisa | Testado com fixtures | Novo fluxo determinístico search → web_fetch → relatório com URL citada → artefato reaberto e verificado. Acesso público real em rede não foi testado neste CI. |
| 9 — Artefatos profissionais | Testado | `test_artifact_tool.py` gera, reabre e valida Markdown, PDF, DOCX, XLSX e PPTX; registra hash e invalida evidência se bytes mudarem. |
| 10 — Identidade e interface | Build testado | Tema claro/escuro, cartões, navegação e acessibilidade reduzida de movimento estão no CSS; build passou. Inspeção visual real e auditoria de acessibilidade em navegador permanecem pendentes. |
| 11 — Acesso a modelos via web | Investigação concluída | A avaliação documental mantém automação de sessões de consumo fora do escopo sem autorização explícita. O registro de providers falha sem fallback; nenhum provider remoto foi escolhido ou ativado. |
| 12 — Avaliação ponta a ponta e autonomia limitada | Matriz atualizada | Matriz registra os fluxos testados e limites. Provider real, crash/restart real, rede pública real e jornada completa de construção de software ainda não têm evidência E2E suficiente. |

## Decisões arquiteturais preservadas

- `MODEL ≠ ACCESS`: provider é resolvido explicitamente a partir do modelo persistido.
- `MOSAIC OWNS STATE`: tarefas, eventos, aprovações, resultados e artefatos continuam sob o Core.
- Nenhum fallback silencioso entre modelos.
- Nenhuma automação de sessão web autenticada, reutilização de cookies ou bypass de proteção.
- Nenhum novo banco, fila distribuída ou segundo Task Engine.
- As etapas do plano de Task agora declaram dependências e registram hashes/IDs de evidência, sem copiar conteúdo integral de arquivos para o plano.
- Relatórios de pesquisa que solicitam pesquisa web exigem um `web_fetch` concluído e ao menos uma URL exata citada antes da criação do artefato.

## Pendências de validação externa

Estas pendências não são falhas ocultadas; dependem de um ambiente que esta execução não controla:

1. Smoke test com Ollama real e modelo instalado.
2. Reinício real do processo enquanto uma Task está ativa ou aguardando aprovação.
3. Pesquisa em rede pública real, separada dos fixtures determinísticos.
4. Inspeção visual e acessibilidade em navegador real para os temas claro/escuro.
5. Fluxo completo de construção de software (arquitetura, API, UI, testes, build e QA).
6. Integração de modelo remoto oficial: falta escolher explicitamente fornecedor/método e definir credenciais e orçamento. Acesso a interfaces web de consumo permanece não autorizado.

## Comandos e resultado

Executados pelo workflow GitHub Actions no commit indicado:

- `python -m pytest -q` — **233 passed, 1 warning**.
- `npm run build` — **sucesso**.

Não foram executados localmente nesta sessão: smoke test com Ollama real, crash/restart real, teste visual de navegador e chamadas a API remota com credenciais.

## Fontes de evidência

- [Matriz E2E](MOSAIC_E2E_VALIDATION_MATRIX_v1.0.md)
- [Auditoria da Fase 0](MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md)
- [Avaliação de acesso a modelos via web](MOSAIC_WEB_MODEL_ACCESS_EVALUATION_v1.0.md)
- [Sequência Mestre de Implementação](MOSAIC_MASTER_PHASED_IMPLEMENTATION_SEQUENCE_v1.0.md)
