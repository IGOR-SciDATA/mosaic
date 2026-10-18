# MOSAIC — MVP IMPLEMENTATION CONTRACT

**Status:** Official implementation contract  
**Version:** 1.0  
**Date:** 2026-10-05  
**Authority:** MASTER / Arquitetura

---

## 1. Purpose

This document is the implementation contract for the Mosaic MVP.

Its purpose is to remove ambiguity from implementation, especially around:

- database tables;
- field types;
- `NULL` vs `NOT NULL`;
- defaults;
- foreign keys;
- relationships;
- allowed values;
- lifecycle states;
- JSON/text fields;
- what belongs in the MVP;
- what explicitly does **not** belong in the MVP.

### Rule for Chat 01

Chat 01 must implement this document literally unless the Master explicitly changes it.

The implementer must **not invent fields, tables, states, relationships or infrastructure** merely because they appear useful.

If the existing repository conflicts with this document:

```text
STOP
↓
describe the conflict
↓
do not silently change architecture
↓
Master decides
```

---

# 2. Sources of truth

The Mosaic has two different sources of truth:

```text
DOCUMENTATION
→ architecture, contracts, decisions, roadmap

GITHUB
→ actual implementation
```

The implementation workflow is:

```text
MASTER
↓
decision / contract
↓
CHAT 01
↓
inspect current repository
↓
minimal implementation
↓
tests
↓
review diff
↓
commit
↓
MASTER validates coherence
```

---

# 3. MVP objective

The MVP exists to prove the Mosaic Core.

It must demonstrate:

```text
USER
↓
CONVERSATION
↓
MODEL
↓
CONTEXT
↓
RESPONSE
↓
PERSISTENCE
```

and progressively:

```text
MEMORY
↓
PROJECT
↓
TASK
↓
ACTION
↓
PERMISSION
↓
TOOL
↓
TOOL RESULT
↓
CONTEXT
↓
MODEL
```

The MVP is **not** intended to be a complete autonomous platform.

---

# 4. Official MVP stack

```text
Frontend: React + Vite
Backend/Core: FastAPI
Database: SQLite
Initial model: Qwen 3B
API: REST
Streaming: SSE
Persistence: SQLite + filesystem/workspaces
```

No additional infrastructure is required.

Do not introduce:

```text
Redis
Kafka
Kubernetes
microservices
vector database
distributed workers
advanced RAG
multi-agent infrastructure
automatic model routing
plugin marketplace
```

---

# 5. Official MVP entities

The persistent entities are:

```text
Project
Conversation
Message
Memory
Task
Action
Artifact
Model
ToolCall
ToolResult
Setting
```

`Tool` is an executable application-level abstraction in the MVP. It is **not** a database table.

`ModelProvider` is an application-level abstraction. It is **not** a database table.

There is no `users` table in the single-user MVP.

There is no `permissions` table in the MVP. Permission is handled by the Action lifecycle and the application permission layer.

---

# 6. Database conventions

## 6.1 Primary keys

