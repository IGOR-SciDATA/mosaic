<div align="center">

<br>

# ◈ MOSAIC

### Core de inteligência pessoal · Memória · Contexto · Estado · Continuidade

<br>

<img
  src="assets/branding/mosaic-symbol.png"
  alt="Mosaic — símbolo do projeto"
  width="520"
/>

<br>

### 🧩 Uma inteligência que não depende de um modelo

<br>

**Mosaic é um núcleo de inteligência pessoal projetado para preservar identidade, memória, contexto, projetos e continuidade independentemente do modelo de IA utilizado.**

<br>

![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Architecture](https://img.shields.io/badge/Architecture-Core%20First-8B0000?style=for-the-badge)
![Offline](https://img.shields.io/badge/Offline-First-111111?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-Model%20Independent-444444?style=for-the-badge)

![Memory](https://img.shields.io/badge/Memory-Persistent-8B0000?style=flat-square)
![State](https://img.shields.io/badge/State-Explicit-555555?style=flat-square)
![Models](https://img.shields.io/badge/Models-Replacable-555555?style=flat-square)
![Version](https://img.shields.io/badge/MOSAIC-v0.1.0-8B0000?style=flat-square)

<br>

**🧠 Core** · **🧬 Identity** · **💾 Memory** · **📍 State** · **📚 Knowledge** · **🧭 Context** · **🔌 Models** · **♾️ Continuity**

<br>

[Visão](#-visão) ·
[Princípios](#-princípios) ·
[Arquitetura](#️-arquitetura) ·
[Core](#-mosaic-core) ·
[Memória](#-memória) ·
[Estado](#-estado) ·
[Contexto](#-contexto) ·
[Modelos](#-modelos) ·
[Continuidade](#-continuidade) ·
[MVP](#-mvp) ·
[Estrutura](#-estrutura-do-projeto) ·
[Status](#-status) ·
[Roadmap](#️-roadmap)

<br>

</div>

---

# 🌌 Visão

**Mosaic** nasce de uma ideia simples:

> **A inteligência não deve estar presa ao modelo que a executa.**

Um modelo de linguagem é apenas uma parte do sistema.

O Mosaic foi concebido para manter fora do modelo aquilo que realmente precisa sobreviver:

- identidade;
- memória;
- histórico;
- conhecimento;
- projetos;
- estado atual;
- decisões;
- contexto;
- princípios;
- continuidade.

O modelo pode mudar.

O computador pode mudar.

A infraestrutura pode mudar.

O modelo pode até deixar de existir.

**O Mosaic deve continuar sendo o Mosaic.**

---

# 🧩 O problema

Os assistentes atuais normalmente tratam a conversa como o centro do sistema.

```text
USUÁRIO
   │
   ▼
MODELO
   │
   ▼
RESPOSTA
```

Isso funciona muito bem para perguntas isoladas.

Mas projetos reais possuem continuidade.

Uma pessoa pode dizer:

```text
"Mosaic, onde paramos naquele projeto?"
```

E a resposta não deveria depender de encontrar manualmente uma conversa antiga.

O sistema precisa compreender:

```text
PROJETO
├── objetivo
├── estado atual
├── decisões
├── tarefas concluídas
├── tarefas pendentes
├── bloqueios
├── arquivos
├── histórico
└── última atividade
```

O objetivo do Mosaic é transformar a IA de uma simples interface de conversa em uma **camada persistente de continuidade**.

---

# 🎯 Princípios

| Princípio | Objetivo |
|---|---|
| 🧠 **Core First** | A lógica principal pertence ao Mosaic, não ao modelo |
| 🧬 **Identidade** | Preservar uma identidade estável entre modelos e sessões |
| 💾 **Memória externa** | Memória persistente fora dos pesos neurais |
| 📍 **Estado explícito** | Saber o que está acontecendo agora, não apenas o que aconteceu |
| 🧭 **Contexto** | Entregar ao modelo somente o contexto relevante |
| 🔌 **Model Independence** | Permitir trocar o modelo sem reconstruir o Mosaic |
| 🔐 **Controle** | Dados e memória pertencem ao usuário |
| 📴 **Offline First** | O núcleo não deve depender de internet para existir |
| 🧩 **Simplicidade** | Não adicionar complexidade sem necessidade |
| ♾️ **Continuidade** | Projetos e identidade devem sobreviver a sessões e tecnologias |

> **Não construir porque podemos. Construir porque precisamos.**

---

# 🏗️ Arquitetura

O Mosaic separa o que é **sistema** do que é **modelo de inteligência**.

```mermaid
flowchart TB

    USER["🧑 USUÁRIO"]

    subgraph MOSAIC["◈ MOSAIC CORE"]
        ID["🧬 Identity"]
        MEM["💾 Memory"]
        STATE["📍 State"]
        KNOW["📚 Knowledge"]
        CTX["🧭 Context Builder"]
        ROUTER["🔌 Model Router"]
    end

    subgraph MODELS["🧠 MODEL LAYER"]
        LOCAL["💻 Modelo Local"]
        ONLINE["🌐 Modelo Online"]
        HYBRID["🔀 Modelo Híbrido"]
    end

    USER --> MOSAIC

    ID --> CTX
    MEM --> CTX
    STATE --> CTX
    KNOW --> CTX

    CTX --> ROUTER

    ROUTER --> LOCAL
    ROUTER --> ONLINE
    ROUTER --> HYBRID

    LOCAL --> ROUTER
    ONLINE --> ROUTER
    HYBRID --> ROUTER

    ROUTER --> USER
```

A regra fundamental é:

```text
MOSAIC CORE
    │
    ├── identidade
    ├── memória
    ├── estado
    ├── conhecimento
    ├── contexto
    └── regras
            │
            ▼
       MODEL LAYER
```

O modelo **serve ao Core**.

O Core não pertence ao modelo.

---

# 🧠 Mosaic Core

O **Mosaic Core** é o centro do sistema.

Ele não é um modelo de linguagem.

É a camada responsável por organizar e preservar a inteligência persistente do usuário.

```text
                 ◈ MOSAIC CORE

        ┌─────────────────────────┐
        │        IDENTITY         │
        ├─────────────────────────┤
        │         MEMORY          │
        ├─────────────────────────┤
        │          STATE          │
        ├─────────────────────────┤
        │        KNOWLEDGE        │
        ├─────────────────────────┤
        │         CONTEXT         │
        ├─────────────────────────┤
        │          RULES          │
        ├─────────────────────────┤
        │      MODEL ROUTER       │
        └─────────────────────────┘
```

O Core deve permanecer funcional mesmo que nenhum modelo específico seja considerado permanente.

---

# 🧬 Identidade

A identidade é a representação persistente de quem é o Mosaic.

Ela pode conter:

```text
identity/
├── name
├── personality
├── principles
├── capabilities
├── preferences
└── configuration
```

A identidade não deve ser reconstruída a cada conversa.

Ela deve ser carregada pelo Core e apresentada ao modelo quando necessário.

```text
MODELO
   ↓
troca

IDENTIDADE
   ↓
permanece
```

---

# 💾 Memória

A memória pertence ao Mosaic.

Não ao modelo.

```text
memory/
├── episodic/
├── semantic/
├── people/
├── projects/
├── decisions/
├── lessons/
├── observations/
├── timeline/
└── archive/
```

A memória deve permitir preservar acontecimentos relevantes, decisões, aprendizados e informações autorizadas pelo usuário.

### Ciclo

```mermaid
flowchart LR

    E["🌎 Experiência"]
    O["👁️ Observação"]
    C["🧠 Consolidação"]
    M["💾 Memória"]
    R["🔍 Recuperação"]
    CTX["🧭 Contexto"]

    E --> O
    O --> C
    C --> M
    M --> R
    R --> CTX
```

Uma informação recebida não deve automaticamente se tornar conhecimento confiável.

O sistema deve poder distinguir:

```text
fato
evidência
hipótese
opinião
memória
inferência
incerteza
```

---

# 📍 Estado

O **State** é uma das separações fundamentais do Mosaic.

Memória, conhecimento e estado não são a mesma coisa.

```text
MEMORY
= o que aconteceu

KNOWLEDGE
= o que o sistema considera que sabe

STATE
= onde as coisas estão agora
```

Um projeto pode possuir:

```yaml
project:
  name: "Projeto X"

  status: "in_progress"

  current_goal: "Implementar o Core"

  current_phase: "context"

  decisions:
    - "Core independente do modelo"

  completed_tasks:
    - "Definir arquitetura inicial"

  pending_tasks:
    - "Implementar Context Builder"

  blockers:
    - null

  files:
    - "README.md"

  last_activity:
    - "2026-10-04"
```

Isso permite uma pergunta como:

```text
"Mosaic, onde paramos no Projeto X?"
```

ser respondida pelo **estado persistente do projeto**, e não apenas por uma busca textual em conversas antigas.

---

# 🧭 Contexto

O modelo não precisa receber tudo.

O Mosaic deve construir o contexto necessário para cada interação.

```mermaid
flowchart TB

    INPUT["💬 Mensagem do usuário"]

    INTENT["🔎 Interpretação"]

    MEMORY["💾 Memória relevante"]
    STATE["📍 Estado relevante"]
    KNOW["📚 Conhecimento relevante"]
    ID["🧬 Identidade"]
    HISTORY["🕒 Histórico relevante"]

    CONTEXT["🧭 Context Builder"]

    MODEL["🧠 Modelo"]

    INPUT --> INTENT

    INTENT --> MEMORY
    INTENT --> STATE
    INTENT --> KNOW
    INTENT --> ID
    INTENT --> HISTORY

    MEMORY --> CONTEXT
    STATE --> CONTEXT
    KNOW --> CONTEXT
    ID --> CONTEXT
    HISTORY --> CONTEXT

    CONTEXT --> MODEL
```

A função do Context Builder é transformar o estado persistente do Mosaic em um contexto útil para o modelo.

---

# 🔌 Model Layer

Modelos são componentes substituíveis.

O Mosaic não deve depender permanentemente de:

- um fornecedor;
- uma API;
- um modelo específico;
- uma arquitetura;
- uma GPU;
- uma conexão com a internet.

O sistema poderá utilizar:

```text
MODELO LOCAL
      │
      ├── desenvolvimento
      ├── offline
      └── privacidade

MODELO ONLINE
      │
      ├── maior capacidade
      └── tarefas específicas

MODELO HÍBRIDO
      │
      ├── local
      └── online
```

O **Model Router** decide qual modelo utilizar quando necessário.

```text
MOSAIC CORE
     │
     ▼
MODEL ROUTER
     │
     ├── Local
     ├── Online
     └── Hybrid
```

Trocar o modelo não deve apagar a memória.

---

# 🔄 Ciclo de execução

O fluxo fundamental do Mosaic é:

```text
USUÁRIO
   │
   ▼
INPUT
   │
   ▼
INTERPRETER
   │
   ▼
IDENTITY
   │
   ├───────────────┐
   ▼               ▼
MEMORY           STATE
   │               │
   └───────┬───────┘
           ▼
      KNOWLEDGE
           │
           ▼
    CONTEXT BUILDER
           │
           ▼
      MODEL ROUTER
           │
           ▼
         MODEL
           │
           ▼
       RESPONSE
           │
           ▼
    CORE PERSISTENCE
```

O ponto importante é que a resposta não termina no modelo.

O Core pode atualizar:

```text
memória
estado
histórico
projeto
decisões
aprendizados
```

quando apropriado.

---

# ♾️ Continuidade

O Mosaic foi pensado para sobreviver a mudanças tecnológicas.

```text
             MOSAIC
                │
      ┌─────────┼─────────┐
      ▼         ▼         ▼
    Model    Computer   Interface
      │         │         │
      ▼         ▼         ▼
   muda       muda      muda

                │
                ▼

        IDENTITY + MEMORY
        STATE + KNOWLEDGE
        HISTORY + PRINCIPLES

                │
                ▼

             CONTINUA
```

A continuidade é baseada em dados persistentes e independentes do modelo.

Uma conversa iniciada hoje deve poder ser retomada no futuro.

Um projeto não deve perder seu estado porque o modelo utilizado mudou.

---

# 📴 Offline First

O Mosaic deve priorizar operação local.

```text
                 INTERNET
                    │
                    │ opcional
                    ▼
             ┌───────────────┐
             │    MOSAIC     │
             │               │
             │ Core          │
             │ Memory        │
             │ State         │
             │ Knowledge     │
             │ Local Model   │
             └───────────────┘
```

**Offline First ≠ Offline Always**

A internet pode ampliar capacidades.

Ela não deve ser um requisito para a existência do Core.

Isso permite:

- uso local;
- maior controle dos dados;
- operação offline;
- independência de APIs;
- substituição de fornecedores;
- migração de modelos.

---

# 🧩 Simplicidade por design

O Mosaic não pretende começar como uma plataforma distribuída gigantesca.

O princípio inicial é:

> **Simple first. Modular by design. Expand only when necessary.**

O MVP deliberadamente evita complexidade prematura.

Não fazem parte do primeiro núcleo:

```text
❌ Multi-agent complexo
❌ Microsserviços
❌ Kubernetes
❌ Vector database obrigatório
❌ RAG complexo
❌ Dezenas de APIs
❌ Infraestrutura cloud obrigatória
❌ Orquestração desnecessária
```

O objetivo é construir primeiro aquilo que prova a ideia central.

---

# 🚀 MVP

O primeiro Mosaic funcional deve ser pequeno.

```text
┌─────────────────────────────┐
│        MOSAIC MVP           │
├─────────────────────────────┤
│ 🧬 Identity                │
│ 💾 Memory                  │
│ 📍 State                   │
│ 🧭 Context Builder         │
│ 🔌 Model Router            │
│ 🧠 Local Model             │
│ 💬 CLI Chat                │
└─────────────────────────────┘
```

### Stack inicial

```text
Python
SQLite
Arquivos locais
Modelo local
CLI
```

A interface pode posteriormente receber uma camada web sem alterar o Core.

---

# 💡 O que diferencia o Mosaic?

Mosaic não tenta competir simplesmente oferecendo:

> "um modelo que conversa melhor."

A proposta é diferente.

```text
CHATBOT TRADICIONAL

Usuário
   ↓
Modelo
   ↓
Resposta
```

```text
MOSAIC

Usuário
   ↓
Mosaic Core
   │
   ├── Identity
   ├── Memory
   ├── State
   ├── Knowledge
   ├── Context
   ├── History
   └── Rules
          ↓
     Model Router
          ↓
        Model
```

O modelo é apenas uma peça.

O verdadeiro produto é a **continuidade**.

O usuário não precisa possuir um modelo específico.

Ele possui uma estrutura persistente capaz de utilizar diferentes modelos.

---

# 🖥️ Interface

A primeira interface pode ser simples:

```text
┌──────────────────────────────────────────┐
│                  MOSAIC                  │
├──────────────────────────────────────────┤
│                                          │
│  Você: onde paramos no Projeto X?        │
│                                          │
│  Mosaic:                                 │
│  O projeto está na fase de contexto.     │
│  A última decisão foi separar State      │
│  de Memory. O próximo passo é...         │
│                                          │
├──────────────────────────────────────────┤
│  > digite uma mensagem...                │
└──────────────────────────────────────────┘
```

A interface existe para testar o conceito.

O Core não deve depender dela.

---

# 📁 Estrutura do projeto

Uma estrutura inicial simples:

```text
mosaic/
│
├── config/
│   └── identity/
│
├── src/
│   └── mosaic/
│       ├── core/
│       ├── identity/
│       ├── memory/
│       ├── state/
│       ├── knowledge/
│       ├── context/
│       ├── models/
│       ├── router/
│       └── interfaces/
│
├── memory/
│
├── knowledge/
│
├── state/
│
├── models/
│
├── data/
│
├── docs/
│
├── tests/
│
├── README.md
└── pyproject.toml
```

| Diretório | Responsabilidade |
|---|---|
| `src/mosaic/core/` | núcleo do sistema |
| `src/mosaic/identity/` | identidade persistente |
| `src/mosaic/memory/` | memória |
| `src/mosaic/state/` | estado atual |
| `src/mosaic/knowledge/` | conhecimento |
| `src/mosaic/context/` | construção de contexto |
| `src/mosaic/models/` | integração com modelos |
| `src/mosaic/router/` | roteamento entre modelos |
| `src/mosaic/interfaces/` | CLI e futuras interfaces |
| `memory/` | dados persistentes de memória |
| `state/` | estado persistente |
| `knowledge/` | base de conhecimento |
| `docs/` | documentação |
| `tests/` | testes |

---

# 🚦 Status

| Sistema | Status |
|---|:---:|
| 🧩 Conceito do Core | 🟢 |
| 🧬 Identity | 🟡 |
| 💾 Memory | 🟡 |
| 📍 State | 🟡 |
| 🧭 Context Builder | 🟡 |
| 🔌 Model Router | 🟡 |
| 🧠 Modelo local | 🟡 |
| 💬 Interface CLI | 🟡 |
| 📚 Knowledge | 🔵 |
| 🌐 Interface Web | 🔵 |
| 🔐 Segurança avançada | 🔵 |
| ♾️ Continuity / Seed | 🔵 |

**Legenda:** 🟢 definido · 🟡 em desenvolvimento · 🔵 planejado

> O status deve refletir o estado real do repositório. Não marcar como implementado aquilo que ainda existe apenas como arquitetura.

---

# 🗺️ Roadmap

```text
FOUNDATION
   │
   ├── 01 Core
   ├── 02 Identity
   └── 03 Persistence
        │
        ▼
MEMORY & STATE
   │
   ├── 04 Memory
   ├── 05 State
   ├── 06 Projects
   └── 07 History
        │
        ▼
CONTEXT
   │
   ├── 08 Interpreter
   ├── 09 Context Builder
   └── 10 Retrieval
        │
        ▼
MODELS
   │
   ├── 11 Local Model
   ├── 12 Model Router
   └── 13 Model Switching
        │
        ▼
INTERACTION
   │
   ├── 14 CLI
   └── 15 Web Interface
        │
        ▼
CONTINUITY
   │
   ├── 16 Export
   ├── 17 Import
   ├── 18 Seed
   └── 19 Migration
        │
        ▼
EXPANSION
   │
   ├── 20 Knowledge
   ├── 21 Tools
   ├── 22 Voice
   ├── 23 Vision
   └── 24 Physical Interfaces
```

---

# 🔐 Controle e propriedade

A visão do Mosaic é que a memória e os dados do usuário sejam controláveis e transportáveis.

O sistema deve caminhar para permitir:

```text
EXPORTAR
   ↓
MOSAIC DATA

IMPORTAR
   ↓
NOVO AMBIENTE

TROCAR MODELO
   ↓
MEMÓRIA PRESERVADA

TROCAR COMPUTADOR
   ↓
CONTINUIDADE PRESERVADA
```

A inteligência utilizada pode mudar.

Os dados que representam a continuidade do usuário não deveriam ficar presos a um fornecedor.

---

# 🌱 Visão de longo prazo

O Mosaic pode evoluir para muito além de um chat.

Mas a expansão deve acontecer a partir do Core.

```text
                 ◈ MOSAIC
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
   💬 Interface   🧠 Models    🛠️ Tools
       │            │            │
       └────────────┼────────────┘
                    │
                    ▼
               💾 CONTINUITY
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
       Projects  Knowledge  History
```

No futuro, o mesmo Core poderá sustentar:

- diferentes interfaces;
- diferentes modelos;
- diferentes dispositivos;
- diferentes ambientes;
- ferramentas;
- automações;
- voz;
- visão;
- robótica.

Mas nenhuma dessas extensões deve ser necessária para provar a ideia central.

---

# 🧠 A pergunta fundamental

O Mosaic deverá conseguir responder, ao longo do tempo:

**Quem sou?**

**O que sei?**

**O que aconteceu?**

**Em que projetos estou trabalhando?**

**Onde paramos?**

**O que decidimos?**

**O que precisa ser feito agora?**

**Qual contexto é relevante?**

**Qual modelo está sendo utilizado?**

**Como continuo se esse modelo desaparecer?**

---

<div align="center">

# ◈ MOSAIC

### Intelligence can change. Continuity remains.

<br>

**Core persists.**

**Models evolve.**

**Memory survives.**

**Projects continue.**

<br>

`MOSAIC · FOUNDATION · 2026`

</div>
