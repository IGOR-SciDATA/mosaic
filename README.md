<div align="center">

<img src="assets/branding/mosaic-symbol.png" alt="Mosaic" width="180" />

# MOSAIC

### Um Core persistente para memória, contexto, projetos e execução de tarefas

**A inteligência não deve depender de um único modelo.**

O Mosaic é um workspace de IA local-first que mantém estado, contexto e execução sob controle do próprio sistema. O modelo interpreta e propõe; o Core organiza, valida, executa e persiste.

[Arquitetura](#arquitetura) · [Estado atual](#estado-atual) · [Roadmap](#roadmap) · [Instalação](#instalação) · [Documentação](#documentação)

</div>

---

## Visão

Um chat responde a uma mensagem. Um projeto real precisa preservar decisões, arquivos, tarefas, resultados e o ponto em que o trabalho parou.

O Mosaic busca transformar a conversa em um **ambiente de trabalho contínuo**: o usuário escolhe o modelo, enquanto o Core mantém o estado e coordena contexto, ferramentas e resultados. A ambição é evoluir para um Harness geral capaz de concluir tarefas variadas — de documentos e pesquisas a apresentações e projetos de software — sem confundir capacidade planejada com capacidade já validada.

O projeto também tem uma motivação de soberania tecnológica: priorizar controle local dos dados, componentes substituíveis e menor dependência de infraestrutura externa.

## Princípios

- **MODEL ≠ ACCESS** — o modelo não determina quais ações são permitidas.
- **MEMORY ≠ TRUTH** — uma lembrança não é automaticamente um fato verificado.
- **HISTORY ≠ MODEL MEMORY** — o histórico fica sob controle do Mosaic, não depende dos pesos do modelo.
- **CONTEXT ≠ FULL HISTORY** — cada inferência recebe contexto selecionado para a tarefa.
- **TOOL CALL ≠ TOOL EXECUTION** — uma chamada proposta precisa ser validada antes da execução; seu resultado é persistido.
- **SKILL ≠ PERMISSION** — instruções especializadas não concedem acesso nem ignoram aprovações.
- **HARNESS ≠ SECOND CORE** — o Harness coordena os componentes existentes, sem criar um segundo sistema de estado.
- **MOSAIC OWNS STATE** — o Core é a fonte autoritativa de estado, política e conclusão.
- **Não construir porque podemos. Construir porque precisamos.**

## Arquitetura

A base tecnológica atual é **React + Vite**, **FastAPI**, **SQLite**, workspace local e uma abstração de provider com suporte a **Ollama**.

~~~text
React + Vite
  └─ Conversas, projetos e experiência de execução
           │ REST / SSE
           ▼
FastAPI — MOSAIC CORE
  ├─ Conversation / Project / Message
  ├─ Context Manager / Memory / Project State
  ├─ Task Engine + ciclo de Agent
  ├─ ModelProvider (modelo escolhido pelo usuário)
  ├─ Tool Registry / ToolCall / ToolResult
  ├─ Política, permissões e aprovações
  └─ Persistência e resultados
           │
           ▼
SQLite + workspace local + provider configurado
~~~

O objetivo arquitetural é ampliar essa base com um Harness robusto: planejamento, subtarefas persistidas, dependências, execução segura de ferramentas, observação de resultados, validação e retomada. Isso deve acontecer por incrementos, sem reescrever o Core nem adicionar infraestrutura sem necessidade comprovada.

### Modelo escolhido pelo usuário

O usuário seleciona o modelo na conversa. O Mosaic deve utilizar essa escolha durante a execução e **não trocar automaticamente de modelo nem fazer fallback silencioso**. A abstração de provider permite evoluir os modelos suportados sem entregar ao modelo o controle do estado ou das permissões.

## Estado atual

O repositório já contém uma base funcional em evolução: interface web, API, persistência SQLite, contexto e estado de projetos, tarefas, abstração de provider e um ciclo de agente com ferramentas e resultados persistidos. Há também trabalho recente para tornar as tarefas mais determinísticas, limitar o contexto por execução e recuperar a conclusão de artefatos após falhas ambíguas de escrita.

Isso **não significa que todo o Harness esteja concluído**. A integração ponta a ponta, a segurança de todas as ferramentas, a recuperação completa, a UX final e a qualidade dos diferentes formatos de artefato precisam ser verificadas por testes reproduzíveis. Consulte os PRs, contratos e testes para distinguir código existente, documentação proposta e capacidades ainda planejadas.

### Em desenvolvimento / planejado

- Perfis de Agent persistidos por conversa, com instruções AGENTS.md/AGENT.md e Skills versionadas.
- Snapshot por tarefa das instruções e Skills realmente utilizadas.
- Coordenador de subtarefas com dependências, critérios de aceite e retomada.
- Contexto de trabalho recuperável e limitado, com proveniência.
- Ferramentas seguras para arquivos, terminal controlado e pesquisa/leitura web.
- Artefatos validados: Markdown, PDF, XLSX e PPTX.
- Interface mais limpa e ampla, com chat como foco principal, progresso factual e detalhes técnicos sob demanda.
- Fluxos completos de criação de documentos, pesquisa e desenvolvimento de software, seguidos por avaliação e eventual paralelismo controlado.

Esses itens são objetivos de evolução, não uma promessa de que todas as capacidades já estejam disponíveis na versão atual.

## Roadmap

A execução segue o [Roadmap Mestre do Harness Universal](docs/MOSAIC_MASTER_ROADMAP_UNIVERSAL_HARNESS_v1.0.md), com uma fase por PR e validação antes de avançar.

| Etapa | Objetivo |
|---|---|
| **0. Baseline** | Auditar o código, branches, contratos, testes e fluxos reais antes de novas mudanças. |
| **1–3. Confiabilidade** | Reforçar segurança e estados; integrar o Harness ao modelo da conversa; persistir eventos, aprovações e retomada. |
| **4–6. Agent e contexto** | Persistir perfil/instruções/Skills, coordenar subtarefas e evoluir a recuperação de contexto. |
| **7–9. Ferramentas e UX** | Consolidar ferramentas seguras, artefatos e validadores; integrar a experiência de execução. |
| **10. Frontend** | Auditar e simplificar a interface, ampliar chat e mensagens, reduzir ruído e organizar os detalhes sob demanda. |
| **11–12. Validação** | Provar fluxos completos de documentos, pesquisa e software; medir qualidade, resiliência e autonomia limitada. |
| **13. Paralelismo** | Só depois de demonstrar isolamento, controle de concorrência, cancelamento e recuperação. |

**Próximo passo acordado: Fase 0 — auditoria do estado real.** Não começar uma reescrita nem implementar todas as ferramentas simultaneamente.

## Instalação

### Pré-requisitos

- Git
- Python compatível com as dependências do backend
- Node.js e npm
- [Ollama](https://ollama.com/) para executar um modelo local

### 1. Clonar o repositório

~~~bash
git clone https://github.com/IGOR-SciDATA/mosaic.git
cd mosaic
~~~

### 2. Preparar o backend

~~~bash
cd backend
python -m venv .venv
~~~

Ative o ambiente virtual:

~~~powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
~~~

~~~bash
# Linux / macOS
source .venv/bin/activate
~~~

Instale as dependências e inicie a API:

~~~bash
pip install -r requirements.txt
uvicorn app.main:app --reload
~~~

A API fica em http://127.0.0.1:8000; a documentação interativa, em http://127.0.0.1:8000/docs.

### 3. Preparar o modelo local

Em outro terminal, com Ollama instalado:

~~~bash
ollama pull qwen2.5:3b
~~~

O Qwen 2.5 3B é uma opção inicial para testes locais em hardware modesto. O modelo precisa estar disponível no Ollama e configurado/selecionado no Mosaic. A qualidade e a velocidade dependem do hardware e da tarefa.

### 4. Iniciar o frontend

Em outro terminal, na raiz do repositório:

~~~bash
cd frontend
npm install
npm run dev
~~~

Use a URL local informada pelo Vite. Os comandos acima descrevem a inicialização dos serviços; não substituem a verificação de compatibilidade do ambiente nem garantem que todos os fluxos agentic estejam completos.

## Documentação

- [Roadmap Mestre — Harness Universal](docs/MOSAIC_MASTER_ROADMAP_UNIVERSAL_HARNESS_v1.0.md)
- [Contrato oficial do Harness v1.2](docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md)
- [Contrato RAGNES — contexto e recuperação](docs/MOSAIC_RAGNES_CONTEXT_SYSTEM_CONTRACT_v1.0.md)
- [Contrato de UX do frontend](docs/MOSAIC_FRONTEND_UX_IMPLEMENTATION_CONTRACT_v1.0.md)
- [Guia de desenvolvimento do workspace agêntico](docs/MOSAIC_DEVELOPMENT_GUIDE_AGENTIC_WORKSPACE_v1.0.md)
- [Proposta de perfis de Agent e ferramentas de artefatos — PR #53](https://github.com/IGOR-SciDATA/mosaic/pull/53)

Os contratos descrevem o comportamento pretendido e os limites arquiteturais; o código e os testes determinam o que está efetivamente implementado e validado.

---

**Mosaic está em desenvolvimento ativo.** A prioridade é construir uma base confiável, observável e retomável antes de ampliar a autonomia ou a complexidade.
