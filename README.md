<div align="center">

<br>

# ◈ MOSAIC

### Core de inteligência pessoal · Memória · Contexto · Estado · Continuidade

<br>

<img src="assets/branding/mosaic-symbol.png" alt="Mosaic — símbolo do projeto" width="420" />

<br>

### 🧩 Uma inteligência que não depende de um modelo

**Mosaic é um workspace de IA local-first que busca preservar contexto, memória, projetos e continuidade enquanto modelos e tecnologias mudam.**

<br>

![Python](https://img.shields.io/badge/Python-FastAPI-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Database](https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Local First](https://img.shields.io/badge/Local--First-By%20Design-0F766E?style=for-the-badge)
![Models](https://img.shields.io/badge/Models-User%20Selected-0891B2?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active%20Development-DC2626?style=for-the-badge)

<br>

**🧠 Core** · **💾 Memória** · **📍 Estado** · **🧭 Contexto** · **🔌 Modelos** · **🛠️ Ferramentas** · **♾️ Continuidade**

<br>

[🇧🇷 Soberania tecnológica](#-soberania-tecnológica-brasileira) · [Visão](#-visão) · [Princípios](#-princípios) · [Interface](#️-interface-web) · [Arquitetura](#️-arquitetura) · [Estado atual](#-estado-atual) · [Roadmap](#️-roadmap) · [Instalação](#-instalação) · [Documentação](#-documentação)

</div>

---

# 🖥️ Interface Web

A interface web atual reúne conversas, projetos, seleção explícita de modelo e informações de contexto em um workspace único. A imagem abaixo é uma captura do ambiente de desenvolvimento — uma demonstração da interface existente, não uma representação de funcionalidades futuras.

<div align="center">

<img src="assets/branding/download.png" alt="Captura da interface web atual do Mosaic" width="100%" />

<sub>Interface web do Mosaic · Captura do ambiente de desenvolvimento</sub>

</div>

---

# 🇧🇷 Soberania tecnológica brasileira

O Mosaic não é apenas um experimento de assistente pessoal. Ele também nasce de uma ambição estratégica: **contribuir para que o Brasil desenvolva e controle mais da própria infraestrutura de inteligência artificial**.

A dependência de modelos, APIs, plataformas e infraestrutura de terceiros pode criar limitações sobre custo, acesso, privacidade, continuidade e autonomia tecnológica. O Mosaic explora uma abordagem diferente: manter o núcleo do sistema, os dados persistentes e as regras de execução sob controle do próprio ambiente, permitindo substituir os modelos utilizados.

Nossa visão é contribuir para um ecossistema brasileiro capaz de:

- 🇧🇷 Fortalecer a soberania de dados e o controle sobre informações estratégicas.
- 🧠 Desenvolver conhecimento, software e capacidade técnica no Brasil.
- 🔓 Reduzir dependências tecnológicas externas quando elas não forem necessárias.
- 💻 Priorizar execução local e modelos abertos quando forem adequados.
- 🏗️ Criar uma base modular que possa evoluir para produtos e aplicações nacionais.
- 🤝 Colaborar com uma indústria brasileira de IA mais autônoma e sustentável.

Isso é uma **direção estratégica do projeto**, não uma alegação de independência total já alcançada. O Mosaic pode integrar serviços externos quando fizer sentido, mas essa dependência não deve ser imposta como requisito central nem retirar do usuário o controle sobre seus dados e escolhas.

> **Soberania de dados. Inteligência estratégica. Tecnologia brasileira.**

---

# 🌌 Visão

Um chatbot normalmente concentra a experiência na conversa e no modelo que responde. Mas o trabalho real se estende para além de uma resposta: existem projetos, arquivos, decisões, tarefas, resultados e pendências que precisam continuar existindo.

O Mosaic busca transformar a interação com IA em um **ambiente persistente de trabalho**.

Imagine perguntar:

> “Mosaic, lembra onde paramos no Projeto X?”

A intenção é recuperar o estado relevante do projeto — objetivo, decisões, tarefas, arquivos, resultados e próximos passos — sem depender de encontrar manualmente uma conversa antiga.

O modelo pode mudar. O computador pode mudar. A interface pode mudar.

**O Mosaic deve preservar a continuidade.**

*The model is just one piece. The true product is continuity.*

---

# 🧩 O problema que queremos resolver

~~~text
ASSISTENTE CONVENCIONAL
Usuário → Modelo → Resposta
~~~

Esse fluxo é útil para perguntas pontuais. Porém, projetos longos precisam de uma estrutura persistente:

~~~text
PROJETO
├── objetivo e estado atual
├── decisões e histórico
├── tarefas concluídas e pendentes
├── arquivos e artefatos
├── resultados e bloqueios
└── próxima ação
~~~

O objetivo não é apenas produzir respostas melhores. É fazer com que o sistema consiga **retomar trabalho com contexto, respeitar decisões anteriores e demonstrar o que realmente fez**.

---

# 🎯 Princípios arquiteturais

| Princípio | O que significa |
|---|---|
| 🧠 **MODEL ≠ ACCESS** | O modelo pode propor ações; o Core decide o que é permitido. |
| 💾 **MEMORY ≠ TRUTH** | Uma informação lembrada não é automaticamente um fato verificado. |
| 🕒 **HISTORY ≠ MODEL MEMORY** | O histórico é persistido pelo sistema, não depende dos pesos do modelo. |
| 🧭 **CONTEXT ≠ FULL HISTORY** | Cada tarefa recebe contexto relevante e limitado. |
| 🛠️ **TOOL CALL ≠ TOOL EXECUTION** | Uma chamada proposta precisa ser validada antes de executar; o resultado deve ser registrado. |
| 📘 **SKILL ≠ PERMISSION** | Instruções especializadas não concedem acesso nem ignoram aprovações. |
| 🧩 **HARNESS ≠ SECOND CORE** | A coordenação reutiliza os componentes do Core; não cria um segundo dono do estado. |
| 📍 **MOSAIC OWNS STATE** | O Core é a fonte autoritativa do estado, das políticas e da conclusão das tarefas. |
| 🔌 **MODEL ≠ IDENTITY** | Trocar o modelo não deve reconstruir a identidade nem apagar a continuidade. |

> **Não construir porque podemos. Construir porque precisamos.**

---

# 🏗️ Arquitetura

A base tecnológica atual é **React + Vite**, **FastAPI**, **SQLite**, workspace local e uma abstração de provider com suporte a **Ollama**.

~~~text
┌───────────────────────────────────────────┐
│               REACT + VITE                │
│ Conversas · Projetos · Seleção de modelo  │
│           Experiência de trabalho         │
└─────────────────────┬─────────────────────┘
                      │ REST / SSE
                      ▼
┌───────────────────────────────────────────┐
│               MOSAIC CORE                 │
│ Conversations / Projects / Messages       │
│ Context Manager / Memory / Project State │
│ Task Engine / Agent Loop                 │
│ ModelProvider (modelo escolhido usuário) │
│ Tool Registry / ToolCall / ToolResult    │
│ Política · Permissões · Aprovações       │
│ Persistência · Resultados                │
└─────────────────────┬─────────────────────┘
                      ▼
       SQLite · Workspace local · Ollama
~~~

### Uma regra importante sobre modelos

O usuário escolhe o modelo para a conversa. O Mosaic deve respeitar essa escolha: **sem roteamento automático, troca silenciosa de modelo ou fallback oculto**. A camada de provider permite substituir modelos sem entregar a eles o controle do estado, das permissões ou da persistência.

### O ciclo que queremos consolidar

~~~text
Pedido do usuário
      ↓
Task persistida
      ↓
Política + contexto relevante
      ↓
Modelo escolhido propõe uma decisão
      ↓
Core valida a proposta
      ↓
Aprovação, quando necessária
      ↓
Ferramenta executa de forma controlada
      ↓
Resultado e evidências são persistidos
      ↓
Observação, validação e próximo passo
      ↓
Conclusão, bloqueio ou retomada explícita
~~~

O Harness é a evolução desse ciclo. Ele deve coordenar planejamento, ferramentas, observação e validação reutilizando o Core existente — sem criar um segundo sistema de estado.

---

# 🧠 Memória, estado e contexto

Esses conceitos se relacionam, mas não são intercambiáveis.

~~~text
MEMÓRIA   = o que foi registrado sobre experiências e informações
HISTÓRICO = o que aconteceu nas conversas e execuções
ESTADO    = onde um projeto ou tarefa está agora
CONTEXTO  = o subconjunto relevante para o trabalho atual
CONHECIMENTO = informação acompanhada de origem e grau de confiança
~~~

A memória deve permanecer fora dos pesos do modelo. O contexto deve ser montado pelo Mosaic, respeitando relevância, escopo e limites. Sempre que possível, informações recuperadas devem manter sua origem para que possam ser inspecionadas e corrigidas.

O objetivo é que a continuidade não dependa de um único modelo nem de uma conversa isolada.

---

# ♾️ Continuidade e independência

A arquitetura procura manter separados os dados persistentes e o modelo que os interpreta:

~~~text
             MOSAIC
                │
       ┌────────┼────────┐
       ▼        ▼        ▼
    Modelo   Máquina  Interface
       │        │        │
       └──── podem mudar ┘
                │
                ▼
       Estado + Memória
       Histórico + Arquivos
       Decisões + Princípios
                │
                ▼
          CONTINUIDADE
~~~

**Local-first não significa que tudo precise funcionar sempre offline.** Significa que a operação local é uma prioridade arquitetural, e que serviços externos devem ser opcionais quando possível, explícitos quando usados e substituíveis quando houver alternativa viável.

---

# 🚦 Estado atual

O repositório já possui uma base de aplicação web em evolução: frontend React/Vite, API FastAPI, persistência SQLite, conversas e projetos, gerenciamento de contexto, provider para modelos locais e componentes para tarefas, ferramentas e resultados.

Isso é uma base real para evoluir o produto — mas a presença de módulos ou testes isolados não comprova, por si só, que todos os fluxos estejam completos de ponta a ponta. O estado exato de cada capacidade deve ser confirmado pelo código da branch, testes reproduzíveis e execução integrada.

| Área | Situação |
|---|---|
| 🌐 Interface web e API | Base existente no repositório |
| 💾 Persistência, conversas e projetos | Componentes existentes; fluxos devem ser verificados |
| 🧭 Contexto e memória | Componentes existentes; qualidade de recuperação precisa de avaliação |
| 🔌 Provider Ollama | Integração existente; configuração local necessária |
| 🛠️ Ciclo de Agent e ferramentas | Base de implementação existente; integração ponta a ponta em validação |
| 🔐 Aprovação, segurança e recuperação | Precisam ser demonstradas nos fluxos integrados |
| 📄 Geração e validação de artefatos | Evolução planejada por formato e critérios de qualidade |
| 🧪 QA integrado | Prioridade antes de ampliar autonomia |

**Importante:** esta tabela não declara todos os fluxos aprovados. A auditoria da Fase 0 deve atualizar o baseline com testes executados, resultados e lacunas verificadas.

---

# 🗺️ Roadmap

O roadmap segue o [Roadmap Mestre do Harness Universal](docs/MOSAIC_MASTER_ROADMAP_UNIVERSAL_HARNESS_v1.0.md). A prioridade é consolidar uma base confiável antes de ampliar a autonomia ou introduzir complexidade desnecessária.

| Fase | Objetivo |
|---|---|
| **0. Baseline** | Auditar o estado real do código, contratos, testes, segurança e fluxos integrados. |
| **1–3. Confiabilidade** | Reforçar estados e segurança; integrar execução com o modelo da conversa; persistir eventos, aprovações e retomada. |
| **4–6. Agent e contexto** | Perfis por conversa, instruções e Skills versionadas, coordenação de subtarefas e recuperação de contexto. |
| **7–9. Ferramentas e experiência** | Ferramentas controladas, artefatos e validadores; timeline e experiência de execução integradas. |
| **10. Interface** | Auditoria e simplificação da UX, chat mais amplo, menos ruído e detalhes técnicos sob demanda. |
| **11–12. Fluxos completos e avaliação** | Validar criação de documentos, pesquisa e software; medir qualidade, resiliência e autonomia limitada. |
| **13. Paralelismo controlado** | Considerar execução paralela somente após provar isolamento, concorrência, cancelamento e recuperação. |

**Próximo passo acordado: Fase 0 — auditoria do estado real.** Uma fase por PR, com validação antes de avançar. O roadmap é direção de trabalho, não uma lista de capacidades já entregues.

---

# 🚀 Instalação

## Pré-requisitos

- [Git](https://git-scm.com/)
- [Python](https://www.python.org/)
- [Node.js](https://nodejs.org/)
- [Ollama](https://ollama.com/) para usar um modelo local

## 1. Clonar o repositório

~~~bash
git clone https://github.com/IGOR-SciDATA/mosaic.git
cd mosaic
~~~

## 2. Preparar o backend

~~~bash
cd backend
python -m venv .venv
~~~

No Windows PowerShell:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

No Linux/macOS:

~~~bash
source .venv/bin/activate
~~~

Instale as dependências e inicie a API:

~~~bash
pip install -r requirements.txt
uvicorn app.main:app --reload
~~~

API: http://127.0.0.1:8000 · Documentação: http://127.0.0.1:8000/docs

## 3. Preparar um modelo local

Com o Ollama instalado, baixe o modelo recomendado para os testes iniciais em hardware modesto:

~~~bash
ollama pull qwen2.5:3b
~~~

O modelo precisa estar disponível e selecionado/configurado no Mosaic. Desempenho e qualidade variam conforme o hardware e a tarefa.

## 4. Iniciar o frontend

Em outro terminal, na raiz do repositório:

~~~bash
cd frontend
npm install
npm run dev
~~~

Abra a URL local informada pelo Vite, normalmente http://localhost:5173.

Esses passos descrevem a inicialização dos serviços; não substituem testes de compatibilidade do ambiente nem garantem que todos os fluxos do Harness estejam concluídos.

---

# 📚 Documentação

- [Roadmap Mestre — Harness Universal](docs/MOSAIC_MASTER_ROADMAP_UNIVERSAL_HARNESS_v1.0.md)
- [Contrato oficial do Harness v1.2](docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md)
- [Contrato RAGNES — contexto e recuperação](docs/MOSAIC_RAGNES_CONTEXT_SYSTEM_CONTRACT_v1.0.md)
- [Contrato de UX do frontend](docs/MOSAIC_FRONTEND_UX_IMPLEMENTATION_CONTRACT_v1.0.md)
- [Guia de desenvolvimento do workspace agêntico](docs/MOSAIC_DEVELOPMENT_GUIDE_AGENTIC_WORKSPACE_v1.0.md)
- [Proposta de perfis de Agent e ferramentas de artefatos — PR #53](https://github.com/IGOR-SciDATA/mosaic/pull/53)

Os contratos descrevem decisões e comportamentos pretendidos. O código mostra a implementação existente; testes e execuções reproduzíveis fornecem evidência do que funciona.

---

<div align="center">

# ◈ MOSAIC

### Intelligence can change. Continuity remains.

**Core persists.**  
**Models evolve.**  
**Memory survives.**  
**Projects continue.**

<br>

🇧🇷 **Construindo tecnologia de IA com foco em autonomia, continuidade e soberania tecnológica.**

<sub>MOSAIC · FOUNDATION · 2026</sub>

</div>
