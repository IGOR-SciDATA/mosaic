<div align="center">

<br>

# ◈ MOSAIC

### Core de inteligência pessoal · Memória · Contexto · Estado · Continuidade

<br>

<img src="assets/branding/mosaic-symbol.png" alt="Mosaic — símbolo do projeto" width="420" />

### 🧩 Uma inteligência que não depende de um modelo

**Mosaic é um workspace de IA local-first que busca preservar contexto, memória, projetos e continuidade enquanto modelos e tecnologias mudam.**

![Python](https://img.shields.io/badge/Python-FastAPI-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Database](https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Local First](https://img.shields.io/badge/Local--First-By%20Design-0F766E?style=for-the-badge)
![Models](https://img.shields.io/badge/Models-User%20Selected-0891B2?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active%20Development-DC2626?style=for-the-badge)

**🧠 Core** · **💾 Memória** · **📍 Estado** · **🧭 Contexto** · **🔌 Modelos** · **🛠️ Ferramentas** · **♾️ Continuidade**

[🇧🇷 Soberania tecnológica](#-soberania-tecnológica-brasileira) · [Visão](#-visão) · [Princípios](#-princípios) · [Interface](#️-interface-web) · [Arquitetura](#️-arquitetura) · [Estado atual](#-estado-atual) · [Roadmap](#️-roadmap) · [Instalação](#-instalação) · [Documentação](#-documentação)

</div>

---

# 🖥️ Interface Web

A interface atual reúne conversas, projetos, seleção de modelo e elementos de contexto em um workspace único. A captura abaixo mostra o ambiente de desenvolvimento real; não representa telas futuras do roadmap.

<div align="center">

<img src="assets/branding/download.png" alt="Captura da interface web atual do Mosaic" width="100%" />

<sub>Interface web do Mosaic · Captura do ambiente de desenvolvimento</sub>

</div>

---

# 🇧🇷 Soberania tecnológica brasileira

O Mosaic nasce também de uma ambição estratégica: **contribuir para que o Brasil desenvolva e controle mais da própria infraestrutura de inteligência artificial**.

A dependência de modelos, APIs, plataformas e infraestrutura de terceiros pode impor limites de custo, acesso, privacidade e continuidade. O Mosaic explora uma alternativa arquitetural: manter o Core, o estado persistente e as regras de execução sob controle do próprio ambiente, permitindo que o usuário escolha e substitua o modelo.

Nossa direção é contribuir para um ecossistema brasileiro capaz de:

- 🇧🇷 fortalecer a soberania de dados e o controle sobre informações estratégicas;
- 🧠 desenvolver conhecimento, software e capacidade técnica no Brasil;
- 🔓 reduzir dependências externas quando elas não forem necessárias;
- 💻 priorizar execução local e modelos abertos quando forem adequados;
- 🏗️ criar bases tecnológicas modulares para produtos e aplicações nacionais;
- 🤝 contribuir para uma indústria brasileira de IA mais autônoma e sustentável.

Isso é uma **direção estratégica**, não uma alegação de independência total já alcançada. Serviços externos poderão ser integrados quando fizer sentido, mas não devem ser uma dependência silenciosa nem retirar do usuário o controle sobre seus dados e escolhas.

> **Soberania de dados. Inteligência estratégica. Tecnologia brasileira.**

---

# 🌌 Visão

Um assistente pode responder a uma mensagem. Um projeto real precisa preservar decisões, arquivos, tarefas, resultados e o ponto em que o trabalho parou.

O Mosaic busca transformar a interação com IA em um **ambiente persistente de trabalho**. Quando o usuário pergunta “Mosaic, lembra onde paramos no Projeto X?”, a ambição é recuperar o estado relevante do projeto — objetivo, decisões, tarefas, arquivos, resultados e próximos passos — sem depender de encontrar manualmente uma conversa antiga.

O modelo pode mudar. O computador pode mudar. A interface pode mudar.

**O Mosaic deve preservar a continuidade.**

*The model is just one piece. The true product is continuity.*

---

# 🎯 Princípios arquiteturais

| Princípio | O que significa |
|---|---|
| 🧠 **MODEL ≠ ACCESS** | O modelo pode propor ações; o Core decide o que é permitido. |
| 💾 **MEMORY ≠ TRUTH** | Uma lembrança não é automaticamente um fato verificado. |
| 🕒 **HISTORY ≠ MODEL MEMORY** | O histórico é persistido pelo Mosaic, não depende dos pesos do modelo. |
| 🧭 **CONTEXT ≠ FULL HISTORY** | Cada tarefa recebe contexto relevante e limitado. |
| 🛠️ **TOOL CALL ≠ TOOL EXECUTION** | Uma chamada proposta precisa ser validada antes de executar. |
| 📘 **SKILL ≠ PERMISSION** | Instruções especializadas não concedem acesso nem ignoram aprovações. |
| 🧩 **HARNESS ≠ SECOND CORE** | A coordenação reutiliza os componentes do Core; não cria um segundo dono do estado. |
| 📍 **MOSAIC OWNS STATE** | O Core é a fonte autoritativa do estado, das políticas e da conclusão. |
| 🔌 **MODEL ≠ IDENTITY** | Trocar o modelo não deve apagar a continuidade. |

> **Não construir porque podemos. Construir porque precisamos.**

---

# 🏗️ Arquitetura

A base tecnológica observada no repositório é **React + Vite**, **FastAPI**, **SQLite**, workspace local e provider com suporte a **Ollama**.

~~~text
React + Vite
  └─ Conversas, projetos, seleção de modelo e experiência de trabalho
              │ REST / SSE
              ▼
FastAPI — MOSAIC CORE
  ├─ Conversation / Project / Message / Memory / Model
  ├─ Context Manager e estado de projeto
  ├─ Task Engine + ciclo de Agent
  ├─ ModelProvider (modelo escolhido na conversa)
  ├─ Tool Registry / ToolCall / ToolResult
  ├─ Action / política / aprovação
  └─ Eventos de tarefa e persistência
              │
              ▼
SQLite + workspace local + provider configurado
              │
              └─ Ollama / modelo local
~~~

### O usuário escolhe o modelo

O modelo é selecionado por conversa. O Mosaic deve respeitar essa escolha: **sem roteamento automático, troca silenciosa de modelo ou fallback oculto**. O provider é uma camada de integração, não o dono do estado nem das permissões.

### O ciclo de execução pretendido

~~~text
Pedido → Task → contexto limitado → decisão do modelo
  → validação do Core → aprovação, quando necessária
  → ferramenta controlada → resultado persistido
  → observação → validação → conclusão ou retomada
~~~

O Harness deve coordenar esse ciclo reutilizando o Core existente, não criar um segundo sistema de estado.

---

# 🧠 Memória, estado e contexto

São conceitos diferentes:

- **Memória:** informações e experiências registradas.
- **Histórico:** o que aconteceu nas conversas e execuções.
- **Estado:** onde um projeto ou tarefa está agora.
- **Contexto:** o subconjunto relevante para o trabalho atual.
- **Conhecimento:** informação acompanhada de origem e grau de confiança.

A memória deve existir fora dos pesos do modelo. O contexto deve ser montado pelo Mosaic respeitando escopo, relevância e limites. Informações recuperadas devem preservar proveniência quando aplicável, para que possam ser inspecionadas e corrigidas.

---

# 🧬 O que deve permanecer quando o modelo muda

O Core foi pensado para manter fora do modelo as informações que precisam sobreviver entre conversas e versões de tecnologia:

- **Identidade e princípios:** regras estáveis do sistema, não reconstruídas a cada sessão.
- **Memória:** fatos declarados, preferências, decisões e experiências com origem identificável.
- **Estado de projeto:** objetivo, fase atual, tarefas, bloqueios e próximos passos.
- **Histórico:** conversas, execuções, chamadas de ferramentas e resultados persistidos.
- **Contexto:** seleção limitada e relevante dessas informações para cada tarefa.
- **Arquivos e artefatos:** conteúdo de trabalho no workspace, separado da janela de contexto do modelo.

Essas são responsabilidades arquiteturais. A cobertura, a recuperação e a experiência completa de cada capacidade devem ser demonstradas por testes; a lista não significa que toda a visão de longo prazo já esteja pronta.

---

# 🧩 Simplicidade por design

O Mosaic deve evoluir por incrementos verificáveis, não começar como uma plataforma distribuída.

**Não são objetivos do estágio atual:** infraestrutura cloud obrigatória, microsserviços, Kubernetes, banco vetorial obrigatório, roteamento automático de modelos, execução paralela de agentes ou marketplace de plugins.

RAG e embeddings só devem ser ampliados quando a avaliação demonstrar uma lacuna real na recuperação lexical/contextual. Paralelismo só pode ser considerado depois de provar isolamento, concorrência, cancelamento e recuperação. O princípio é simples: **modular por desenho; complexidade somente quando necessária**.

---

# 🚦 Estado real do projeto

A inspeção estática da branch `main` encontrou:

- **Frontend:** aplicação React/Vite existente; a experiência visual e os fluxos completos ainda precisam de validação de uso.
- **API:** FastAPI com rotas para conversas, mensagens, projetos, memórias, modelos, tarefas, chamadas de ferramentas e ações.
- **Persistência:** SQLite cria tabelas para modelos, projetos, memórias, conversas, mensagens, tarefas, ações, chamadas/resultados de ferramentas e eventos de tarefa.
- **Agent e ferramentas:** existe ciclo de agente com decisão injetável e integração com provider no endpoint de tarefas; ferramentas registradas incluem `filesystem`, `terminal`, `search`, `web_fetch`, `calculator` e `weather`.
- **Controles:** há validação de argumentos, aprovação de chamadas e testes para traversal/symlinks, allowlist do terminal e validação de URLs.
- **Observabilidade:** há persistência de eventos e endpoints de eventos/stream de tarefas.
- **Testes:** existem testes para agente, ferramentas, ações, tarefas e eventos. A presença dos testes não significa que tenham passado; nesta auditoria remota, a suíte não foi executada.
- **Limites de escopo:** não foi comprovado um fluxo completo de ponta a ponta após reinício, nem a validação completa de todas as ferramentas, aprovações, retomadas e UX.

A auditoria também identificou divergências documentais: o contrato MVP citado por outros documentos não está versionado no caminho esperado em `main`; o schema atual não cria todas as entidades listadas no contrato (em especial `artifacts` e `settings`); e a sequência do roadmap precisa ser reconciliada com o trabalho que já existe. Esses pontos estão registrados no [Relatório de Auditoria da Fase 0](docs/MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md).

**Não declaramos o Harness completo nem testes aprovados sem evidência reproduzível.** O objetivo imediato é fechar as divergências documentais e validar os fluxos existentes antes de ampliar capacidades.

---

# 🗺️ Roadmap

O [Roadmap Mestre do Harness Universal](docs/MOSAIC_MASTER_ROADMAP_UNIVERSAL_HARNESS_v1.0.md) define a direção arquitetural. A auditoria de baseline é feita por inspeção estática; testes de execução e integração continuam pendentes onde não há evidência registrada.

| Etapa | Objetivo |
|---|---|
| **Fase 0 — Baseline** | Inventário de código, schema, APIs, UI, ferramentas, testes, branches e contratos; registrar o que existe e o que ainda não foi validado. |
| **Fases 1–3 — Confiabilidade** | Revalidar segurança e transições de estado; provar o Harness com o modelo escolhido na conversa; provar eventos, reconexão, cancelamento e retomada. |
| **Fases 4–6 — Agent e contexto** | Perfis por conversa, instruções/Skills versionadas e snapshots por Task; coordenação sequencial de subtarefas; contexto com proveniência e avaliação. |
| **Fases 7–9 — Ferramentas e UX** | Consolidar ferramentas seguras, artefatos/validadores e a experiência de execução integrada. |
| **Fase 10 — Frontend** | Simplificar e ampliar a interface, manter o chat como foco e revelar detalhes técnicos sob demanda. |
| **Fases 11–12 — Validação** | Provar fluxos completos de documentos, pesquisa e software; medir qualidade, resiliência e autonomia limitada. |
| **Fase 13 — Paralelismo** | Só considerar execução paralela após provar isolamento, concorrência, cancelamento e recuperação. |

**Próximo passo:** usar o relatório da Fase 0 para resolver os bloqueios de contrato e decidir o menor incremento validável. O roadmap descreve a sequência-alvo, não uma afirmação de que todas as fases anteriores já passaram por QA.

---

# 🚀 Instalação

## Pré-requisitos

- [Git](https://git-scm.com/)
- [Python](https://www.python.org/)
- [Node.js](https://nodejs.org/)
- [Ollama](https://ollama.com/) para usar um modelo local

## 1. Clonar

~~~bash
git clone https://github.com/IGOR-SciDATA/mosaic.git
cd mosaic
~~~

## 2. Backend

~~~bash
cd backend
python -m venv .venv
~~~

Windows PowerShell:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

Linux/macOS:

~~~bash
source .venv/bin/activate
~~~

~~~bash
pip install -r requirements.txt
uvicorn app.main:app --reload
~~~

API: http://127.0.0.1:8000 · Documentação: http://127.0.0.1:8000/docs

## 3. Modelo local

Com o Ollama instalado:

~~~bash
ollama pull qwen2.5:3b
~~~

O modelo precisa estar disponível e selecionado/configurado no Mosaic. Desempenho e qualidade dependem do hardware e da tarefa.

## 4. Frontend

Em outro terminal, na raiz do repositório:

~~~bash
cd frontend
npm install
npm run dev
~~~

Abra a URL local informada pelo Vite, normalmente http://localhost:5173.

Esses comandos iniciam os serviços; não substituem a execução dos testes nem garantem que todos os fluxos do Harness estejam completos.

---

# 📚 Documentação

- [Relatório de Auditoria da Fase 0](docs/MOSAIC_PHASE_0_BASELINE_AUDIT_v1.0.md)
- [Roadmap Mestre — Harness Universal](docs/MOSAIC_MASTER_ROADMAP_UNIVERSAL_HARNESS_v1.0.md)
- [Contrato oficial do Harness v1.2](docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md)
- [Contrato RAGNES — contexto e recuperação](docs/MOSAIC_RAGNES_CONTEXT_SYSTEM_CONTRACT_v1.0.md)
- [Contrato de UX do frontend](docs/MOSAIC_FRONTEND_UX_IMPLEMENTATION_CONTRACT_v1.0.md)
- [Guia de desenvolvimento do workspace agêntico](docs/MOSAIC_DEVELOPMENT_GUIDE_AGENTIC_WORKSPACE_v1.0.md)
- [Proposta de perfis de Agent e ferramentas de artefatos — PR #53](https://github.com/IGOR-SciDATA/mosaic/pull/53)

O contrato MVP v1.0 é citado por documentos arquiteturais, mas não está versionado no caminho esperado em `main`. Até ser reconciliado e adicionado ao repositório, não se deve usá-lo como um link de implementação inacessível nem alterar o schema por suposição.

---

<div align="center">

# ◈ MOSAIC

### Intelligence can change. Continuity remains.

**Core persists.** · **Models evolve.** · **Memory survives.** · **Projects continue.**

🇧🇷 **Construindo tecnologia de IA com foco em autonomia, continuidade e soberania tecnológica.**

<sub>MOSAIC · FOUNDATION · 2026</sub>

</div>
