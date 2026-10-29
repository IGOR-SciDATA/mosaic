# MOSAIC — Prompt integrado de implementação: HIE + frontend conversacional

**Versão:** 1.0  
**Data:** 2026-10-29  
**Repositório:** `IGOR-SciDATA/mosaic`  
**Contrato:** [Fase HIE e frontend integrado](MOSAIC_HIE_OBSERVABILITY_AND_SELF_IMPROVEMENT_PHASE_v1.0.md) — consulte o aditivo v1.1 nesta fase.

## Objetivo

Concluir com o menor diff seguro a fase HIE existente e integrar as decisões recentes de produto no frontend. **Não reimplemente o HIE do zero.** A cadeia #101–#116 contém componentes incrementais já documentados; o #119 permanece Draft até validação verificável. Audite o que está realmente em `main`, o que está somente em PR e o que ainda falta.

## Regras obrigatórias

- Trabalhe em branch dedicada, sem merge automático nem alterações diretas em `main`.
- A Fase 1 é somente auditoria: não edite arquivos antes de entregar a matriz de evidências.
- PR descriptions são intenção, não prova. Confira código, checks atuais e resultados de testes.
- Preserve React/Vite, FastAPI, SQLite, REST/SSE e os serviços/contratos existentes.
- Não crie segundo Core, executor, Task engine, event bus, memória, Artifact store, provider registry ou sistema paralelo.
- Não adicione dependências, tabelas, infraestrutura ou novos serviços sem necessidade demonstrada e aprovação.
- HIE desligado por padrão; execução sequencial k=1; candidatos declarativos allowlisted; nenhum código de candidato é executado; sem auto-promoção.
- HIE não altera permissões, políticas, guardrails, schemas/migrações, dependências, credenciais, configuração de provider nem dados canônicos.
- Não expor cadeia de pensamento privada, segredos ou instruções internas privilegiadas.
- Não afirmar CI verde ou testes aprovados sem evidência.

## Fase 1 — Auditoria sem edição

1. Revise PRs #101–#116 e #119: descrição, diff, dependências, merge, reviews, checks e estado atual.
2. Compare a documentação da fase com o código em `main` e o diff de #119.
3. Mapeie candidato declarativo, fixtures, orquestrador, eventos, budgets, Artifact/evidências, SQLite, opt-in, API, aprovação, promoção, rollback e frontend.
4. Rastreie o caminho real do probe até o provider e prove se usa enforcement de budget; truncamento pós-resposta não basta.
5. Verifique consistência entre capacidades declaradas pela API e testes.
6. Verifique recuperação de `queued/running`, falhas de evento/persistência, timeouts e concorrência/stale state.
7. Verifique opt-in por conversa/Task e precedência da configuração explícita da Task.
8. Verifique se conversa/Task avulsa é possível e como o HIE explica a exigência atual de projeto/perfil.
9. Entregue matriz `requisito → PR/commit → código real → teste/CI → estado → lacuna/risco`, classificando `comprovado`, `parcial`, `falhou` ou `não verificado`.
10. Pare após o relatório. Se uma correção exigir mudança de schema, permissões, segurança ou contrato público, proponha o menor ajuste e aguarde aprovação.

## Fase 2 — Corrigir o HIE existente

Corrija apenas problemas confirmados:
- conectar probes ao enforcement real de budget de provider; limitar entrada/saída antes/durante a geração sempre que o provider suportar; registrar limites e falhas; não alegar que timeout interrompe à força chamada síncrona se isso não for garantido;
- alinhar capacidades suportadas/indisponíveis e testes;
- usar/reaproveitar lifecycle de Tasks para recuperação, sem infraestrutura nova não aprovada;
- validar atomicidade de aprovação, promoção e rollback contra versões/hash atuais;
- garantir opt-in off por padrão, configuração própria de Task prevalecendo e herança da conversa apenas quando não houver configuração própria;
- validar persistência de evidências, budgets agregados, paths/symlinks, temporários e falhas parciais;
- manter promoção limitada ao alvo já suportado (instruções de perfil de projeto); não ampliar para Skill ou perfil global nesta fase;
- sem projeto/perfil elegível, manter chat e Task normais funcionais e desabilitar apenas a execução HIE, explicando o motivo.

## Fase 3 — Redesign do frontend