All persistent entities use:

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
```

No UUID infrastructure is required in the MVP.

---

## 6.2 Text

SQLite `TEXT` is used for:

- names;
- descriptions;
- identifiers;
- statuses;
- roles;
- timestamps;
- JSON documents serialized as text.

---

## 6.3 JSON

SQLite does not require a separate JSON type.

The following fields are stored as `TEXT` containing JSON:

```text
metadata
configuration
state
plan
result
payload
arguments
data
error
```

When the field represents a JSON object, the default is:

```json
{}
```

When it represents a JSON array, the default is:

```json
[]
```

Do not introduce a JSON database extension.

---

## 6.4 Timestamps

All timestamps use:

```text
TEXT
```

Format:

```text
ISO 8601 UTC
```

Example:

```text
2026-10-05T22:00:00Z
```

Timestamp fields defined as `created_at` or `updated_at` are always `NOT NULL`.

The application is responsible for generating timestamps.

---

## 6.5 Foreign keys

SQLite foreign keys must be enabled on every connection:

```sql
PRAGMA foreign_keys = ON;
```

---

# 7. Table: models

## Purpose

Stores the models available to Mosaic.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| name | TEXT | NO | — | Friendly UI name |
| provider | TEXT | NO | — | Provider identifier |
| model_name | TEXT | NO | — | Technical provider model identifier |
| configuration | TEXT | NO | `{}` | JSON object |
| enabled | INTEGER | NO | `1` | Boolean: 0/1 |

### Constraints

```sql
UNIQUE(provider, model_name)
CHECK(enabled IN (0, 1))
```

### Example

```json
{
  "name": "Qwen 3B",
  "provider": "ollama",
  "model_name": "qwen3:3b",
  "configuration": {},
  "enabled": true
}
```

### Important

Do NOT add:

```text
context_window
pricing
latency
hardware
quantization
ram_required
gpu_required
routing_priority
performance_score
capabilities
```

Those are not MVP Model fields.

---

# 8. Table: projects

## Purpose

Represents a first-class Mosaic project.

A project groups:

```text
conversations
memories
tasks
artifacts
workspace
state
```

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| name | TEXT | NO | — | Project name |
| description | TEXT | YES | NULL | Optional description |
| workspace | TEXT | NO | — | Workspace path |
| metadata | TEXT | NO | `{}` | JSON object |
| state | TEXT | NO | `{}` | JSON object |
| created_at | TEXT | NO | — | ISO 8601 UTC |
| updated_at | TEXT | NO | — | ISO 8601 UTC |

### Why description is nullable

A project can exist before the user provides a description.

### Why workspace is NOT NULL

Every Project has a workspace identity in the Mosaic model. The implementation may create the physical directory when the project is created.

---

# 9. Table: conversations

## Purpose

Stores user conversations and their relationship to a model/project.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| title | TEXT | NO | — | Conversation title |
| mode | TEXT | NO | `chat` | Initial allowed mode: `chat` |
| model_id | INTEGER | NO | — | FK → models.id |
| project_id | INTEGER | YES | NULL | FK → projects.id |
| created_at | TEXT | NO | — | ISO 8601 UTC |
| updated_at | TEXT | NO | — | ISO 8601 UTC |

### Foreign keys

```text
model_id
→ models.id
→ ON DELETE RESTRICT
```

```text
project_id
→ projects.id
→ ON DELETE SET NULL
```

### Important decisions

`project_id` is nullable because Mosaic must support a normal conversation that is not currently inside a project.

`model_id` is NOT NULL because every conversation must have an explicit model.

Do not create a conversation without a model.

### Mode

MVP:

```text
chat
```

Future modes such as:

```text
create
agent
```

belong to later Task/Agent functionality and must not be invented as additional Conversation modes unless the implementation contract is updated.

---

# 10. Table: messages

## Purpose

Stores the complete conversation history.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| conversation_id | INTEGER | NO | — | FK → conversations.id |
| role | TEXT | NO | — | user/assistant/system/tool |
| content | TEXT | NO | — | Message content |
| created_at | TEXT | NO | — | ISO 8601 UTC |
| metadata | TEXT | NO | `{}` | JSON object |

### Foreign key

```text
conversation_id
→ conversations.id
→ ON DELETE CASCADE
```

### Allowed roles

```text
user
assistant
system
tool
```

### Important

The existence of the `tool` role does NOT mean the Tool Layer must be implemented immediately.

It only defines the message contract.

---

# 11. Table: memories

## Purpose

Stores structured Mosaic memory.

Memory belongs to Mosaic, not to the model.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| project_id | INTEGER | YES | NULL | FK → projects.id |
| type | TEXT | NO | — | Allowed memory type |
| key | TEXT | NO | — | Memory key |
| value | TEXT | NO | — | Stored value |
| source | TEXT | NO | — | Origin of memory |
| confidence | REAL | YES | NULL | 0.0–1.0 when present |
| created_at | TEXT | NO | — | ISO 8601 UTC |
| updated_at | TEXT | NO | — | ISO 8601 UTC |

### Foreign key

```text
project_id
→ projects.id
→ ON DELETE SET NULL
```

### Allowed types

```text
user_fact
user_preference
user_claim
project_state
instruction
```

### Confidence

`confidence` is nullable.

Reason:

Not every memory needs a numeric confidence score.

When present:

```text
0.0 <= confidence <= 1.0
```

### Source

`source` is NOT NULL.

Examples:

```text
user
conversation
system
tool
```

The exact source vocabulary is application-level and may be expanded later without creating a new table.

### Important semantic rule

```text
MEMORY ≠ TRUTH
```

A `user_claim` is persisted as a user claim, not automatically promoted to objective fact.

---

# 12. Table: tasks

## Purpose

Task is the general unit of structured work.

Create and Agent are modes of the same Task Engine.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| conversation_id | INTEGER | YES | NULL | FK → conversations.id |
| project_id | INTEGER | YES | NULL | FK → projects.id |
| type | TEXT | NO | — | Task type |
| mode | TEXT | NO | — | create/agent |
| status | TEXT | NO | `pending` | Task lifecycle |
| plan | TEXT | YES | NULL | JSON object |
| result | TEXT | YES | NULL | JSON object/result |
| created_at | TEXT | NO | — | ISO 8601 UTC |
| updated_at | TEXT | NO | — | ISO 8601 UTC |

### Relationship rule

At least one of these must exist:

```text
conversation_id
project_id
```

So the database should enforce:

```sql
CHECK (
    conversation_id IS NOT NULL
    OR project_id IS NOT NULL
)
```

### Foreign keys

```text
conversation_id
→ conversations.id
→ ON DELETE SET NULL
```

```text
project_id
→ projects.id
→ ON DELETE SET NULL
```

### Task types

Initial:

```text
code_project
document
analysis
report
generic
```

### Task modes

```text
create
agent
```

### Task status

Initial:

```text
pending
planning
awaiting_approval
executing
validating
completed
failed
cancelled
```

The implementation should use these exact lifecycle concepts. Do not invent additional states without Master approval.

### Why plan/result are nullable

A Task can exist before planning is generated and before a result exists.

---

# 13. Table: actions

## Purpose

Represents an operation proposed/executed as part of a Task.

The model proposes intent. Mosaic controls execution.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| task_id | INTEGER | NO | — | FK → tasks.id |
| type | TEXT | NO | — | Action type |
| target | TEXT | YES | NULL | Target resource |
| payload | TEXT | NO | `{}` | JSON object |
| status | TEXT | NO | `pending` | Action lifecycle |
| result | TEXT | YES | NULL | JSON/result |
| created_at | TEXT | NO | — | ISO 8601 UTC |
| updated_at | TEXT | NO | — | ISO 8601 UTC |

### Foreign key

```text
task_id
→ tasks.id
→ ON DELETE CASCADE
```

### Action lifecycle

Primary MVP lifecycle:

```text
pending
→ approved
→ executing
→ completed
```

Failure/cancellation states:

```text
rejected
failed
cancelled
```

### Why target is nullable

Some actions operate on a resource target; others can represent a generic operation.

Do not force fake target strings.

### Why result is nullable

An action has no result before execution.

---

# 14. Table: artifacts

## Purpose

Represents files or other persistent outputs generated by a Task.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| task_id | INTEGER | NO | — | FK → tasks.id |
| type | TEXT | NO | — | Artifact type |
| path | TEXT | NO | — | Filesystem path |
| metadata | TEXT | NO | `{}` | JSON object |
| created_at | TEXT | NO | — | ISO 8601 UTC |

### Foreign key

```text
task_id
→ tasks.id
→ ON DELETE CASCADE
```

### Important

Artifact metadata is descriptive.

The actual artifact bytes live in the filesystem/workspace, not inside SQLite.

---

# 15. Table: tool_calls

## Purpose

Persists model requests to execute a Tool.

A Tool Call is an **intent**, not execution itself.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| conversation_id | INTEGER | NO | — | FK → conversations.id |
| task_id | INTEGER | YES | NULL | FK → tasks.id |
| tool_name | TEXT | NO | — | Registered Tool name |
| arguments | TEXT | NO | `{}` | JSON object |
| status | TEXT | NO | `pending` | Execution status |
| created_at | TEXT | NO | — | ISO 8601 UTC |
| updated_at | TEXT | NO | — | ISO 8601 UTC |

### Foreign keys

```text
conversation_id
→ conversations.id
→ ON DELETE CASCADE
```

```text
task_id
→ tasks.id
→ ON DELETE SET NULL
```

### Tool Call status

```text
pending
approved
executing
completed
failed
rejected
cancelled
```

### Important

`tool_name` is a string identifier.

There is no `tools` database table in the MVP.

---

# 16. Table: tool_results

## Purpose

Persists the result returned by a Tool execution.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| id | INTEGER | NO | AUTOINCREMENT | PK |
| tool_call_id | INTEGER | NO | — | FK → tool_calls.id |
| status | TEXT | NO | — | completed/failed |
| data | TEXT | YES | NULL | JSON/result |
| error | TEXT | YES | NULL | Error information |
| created_at | TEXT | NO | — | ISO 8601 UTC |

### Foreign key

```text
tool_call_id
→ tool_calls.id
→ ON DELETE CASCADE
```

### Result rule

Success:

```text
status = completed
data != NULL
error = NULL
```

Failure:

```text
status = failed
data = NULL
error != NULL
```

This is an application-level invariant.

---

# 17. Table: settings

## Purpose

Stores simple Mosaic application configuration without introducing a configuration service.

## Schema

| Field | SQLite type | Null | Default | Rules |
|---|---|---:|---|---|
| key | TEXT | NO | — | PK |
| value | TEXT | NO | — | Stored configuration value |

### Important

Do not add:

```text
id
created_at
updated_at
user_id
```

unless the architecture explicitly changes.

Settings are key/value configuration for the single-user MVP.

Example:

```text
key = default_model_id
value = 1
```

or:

```text
key = theme
value = dark
```

The application decides whether a setting contains plain text or serialized JSON.

---

# 18. Tables that do NOT exist in the MVP

Do not create these tables:

```text
users
providers
model_providers
tools
permissions
tool_permissions
agents
agent_runs
context_snapshots
embeddings
documents
chunks
vector_store
sessions
audit_log
jobs
workers
plugins
```

They may become relevant later, but they are not part of the current MVP contract.

---

# 19. Complete relationship map

```text
                         ┌─────────────┐
                         │   PROJECT   │
                         └──────┬──────┘
                                │
                 ┌──────────────┼───────────────┐
                 │              │               │
                 ▼              ▼               ▼
          CONVERSATIONS      MEMORIES         TASKS
                 │                              │
                 │                              │
                 ▼                              ▼
             MESSAGES                         ACTIONS
                 │                              │
                 │                              ▼
                 │                           ARTIFACTS
                 │
                 ├──────────────┐
                 │              │
                 ▼              ▼
            TOOL_CALLS     MODEL
                 │
                 ▼
            TOOL_RESULTS
