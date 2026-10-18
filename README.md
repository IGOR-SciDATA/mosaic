<div align="center">

<br>

# ◈ MOSAIC

### Core de inteligência pessoal · Memória · Contexto · Estado · Continuidade

<br>

<img src="assets/branding/mosaic-symbol.png" alt="Símbolo do Mosaic" width="360" />

### 🧩 Uma inteligência que não depende de um único modelo

**Mosaic é um workspace de IA local-first que organiza memória, conversas, projetos e execução de tarefas em um Core persistente.**

![Python](https://img.shields.io/badge/Python-FastAPI-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Database](https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Local First](https://img.shields.io/badge/Local--First-By%20Design-0F766E?style=for-the-badge)
![Models](https://img.shields.io/badge/Models-User%20Selected-0891B2?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active%20Development-DC2626?style=for-the-badge)

**🧠 Core** · **💾 Memória** · **📍 Estado** · **🧭 Contexto** · **🔌 Modelos** · **🛠️ Ferramentas** · **♾️ Continuidade**

[🇧🇷 Soberania tecnológica](#-soberania-tecnológica-brasileira) · [Visão](#-visão) · [O que o Mosaic faz](#-o-que-o-mosaic-faz) · [Arquitetura](#️-arquitetura) · [Princípios](#-princípios) · [Próximos objetivos](#️-próximos-objetivos) · [Instalação](#-instalação) · [Documentação](#-documentação)

</div>

---

# 🖥️ Interface Web

O Mosaic reúne conversas, projetos, seleção de modelo e recursos do Core em uma interface web. A captura abaixo mostra a interface do projeto.

<div align="center">

<img src="assets/branding/download.png" alt="Interface web do Mosaic" width="100%" />

<sub>Mosaic · Workspace de inteligência pessoal</sub>

</div>

---

# 🇧🇷 Soberania tecnológica brasileira

O Mosaic nasce com uma ambição estratégica: **contribuir para que o Brasil desenvolva e controle mais da própria infraestrutura de inteligência artificial**.

Nossa arquitetura prioriza controle sobre dados, estado e execução, com suporte a modelos locais e a possibilidade de substituir o modelo sem transferir a ele a identidade e a memória do sistema. O objetivo é reduzir dependências desnecessárias e ampliar a capacidade brasileira de criar, operar e evoluir tecnologia própria.

- 🇧🇷 Fortalecer a soberania de dados e o controle sobre informações estratégicas.
- 🧠 Desenvolver conhecimento, software e capacidade técnica no Brasil.
- 🔓 Reduzir dependências externas quando elas não forem necessárias.
- 💻 Priorizar execução local e modelos abertos quando forem adequados.
- 🏗️ Criar uma base modular para aplicações e produtos tecnológicos nacionais.

> **Soberania de dados. Inteligência estratégica. Tecnologia brasileira.**

---

# 🌌 Visão

Um assistente pode responder a uma mensagem. Um ambiente de trabalho precisa lembrar decisões, recuperar informações relevantes, acompanhar tarefas e saber onde um projeto parou.

O Mosaic transforma conversas com IA em uma experiência persistente. A ideia é simples: poder perguntar **“Mosaic, lembra onde paramos no Projeto X?”** e recuperar o contexto útil — decisões, preferências, tarefas, arquivos, resultados e próximos passos — sem depender de procurar manualmente uma conversa antiga.

O modelo pode mudar. O computador pode mudar. A interface pode evoluir.

**O Mosaic deve preservar a continuidade.**

*The model is just one piece. The true product is continuity.*

---

# ✨ O que o Mosaic faz

## 💾 Memória que atravessa conversas

O Mosaic possui uma camada própria de memória e persistência, separada dos pesos do modelo. Isso permite registrar informações relevantes, recuperar memórias de forma global e usar preferências e decisões como contexto em interações posteriores.

## 🧭 Contexto orientado ao trabalho

O Core reúne o contexto relevante para uma conversa ou tarefa, em vez de depender de reenviar indiscriminadamente todo o histórico. Memória, histórico, estado do projeto e contexto são tratados como conceitos distintos.

## 🗂️ Conversas e projetos persistentes

Conversas, mensagens, projetos e tarefas possuem estrutura própria. Essa base permite construir continuidade entre sessões e evoluir para uma visão clara de objetivos, decisões, arquivos e próximos passos.

## 🤖 Agent e execução de tarefas

O Mosaic já possui uma base de Agent e ciclo de tarefas integrado ao Core. A arquitetura prevê que o modelo proponha ações, enquanto o Core valida chamadas de ferramentas, aplica controles, registra resultados e acompanha o estado da tarefa.

## 🛠️ Ferramentas com controle do Core

O projeto inclui uma camada de ferramentas e mecanismos de validação e aprovação. A direção é permitir que o Mosaic vá além de responder: consultar informações, trabalhar com arquivos e executar etapas delimitadas, sempre respeitando as regras do Core.

## 🔌 Modelo escolhido pelo usuário

O modelo é uma peça substituível. O usuário escolhe o modelo utilizado na conversa; memória, estado, contexto e regras pertencem ao Mosaic, não ao provedor de inferência.

---

# 🏗️ Arquitetura

A base tecnológica do Mosaic é **React + Vite**, **FastAPI**, **SQLite**, workspace local e uma camada de integração com modelos, incluindo Ollama.

~~~text
React + Vite
  └─ Conversas, projetos e experiência de trabalho
              │ REST / SSE
              ▼
FastAPI — MOSAIC CORE
  ├─ Conversation / Project / Message / Memory / Model
  ├─ Context Manager e estado de projeto
  ├─ Task Engine + ciclo de Agent
  ├─ ModelProvider — modelo selecionado na conversa
  ├─ Tool Registry / ToolCall / ToolResult
  ├─ Action / política / aprovação
  └─ Eventos e persistência
              │
              ▼
SQLite + workspace local + provider configurado
              │
              └─ Ollama / modelo local
~~~

### O ciclo de execução

~~~text
Pedido
  → Task
  → contexto relevante
  → decisão do modelo
  → validação pelo Core
  → aprovação, quando necessária
  → execução controlada da ferramenta
  → resultado persistido
  → observação e validação
  → conclusão, falha ou retomada
~~~

O Harness universal deve coordenar esse ciclo reutilizando os componentes do Core. Não é um segundo Core nem um mecanismo paralelo de estado.

---

# 🎯 Princípios

| Princípio | Significado |
|---|---|
| 🧠 **MODEL ≠ ACCESS** | O modelo pode propor ações; o Core decide o que é permitido. |
| 💾 **MEMORY ≠ TRUTH** | Uma lembrança não é automaticamente um fato verificado. |
| 🕒 **HISTORY ≠ MODEL MEMORY** | O histórico é persistido pelo Mosaic, não depende dos pesos do modelo. |
| 🧭 **CONTEXT ≠ FULL HISTORY** | Cada tarefa recebe contexto relevante e limitado. |
| 🛠️ **TOOL CALL ≠ TOOL EXECUTION** | Uma chamada proposta precisa ser validada antes de executar. |
| 📘 **SKILL ≠ PERMISSION** | Instruções especializadas não concedem acesso nem ignoram aprovações. |
| 🧩 **HARNESS ≠ SECOND CORE** | O Harness coordena componentes existentes sem duplicar o dono do estado. |
| 📍 **MOSAIC OWNS STATE** | O Core é responsável pelo estado, pelas políticas e pela conclusão. |
| 🔌 **MODEL ≠ IDENTITY** | Trocar o modelo não deve apagar a continuidade. |

> **Não construir porque podemos. Construir porque precisamos.**

---

# 🧠 Memória, histórico, estado e contexto

Esses conceitos se complementam, mas não são a mesma coisa:

- **Memória:** informações relevantes que podem ser recuperadas em outros momentos.
- **Histórico:** registro do que aconteceu nas conversas e execuções.
- **Estado:** situação atual de um projeto ou tarefa.
- **Contexto:** seleção do que é relevante para o trabalho atual.
- **Conhecimento:** informação acompanhada de origem e, quando possível, evidência verificável.
- **Skill:** procedimento reutilizável que orienta como executar um tipo de trabalho.

Essa separação permite que o Mosaic preserve continuidade, limite o contexto enviado ao modelo e evolua sem ficar preso a um único modelo ou fornecedor.

---

# 🗺️ Próximos objetivos

O desenvolvimento segue incrementos pequenos, com validação de cada etapa antes de ampliar a autonomia.

| Etapa | Objetivo |
|---|---|
| **1. Consolidar a fundação** | Alinhar os contratos, persistência e ciclo de vida; provar os fluxos centrais com testes reproduzíveis. |
| **2. Fortalecer o Harness** | Integrar decisão do modelo, ferramentas, políticas, resultados, eventos, cancelamento e retomada em um único ciclo confiável. |
| **3. Agent por conversa** | Permitir configurar identidade e instruções por conversa, habilitar Skills e preservar snapshots por tarefa. |
| **4. Contexto e recuperação** | Evoluir a seleção de contexto, a busca em arquivos e a recuperação com proveniência e avaliação de qualidade. |
| **5. Ferramentas e artefatos** | Melhorar leitura e escrita controladas, pesquisa com fontes e criação/validação de arquivos de saída. |
| **6. Frontend** | Simplificar a navegação, ampliar a área de chat, melhorar tamanho e hierarquia das fontes, legibilidade, responsividade e estados de execução. |
| **7. Fluxos completos** | Validar tarefas de análise, pesquisa, documentos e software de ponta a ponta, incluindo falhas e retomada. |
| **8. Autonomia limitada** | Ampliar a capacidade de concluir tarefas dentro de limites explícitos, com controles e evidências. |
| **9. Extensibilidade futura** | Considerar coordenação paralela somente depois de comprovar isolamento, concorrência e recuperação. |

O objetivo não é acumular funcionalidades isoladas. É fazer com que o Mosaic consiga **entender uma tarefa, reunir o contexto certo, agir por etapas, verificar o resultado e preservar o trabalho realizado**.

---

# 🚀 Instalação

## Pré-requisitos

- [Git](https://git-scm.com/)
- [Python](https://www.python.org/)
- [Node.js](https://nodejs.org/)
- [Ollama](https://ollama.com/) para utilizar um modelo local

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

Configure e selecione o modelo no Mosaic. O desempenho depende do hardware e da tarefa.

## 4. Frontend

Em outro terminal, na raiz do repositório:

~~~bash
cd frontend
npm install
npm run dev
~~~

Abra a URL local informada pelo Vite, normalmente http://localhost:5173.

---

# 📚 Documentação do projeto

- [Roadmap Mestre — Harness Universal](docs/MOSAIC_MASTER_ROADMAP_UNIVERSAL_HARNESS_v1.0.md)
- [Contrato oficial do Harness v1.2](docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md)
- [Contrato RAGNES — contexto e recuperação](docs/MOSAIC_RAGNES_CONTEXT_SYSTEM_CONTRACT_v1.0.md)
- [Contrato de UX do frontend](docs/MOSAIC_FRONTEND_UX_IMPLEMENTATION_CONTRACT_v1.0.md)
- [Guia de desenvolvimento do workspace agêntico](docs/MOSAIC_DEVELOPMENT_GUIDE_AGENTIC_WORKSPACE_v1.0.md)
- [Plano de implementação passo a passo](docs/MOSAIC_IMPLEMENTATION_EXECUTION_PLAN_v1.0.md)
- [Perfis de Agent e ferramentas de artefatos](docs/MOSAIC_AGENT_PROFILES_AND_ARTIFACT_TOOLS_ROADMAP_v1.0.md)

---

<div align="center">

# ◈ MOSAIC

### Intelligence can change. Continuity remains.

**Core persists.** · **Models evolve.** · **Memory survives.** · **Projects continue.**

🇧🇷 **Construindo tecnologia de IA com foco em autonomia, continuidade e soberania tecnológica.**

<sub>MOSAIC · FOUNDATION · 2026</sub>

</div>