### Chat e navegação
- Criar experiência principal conversacional com menu lateral recolhível.
- Permitir criar conversa avulsa, sem projeto.
- O chat comum é o ponto de entrada para solicitar trabalho; o Core decide se a solicitação inicia uma Task conforme os contratos reais. Remover fluxo/tela separada obrigatória para criar Tasks.
- Exibir histórico real de conversas/Tasks, persistido e retomável; projetos continuam opcionais.
- Garantir que conversa/Task avulsa não herde contexto de projeto por acidente.

### Seletor de modelo
- Exibir modelo ativo próximo ao compositor.
- Buscar modelos pela API real e persistir seleção no escopo correto da conversa.
- Aplicar mudança às próximas chamadas; não trocar geração ativa silenciosamente, não fazer fallback silencioso nem roteamento automático.
- O browser nunca chama provider diretamente.

### Tela de gestão
- Remover do chat o menu fixo que lista Contexto/Memória/Arquivos como módulos permanentes.
- Criar tela separada acessível pelo menu lateral (nome provisório “Espaço de trabalho”) para gestão/edição de agentes, Skills e navegação/visualização geral de arquivos.
- Manter anexos/upload necessários à mensagem quando já forem parte do chat; não confundir anexar arquivo com administrar/navegar workspace.
- Usar APIs e permissões existentes; não simular CRUD inexistente.
- Preservar conversa e rascunho ao navegar quando aplicável.

### Inspetor didático do contexto
- Disponibilizar painel recolhível “Etapas e contexto”.
- Mostrar somente eventos reais: solicitação, Task, fontes, seleção, chamada ao modelo, ferramentas, verificação e artefatos.
- Diferenciar encontrado, lido, selecionado, enviado, parcial/truncado e omitido.
- Indicar payload exato versus prévia aproximada; quando não instrumentado, declarar a lacuna.
- Não expor cadeia de pensamento privada, segredos ou instruções privilegiadas.
- Se exigir nova instrumentação de backend/persistência, documentar proposta mínima e aguardar aprovação.

### HIE Experimental
- Acesso discreto e explicitamente experimental, somente se o backend indicar disponibilidade.
- Mostrar baseline, candidato, diff/hash, fixtures, critérios, evidências e resultado.
- Controles separados para rejeitar, aprovar, promover e rollback, cada um só quando a API e o estado real permitirem.
- Aprovação vinculada ao hash exato do candidato e versão/hash ativos; alteração invalida a aprovação.
- Nenhuma promoção automática. Evidência inconclusiva, empate ou regressão nunca promovem candidato.

## Fase 4 — Testes obrigatórios

Inclua testes para:
- orçamento bloqueando chamada antes da execução e limites reais de provider;
- falhas de provider, timeouts, saídas vazias e eventos/persistência com falha;
- reinício em `queued/running`, concorrência de experimentos e concorrência de promoção/rollback;
- aprovação obsoleta, perfil alterado e rollback após edição posterior;
- capacidades da API consistentes com o comportamento;
- opt-in off por padrão e precedência/herança de Task;
- conversa/Task avulsa, isolamento de contexto e indisponibilidade contextual do HIE;
- seletor e persistência de modelo, modelo indisponível e geração em curso;
- navegação recolhível, preservação de rascunho, tela de gestão e remoção do menu fixo do chat;
- inspetor de contexto exato/aproximado e proteção de conteúdo;
- HIE desligado, erro, regressão, empate, inconclusivo e promoção explícita.

Execute testes focados HIE, suíte completa do backend, testes/build frontend e CI disponível. Informe comandos e resultados reais. Doubles/fixtures não equivalem a smoke test de provider real.

## Fase 5 — Entrega

Entregue:
1. matriz de PRs e evidências;
2. problemas confirmados e correções;
3. arquivos alterados;
4. testes/CI e resultados reais;
5. capacidades HIE disponíveis/indisponíveis;
6. lacunas, riscos e decisões pendentes;
7. branch e PR para revisão, sem merge automático.

**Definição de pronto:** budget aplicado no caminho real; contrato de capacidades coerente; lifecycle e aprovação resistentes a stale state/concorrência; chat avulso e troca de modelo funcionando; gestão separada; inspetor honesto sobre o contexto real; HIE opt-in sem auto-promoção; testes/build reportados com evidência.

**Ordem inegociável:** auditoria sem edição → relatório/decisão → correções HIE → frontend → testes → revisão de diff → PR/relatório.