```

More precisely:

```text
PROJECT
 ├──< CONVERSATION
 │      ├──< MESSAGE
 │      └──< TOOL_CALL
 │               └──< TOOL_RESULT
 │
 ├──< MEMORY
 │
 └──< TASK
        ├──< ACTION
        ├──< ARTIFACT
        └──── TOOL_CALL

MODEL
 └──< CONVERSATION
```

---

# 20. Recommended indexes

Only indexes with an immediate MVP use are required.

## conversations

```sql
CREATE INDEX idx_conversations_project_id
ON conversations(project_id);
```

## messages

```sql
CREATE INDEX idx_messages_conversation_id
ON messages(conversation_id);
```

## memories

```sql
CREATE INDEX idx_memories_project_id
ON memories(project_id);

CREATE INDEX idx_memories_type
ON memories(type);

CREATE INDEX idx_memories_key
ON memories(key);
```

## tasks

```sql
CREATE INDEX idx_tasks_conversation_id
ON tasks(conversation_id);

CREATE INDEX idx_tasks_project_id
ON tasks(project_id);

CREATE INDEX idx_tasks_status
ON tasks(status);
```

## actions

```sql
CREATE INDEX idx_actions_task_id
ON actions(task_id);

CREATE INDEX idx_actions_status
ON actions(status);
```

## tool_calls

```sql
CREATE INDEX idx_tool_calls_conversation_id
ON tool_calls(conversation_id);

CREATE INDEX idx_tool_calls_task_id
ON tool_calls(task_id);

CREATE INDEX idx_tool_calls_status
ON tool_calls(status);
```

## tool_results

```sql
CREATE INDEX idx_tool_results_tool_call_id
ON tool_results(tool_call_id);
```

Do not add speculative indexes.

---

# 21. Complete database DDL

The following is the reference shape for the MVP database.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    configuration TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1
        CHECK (enabled IN (0, 1)),
    UNIQUE (provider, model_name)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NULL,
    workspace TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    state TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'chat',
    model_id INTEGER NOT NULL,
    project_id INTEGER NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (model_id)
        REFERENCES models(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NULL,
    type TEXT NOT NULL
        CHECK (
            type IN (
                'user_fact',
                'user_preference',
                'user_claim',
                'project_state',
                'instruction'
            )
        ),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NULL
        CHECK (
            confidence IS NULL
            OR (confidence >= 0.0 AND confidence <= 1.0)
        ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NULL,
    project_id INTEGER NULL,
    type TEXT NOT NULL
        CHECK (
            type IN (
                'code_project',
                'document',
                'analysis',
                'report',
                'generic'
            )
        ),
    mode TEXT NOT NULL
        CHECK (mode IN ('create', 'agent')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'planning',
                'awaiting_approval',
                'executing',
                'validating',
                'completed',
                'failed',
                'cancelled'
            )
        ),
    plan TEXT NULL,
    result TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CHECK (
        conversation_id IS NOT NULL
        OR project_id IS NOT NULL
    ),

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE SET NULL,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    target TEXT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'approved',
                'executing',
                'completed',
                'rejected',
                'failed',
                'cancelled'
            )
        ),
    result TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    path TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    task_id INTEGER NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'approved',
                'executing',
                'completed',
                'failed',
                'rejected',
                'cancelled'
            )
        ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tool_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_call_id INTEGER NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('completed', 'failed')),
    data TEXT NULL,
    error TEXT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (tool_call_id)
        REFERENCES tool_calls(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

# 22. Nullability master rule

When Chat 01 is unsure whether a field should be nullable, use this rule:

### NOT NULL when:

The entity cannot be meaningfully created without the value.

Examples:

```text
Model.provider
Model.model_name
Conversation.model_id
Message.content
Task.type
Action.task_id
Artifact.path
ToolCall.tool_name
```

### NULL when:

The value legitimately does not exist yet or is genuinely optional.

Examples:

```text
Project.description
Conversation.project_id
Memory.project_id
Memory.confidence
Task.plan
Task.result
Action.target
Action.result
ToolCall.task_id
ToolResult.data
ToolResult.error
```

Do not use `NULL` as a generic escape hatch.

Do not use fake values such as:

```text
""
"unknown"
0
"none"
```

when the semantic value is genuinely absent.

---

# 23. Default-value master rule

Use defaults only when they represent a real domain default.

Approved examples:

```text
configuration → {}
metadata      → {}
state         → {}
payload       → {}
arguments     → {}
enabled       → 1
mode          → chat
status        → pending
```

Do not invent defaults for:

```text
name
provider
model_name
title
content
workspace
path
type
tool_name
created_at
updated_at
```

Those values must be explicitly supplied.

---

# 24. ModelProvider contract

ModelProvider is application code, not a table.

Conceptual interface:

```python
class ModelProvider:
    def generate(...):
        ...

    def stream(...):
        ...
```

The Core must not depend directly on Ollama/Qwen-specific implementation details.

Initial implementation:

```text
Model
provider = ollama
model_name = qwen3:3b

↓

Ollama ModelProvider

↓

generate()
stream()
```

---

# 25. Tool contract

Tool is application code, not a table.

Conceptual contract:

```text
Tool
├── name
├── description
├── input_schema
├── permission_policy
└── executor
```

The Tool Registry is initially in-memory/application-level.

No Tool database table is required.

---

# 26. Context contract

Context belongs to Mosaic.

The initial Context Manager assembles:

```text
SYSTEM / CORE INSTRUCTIONS
+
PROJECT STATE
+
RELEVANT MEMORY
+
RECENT HISTORY
+
RELEVANT HISTORY
+
RELEVANT FILES
+
CURRENT TASK
+
TOOL RESULTS
+
CURRENT USER MESSAGE
```

The MVP must prefer simple, debuggable retrieval.

Do not introduce:

```text
embeddings
vector DB
semantic search infrastructure
advanced RAG
```

just to implement Context.

---

# 27. Permission contract

The model does not execute actions.

Correct flow:

```text
MODEL
↓
proposes Action / Tool Call
↓
MOSAIC validates
↓
permission check
↓
APPROVAL when required
↓
EXECUTOR
↓
RESULT
↓
PERSISTENCE
↓
CONTEXT
↓
MODEL
```

Security principle:

```text
MODEL ≠ ACCESS
```

---

# 28. Task execution contracts

## Create mode

```text
INTENT
↓
PLAN
↓
PROPOSAL
↓
APPROVAL
↓
EXECUTION
↓
VALIDATION
↓
RESULT
```

## Agent mode

```text
INTENT
↓
PLAN
↓
ACTION
↓
EXECUTION
↓
OBSERVATION
↓
CONTEXT UPDATE
↓
MODEL
↓
NEW ACTION
↓
...
```

Agent mode must have an iteration limit.

The exact default can be defined during Agent implementation, but it must exist.

---

# 29. MVP API surface

The implementation can evolve endpoint details, but these capabilities are required.

## Health

```text
GET /health
```

## Models

```text
GET  /models
GET  /models/{id}
POST /models
```

Additional model mutation endpoints are not required unless needed by the UI.

## Conversations

```text
POST /conversations
GET  /conversations
GET  /conversations/{id}
PATCH /conversations/{id}
```

## Messages

```text
POST /conversations/{id}/messages
GET  /conversations/{id}/messages
```

## Streaming

SSE is required for model streaming when the provider supports it.

Exact endpoint may be:

```text
GET /conversations/{id}/stream
```

or an equivalent REST/SSE design chosen during implementation.

The API contract must remain simple.

## Projects

```text
POST   /projects
GET    /projects
GET    /projects/{id}
PATCH  /projects/{id}
DELETE /projects/{id}
```

## Memories

```text
GET    /memories
POST   /memories
PATCH  /memories/{id}
DELETE /memories/{id}
```

## Tasks

Task endpoints are required when Phase 4 begins.

## Actions

Action endpoints are required when Phase 5 begins.

## Tools

Tool execution endpoints are internal Core behavior where possible.

Do not expose unrestricted arbitrary execution through a public endpoint.

---

# 30. MVP implementation order

The implementation must follow this order.

## Phase A — Foundation

Already implemented:

```text
FastAPI
React/Vite
SQLite
configuration
health
basic API structure
```

Do not rebuild it.

---

## Phase B — Model

```text
Model entity
↓
database schema
↓
repository
↓
tests
↓
commit
```

Verify:

- creation;
- retrieval;
- persistence;
- configuration;
- enabled;
- uniqueness of provider + model_name.

---

## Phase C — Conversation

```text
Conversation
↓
repository
↓
API
↓
tests
↓
commit
```

---

## Phase D — Message

```text
Message
↓
repository
↓
API
↓
tests
↓
commit
```

---

## Phase E — Provider + Chat

```text
ModelProvider
↓
Qwen/Ollama provider
↓
generate
↓
stream
↓
chat flow
↓
persist messages
```

---

## Phase F — Context

```text
Context Manager
↓
recent history
↓
project context
↓
memory
```

Use deterministic/simple retrieval first.

---

## Phase G — Memory

```text
Memory entity
↓
repository
↓
Memory Manager
↓
context integration
```

---

## Phase H — Project

```text
Project
↓
workspace
↓
project conversations
↓
project memory
↓
project state
```

---

## Phase I — Task

```text
Task
↓
Create mode
↓
plan
↓
proposal
↓
artifact
```

---

## Phase J — Action + Permission

```text
Action
↓
approval
↓
execution
↓
result
```

---

## Phase K — Tools

```text
Tool abstraction
↓
Tool Registry
↓
ToolCall
↓
Tool validation
↓
permission
↓
execution
↓
ToolResult
↓
context
```

Initial tools:

```text
Filesystem
Terminal
Search
Calculator
Weather
```

---

## Phase L — Agent

```text
Task(mode=agent)
↓
loop
↓
action
↓
tool
↓
observation
↓
context
↓
model
```

Add:

```text
iteration limit
cancellation
basic error recovery
```

---

# 31. What Chat 01 must NOT do

Do not implement ahead of the current phase:

```text
Model Manager
automatic routing
vector DB
RAG
semantic memory
multi-agent
plugin marketplace
browser automation
distributed execution
microservices
Redis
Kafka
Kubernetes
complex sandbox
multi-user authentication
```

Do not create speculative database fields.

Do not create tables because they may be useful later.

Do not refactor unrelated modules.

Do not change architecture silently.

Do not add abstractions without an immediate MVP use.

---

# 32. Required implementation behavior

For every task:

```text
1. Read this contract.
2. Inspect the current GitHub repository.
3. Identify exactly what is missing.
4. Implement only that increment.
5. Add focused tests.
6. Run tests.
7. Review diff.
8. Commit with a coherent message.
9. Report what changed.
10. Stop before the next architectural increment unless explicitly instructed.
```

---

# 33. Validation checklist for Master

After Chat 01 reports completion, Master validates:

### Database

- [ ] correct tables
- [ ] correct fields
- [ ] correct SQLite types
- [ ] correct NULL/NOT NULL
- [ ] correct defaults
- [ ] correct FKs
- [ ] correct constraints
- [ ] no speculative fields
- [ ] no speculative tables

### Domain

- [ ] Model contract respected
- [ ] Conversation contract respected
- [ ] Message contract respected
- [ ] Memory semantics respected
- [ ] Task lifecycle respected
- [ ] Action lifecycle respected
- [ ] Tool Call ≠ Tool execution
- [ ] Model ≠ access

### Engineering

- [ ] tests exist
- [ ] tests pass
- [ ] diff is coherent
- [ ] no unrelated refactor
- [ ] commit is focused
- [ ] architecture was not silently changed

---

# 34. Final MVP definition

The Mosaic MVP is complete when the following end-to-end flow works:

```text
USER
 ↓
React UI
 ↓
FastAPI
 ↓
Conversation
 ↓
Message
 ↓
Context Manager
 ↓
Memory / Project State / History
 ↓
ModelProvider
 ↓
Qwen 3B
 ↓
Response
 ↓
Message persistence
 ↓
UI

---

# 21. Addendum de reconciliação do repositório — 2026-10-18

Este adendo registra decisões posteriores do MASTER sem apagar o contrato original acima.

## 21.1 Papel normativo

Este arquivo é a versão canônica versionada do contrato MVP. O texto original foi preservado. As decisões deste adendo complementam o contrato quando houver conflito explícito; não autorizam mudanças adicionais por inferência.

## 21.2 Tabelas internas encontradas no repositório

O repositório atual também contém `task_events` e `_mosaic_meta`. Elas são tabelas internas de infraestrutura, não novas entidades de domínio do MVP:

- `task_events`: persistência de eventos do ciclo de vida de Tasks e suporte à observabilidade/retomada.
- `_mosaic_meta`: metadados internos de inicialização/migração.

Devem ser mantidas enquanto forem utilizadas. Sua existência não autoriza a criação de outras tabelas fora do contrato.

## 21.3 Reconciliação de Artifact e Setting

As entidades `Artifact` e `Setting` continuam fazendo parte do contrato MVP. A ausência de tabelas correspondentes no bootstrap inspecionado é uma divergência a corrigir por migração incremental e não destrutiva, seguindo o plano de implementação aprovado.

Antes de migrar:
1. inspecionar o schema e os repositórios atuais;
2. mapear cada campo e relação do contrato;
3. definir migração idempotente compatível com banco novo e existente;
4. preservar todos os dados;
5. testar upgrade repetido e integridade das relações.

Não recriar o banco nem remover dados para fazer o schema coincidir.

## 21.4 Agente geral e evolução futura

O objetivo do produto evolui para um agente de propósito geral capaz de pesquisar na internet com fontes rastreáveis, criar/validar artefatos, construir projetos de software com especialidades coordenadas e retomar tarefas longas. Isso não amplia automaticamente o schema MVP nem autoriza tabelas como `agents`, `agent_runs`, `permissions`, `sessions`, `jobs`, `workers` ou infraestrutura distribuída.

As especialidades devem inicialmente reutilizar o mesmo Task Engine, Harness, políticas, ferramentas e persistência, com coordenação sequencial. Mudanças de schema exigem contrato/adendo aprovado pelo MASTER.

## 21.5 Regra de validação

A presença de módulos ou testes no repositório não equivale a capacidade validada. Cada família de tarefa deve ser demonstrada por fluxo integrado, testes executados e validação do resultado real. O README deve distinguir explicitamente: planejado, presente no código, testado e validado ponta a ponta.
