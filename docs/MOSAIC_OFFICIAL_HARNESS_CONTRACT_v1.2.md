# MOSAIC — OFFICIAL HARNESS IMPLEMENTATION CONTRACT

**Version:** 1.2  
**Status:** Official architecture decision — supersedes v1.1 for Harness scope and roadmap; selectively amends MVP Contract v1.0 where explicitly stated below.  
**Date:** 2026-10-12  
**Authority:** MASTER / Architecture  
**Repository:** https://github.com/IGOR-SciDATA/mosaic  
**Implementation target:** existing `main` branch; incremental commits by Chat 01.

---

## 1. Why this contract exists

The earlier MVP contract v1.0 correctly constrained the initial Core to avoid premature infrastructure. The Harness proposal prepared on 2026-10-12 expands the product goal: Mosaic must evolve from a persistent chat/Core into a complete, user-controlled execution environment that can plan work, select capabilities, use tools, observe results, recover context, work with project files, and expose what it is doing.

The prior v1.1 contract was too narrow in framing the task primarily as safety fixes followed by a minimal loop. This v1.2 defines the **complete Harness target architecture**, while retaining an incremental implementation order. “Complete” describes the capability and integration contract, not a requirement to ship every feature in one commit.

The architecture may add modules, dependencies, and persistent structures when they serve a demonstrated Harness requirement. Existing code is the starting point, not a boundary. Conversely, additions must have an explicit role, tests, lifecycle, and acceptance criteria; do not add infrastructure for hypothetical future needs.

## 2. Product definition

Mosaic is a local-first orchestration Core and execution environment. The model reasons and proposes; Mosaic owns state, access, execution, memory, context, policy, and the operational record.

Mosaic should answer three questions throughout a task:

- What do I know?
- What do I need to discover?
- What am I allowed to do?

Non-negotiable principles:

```text
MODEL ≠ ACCESS
MEMORY ≠ TRUTH
HISTORY ≠ MODEL MEMORY
CONTEXT ≠ FULL HISTORY
TOOL CALL ≠ TOOL EXECUTION
SKILL ≠ PERMISSION
HARNESS ≠ SECOND CORE
TASK = GENERAL UNIT OF WORK
CREATE + AGENT = MODES OF ONE TASK ENGINE
MOSAIC OWNS STATE
DOCUMENTATION = ARCHITECTURAL TRUTH
GITHUB = IMPLEMENTATION TRUTH
```

## 3. Scope of this amendment to the MVP v1.0

### Preserved
- React + Vite frontend, FastAPI Core, SQLite, filesystem workspaces, REST and SSE.
- Existing Project, Conversation, Message, Memory, Task, Action, Artifact, Model, ToolCall, ToolResult and Setting domain contracts unless explicitly amended by a future decision.
- `Tool` and `ModelProvider` remain application abstractions, not required database tables.
- No multi-user/authentication system is required for this single-user MVP.
- Existing Context Manager, Memory Manager, Task Engine, Action/permission code, Tool Registry, ToolCall/ToolResult repositories and Ollama provider should be reused where appropriate.
- No microservices, distributed queues, Redis, Kafka or Kubernetes for this local-first milestone.

### Explicitly amended
The old blanket exclusions of RAG, document/chunk storage, execution logs, skills and richer Harness orchestration no longer prohibit implementation where needed for the target described here. These capabilities must be introduced incrementally and with documented schemas/behavior. This is not blanket permission to build every possible subsystem.

### Not in scope yet
- Multi-agent delegation / agent swarms.
- Remote multi-tenant SaaS, users, teams and authentication.
- Distributed execution, message brokers or cluster scheduling.
- Plugin marketplace or arbitrary third-party code installation.
- Unrestricted shell, unrestricted filesystem, uncontrolled browser automation.
- Mandatory cloud APIs or mandatory remote model use.

## 4. Target architecture

The Harness is an internal orchestration subsystem inside the existing Mosaic Core. It is not a second Core or a parallel Task Engine.

```text
REACT UI
  ├── Chat + streaming
  ├── Projects + files + artifacts
  ├── Task / execution timeline
  ├── Tool approval inbox
  ├── Skills manager
  ├── Harness/autonomy settings
  └── Logs + retrieval/source inspector
             │ REST / SSE
             ▼
FASTAPI — MOSAIC CORE
  ├── Conversation / Project / Artifact services
  ├── Task Engine (single source of task lifecycle)
  ├── Harness Orchestrator
  │    ├── Request & goal interpreter
  │    ├── Task planning / plan update
  │    ├── Profile & policy resolver
  │    ├── Context assembler / budget manager
  │    ├── Skill selector and skill loader
  │    ├── Model decision adapter / parser
  │    ├── Tool-call validator
  │    ├── Approval and execution coordinator
  │    ├── Observation / result processor
  │    ├── Validation / completion evaluator
  │    └── Stop, retry, cancellation and budget control
  ├── Context Manager
  ├── Memory Manager
  ├── Knowledge / Document Retrieval
  ├── Policy / Action service
  ├── Tool Registry + constrained executors
  ├── ModelProvider abstraction (Ollama first)
  ├── Event / Logging service
  └── Persistence repositories
             │
             ▼
SQLite + project workspaces + original files + artifacts + local logs
             │
             ├── Ollama / Qwen / other configured local models
             ├── filesystem / terminal / calculator
             ├── web search / safe fetch
             ├── document parsers / test runner / Git
             └── future explicitly approved capabilities
```

Not every box must be a separate Python package on day one. Boundaries are logical responsibilities. Prefer a modular monolith and stable interfaces before introducing process boundaries.

## 5. The complete Harness execution contract

A normal task must be able to follow this lifecycle:

1. Receive the user goal and resolve the active conversation, project, model and autonomy profile.
2. Create or attach a `Task` when the request requires structured work or tool execution.
3. Build a bounded context: Core policy, goal, project state, relevant memory, recent/relevant conversation, active plan, selected skills, retrieved source passages, prior observations and current request.
4. Ask the selected ModelProvider for a decision using a documented structured protocol.
5. Parse and validate the decision. Valid decision kinds include `final`, `plan/update_plan` and `tool_call`; unsupported or malformed output must fail safely or receive a bounded repair attempt.
6. Persist the plan update or proposed `ToolCall` before any side effect.
7. Resolve tool policy, risk, scope, budget and approval requirement on the backend.
8. If approval is required, persist the pending approval and pause. The UI can approve/reject; it cannot grant authority itself.
9. Execute only after policy permits it, within a bounded and project-aware executor.
10. Persist `ToolResult`, execution metadata and an operational event. Convert results into observations with bounded output and source/reference metadata.
11. Rebuild the next context from the current task state and relevant observations; do not blindly append all historical tool output forever.
12. Continue until a final answer, approval wait, explicit cancellation, unrecoverable error or a configured limit.
13. When a task produces files, record them as `Artifact` metadata and keep bytes in the workspace.
14. Validate completion where appropriate: tests/build checks for code tasks, existence/readability checks for generated files, source checks for research/document tasks.
15. Persist the final answer, task result, status, and event trail. Make the result available through API and UI after restart.

Required stop controls:
- maximum model/tool iterations;
- wall-clock task deadline;
- per-tool timeout;
- bounded context and tool-result size;
- cancellation checked before and after model/tool calls;
- bounded retries with no infinite retry loops;
- explicit handling of provider offline, malformed output, tool failure and approval rejection.

A Task must not be marked completed merely because the model emitted a plausible sentence. Completion must correspond to the requested output and validation policy.

## 6. Task and state ownership

- `Task` remains the general unit of work. `create` and `agent` remain modes; do not introduce a parallel AgentRun or Job system without a future architecture decision.
- Task status remains within the v1.0 contract: `pending`, `planning`, `awaiting_approval`, `executing`, `validating`, `completed`, `failed`, `cancelled`.
- Enforce allowed transitions centrally. API clients must not arbitrarily jump between valid status strings.
- `Action` remains the auditable action/approval lifecycle where appropriate. `ToolCall` is the model/tool intent and its own invocation lifecycle. Do not create a third permission lifecycle.
- Define one policy/approval coordinator so Action and ToolCall cannot disagree about whether a side effect is authorized.
- A paused approval resumes the same persisted Task and ToolCall. It must not repeat an already completed side effect.
- Store durable task plans, results, status, tool invocations and artifacts. Transient model context is rebuilt from these records.

## 7. Model adapter and decision protocol

The Harness must work through the existing `ModelProvider` abstraction, not depend directly on Ollama internals.

- Ollama/Qwen is the first concrete provider; preserve local-first behavior.
- Model selection comes from Mosaic's configured Model/Conversation. Automatic model routing is not required for this milestone.
- Define a provider-neutral structured decision schema for final responses, plan updates and tool calls.
- Validate model-emitted tool name and arguments against the registered tool schema and policy.
- Never execute text that merely resembles a tool call. Never allow model output to mutate Core policy or permissions.
- Keep hidden model reasoning private. Observability records operational decisions and concise rationales, not hidden chain-of-thought.
- Include fake-provider tests for deterministic orchestration, plus opt-in local Ollama smoke tests.

## 8. Tool capability and execution system

Initial built-ins from the existing MVP remain useful: filesystem, terminal, search, calculator and weather. Harness completion may require document reading, safe web fetch, test runner and Git integration, added only when each has a clear tool contract and tests.

Every Tool must declare:
- stable name and description;
- input schema and validation behavior;
- risk/side-effect classification;
- approval policy metadata;
- execution timeout and output limit;
- required scope (for example active workspace or public web);
- normalized result/error shape.

Server-side invariants:
- unknown tools and invalid arguments fail closed;
- schema validation rejects unknown fields unless explicitly allowed;
- filesystem paths resolve inside the active project workspace; traversal and symlink escape are rejected;
- terminal runs in a scoped workspace with explicit process lifecycle, timeout, bounded stdout/stderr and cancellation cleanup;
- high-risk/destructive/external side effects require approval;
- web requests use timeout, response-size cap, redirect validation and protection against private/loopback/link-local destinations unless a narrowly defined trusted local target is configured;
- tool output is untrusted data, not instructions;
- errors are persisted as failed ToolResults without silently being converted to success;
- logs redact secrets and avoid storing full file contents by default.

Approval profiles:
- **Assistido (default):** execution requires explicit approval except explicitly harmless local read-only operations.
- **Controlado:** pre-approved low-risk tools may run within defined scope and budgets; side effects require approval.
- **Autonomia limitada:** user-preauthorized tools may run inside strict workspace and resource limits; destructive, external, privileged or out-of-scope actions still require approval.

Profile resolution and permission enforcement belong to the backend. Skill text and UI settings never grant permissions.

## 9. Skills and reusable procedures

Skills are reusable, versioned procedural instructions selected for a task. They are not executable authority and are not a second agent.

A Skill should have:
- stable identifier/name and description;
- version;
- instructions;
- applicable task/trigger description;
- declared tool needs;
- optional user enable/disable state;
- source and integrity metadata.

Initial skills may be stored as files in a documented Mosaic-managed directory and loaded by an application-level registry. A database table is not mandatory unless it materially improves lifecycle/query needs. Skills are untrusted procedural content: they cannot override Core policy, escape workspace boundaries, or grant tools. The Harness should expose which skills were selected in the task trace.

Implement a minimal skill loader/selector before a large marketplace or community distribution system.

## 10. Context, memory and project continuity

Context must be assembled deliberately and remain bounded. Include, as relevant:
- canonical Core identity and policy;
- current goal and Task plan/status;
- project state;
- selected relevant memories;
- recent conversation and relevant older history;
- relevant files and retrieved passages with provenance;
- selected skill instructions;
- recent ToolResults/observations and validation results;
- current user request.

Memory categories:
- **Semantic:** stable facts, preferences and accepted project decisions.
- **Episodic:** what happened in conversations/tasks, actions, tool results, failures and outcomes; much of this can be derived from existing durable records.
- **Procedural:** Skills and reusable workflows.

Do not duplicate all messages into a second memory database. Preserve source and confidence semantics; `MEMORY ≠ TRUTH`. Allow corrections/deletions. Keep global user memories separate from project-scoped state and project-specific history. Retrieval must respect conversation and project boundaries.

Add context budget accounting and relevance selection before introducing expensive semantic infrastructure. Expose the context sources selected to the observability view without revealing secrets or dumping private content unnecessarily.

## 11. Knowledge and RAG decision

**RAG is a supported architectural capability, not a mandatory first dependency.** It is justified when Mosaic must answer from many, large, or frequently changing project files and cannot reliably fit/read them directly.

Build in measurable stages:

- **K0 — Explicit file context:** safely read user-selected small files in the active workspace; preserve original bytes.
- **K1 — Knowledge registry and lexical retrieval:** file metadata, extraction status, content type, updated/hash metadata, safe text extraction and lexical search. SQLite FTS5 may be used if available; provide a deterministic fallback.
- **K2 — Chunking and provenance:** bounded passages with document ID/path and line/page/section references. Original files remain canonical; extracted text/chunks are rebuildable derived data.
- **K3 — Retrieval evaluation:** fixed question set with expected source documents/passages; measure whether relevant evidence is retrieved and whether answers are grounded.
- **K4 — Local embeddings/vector index:** implement only if K3 demonstrates lexical retrieval gaps that matter. Index must be rebuildable and local by default.
- **K5 — Hybrid retrieval/reranking:** only if measured results justify added latency/complexity.

Retrieved text is untrusted data. Prompt injection inside files or web pages cannot change policy or permissions. Answers based on documents should cite file and page/section where possible. Log which sources were retrieved and used, with safe metadata.

The v1.0 blanket prohibition of RAG is amended by this staged plan; it does not authorize skipping evaluation or starting with a vector database.

## 12. Observability and execution console

Observability is a first-class Harness capability, not a later cosmetic dashboard. A task should be understandable after it finishes and diagnosable while running.

Use structured events with at least:
- timestamp (UTC ISO-8601);
- level;
- component;
- event name;
- concise operational message;
- task_id, conversation_id, project_id, tool_call_id and action_id when applicable;
- duration_ms and status when applicable;
- bounded, redacted metadata.

Minimum event types:
- task created, planned, status changed, cancelled, completed, failed;
- model request started/completed/failed;
- context assembled (source types and token/size estimates, not secret content);
- skill selected;
- decision parsed/invalid;
- tool proposed, validated, approval-required, approved, rejected;
- tool execution started/completed/failed/timed out;
- retrieval query/results and source identifiers;
- artifact created/validated;
- retry and stop reason.

Minimum UI:
- live/current task timeline;
- filtered operational logs;
- model/provider status and latency;
- ToolCalls and ToolResults with status, duration, approval state, redacted arguments and errors;
- approval inbox;
- selected skills;
- retrieved documents/passages/source references;
- final output and generated artifacts;
- stop reason and resource/iteration usage.

Persistence decision:
- operational logs may use rotating local JSONL files;
- task-linked events needed for reliable timeline/restart reconstruction should use a bounded persistent local event store or be deterministically reconstructible from domain records;
- do not add a generic `audit_log` table just because the old MVP excluded it; specify event schema, retention, redaction and query needs before choosing a SQLite table versus JSONL.
- No external logging SaaS or message broker is required.

Never log credentials, tokens, environment secrets, or full private file contents by default. Do not expose hidden model chain-of-thought.

## 13. Document and artifact lifecycle

- User-provided files remain unchanged unless an explicit action requests modification.
- Generated outputs are written within the active project workspace.
- Record generated output in the existing Artifact entity contract: task_id, type, path, metadata, created_at.
- Provide explicit distinction between source file, derived extraction/index, intermediate output and final artifact.
- Validate that a reported artifact exists and is readable.
- Prevent paths from escaping the project workspace.
- A document parser must enforce file-size and extraction limits and treat embedded instructions as untrusted content.

## 14. Persistence and schema policy

The existing v1.0 schema contracts remain the baseline for current entities. New persistent data is allowed only when required by this contract and documented before implementation.

Potential new durable structures, only if justified by the implemented feature:
- knowledge documents/chunks/index metadata for K1/K2;
- skill metadata if filesystem registry is insufficient;
- structured task events if not reconstructible and JSONL is insufficient;
- explicit execution metadata if current Task/ToolCall/Action fields cannot safely represent it.

For every proposed table/field, document purpose, ownership, key, relationships, constraints, retention/deletion and migration strategy before coding. Use additive migrations/backward-compatible initialization; never silently reset user data. Do not create `agent_runs`, `jobs`, `permissions`, `tools`, `providers` or other parallel domain tables without a separate decision.

Before adding tables, reconcile the existing discrepancy between v1.0 and current database initialization: v1.0 specifies `artifacts` and `settings`; current `database.py` has not created these tables in the reviewed branch and instead creates `_mosaic_meta`. Preserve user data and make an explicit migration decision.

## 15. API and UI contract

Use the existing FastAPI and React/Vite application. Add APIs for task execution, task timeline/events, approvals, skills and knowledge only as their services are implemented.

- REST for durable resources and user actions.
- SSE for live task/event updates, with reconnection or refresh behavior.
- Every API validates IDs and ownership relationships; a Task must not attach a ToolCall from another conversation/project.
- Frontend state is a view of Core state, never the authority for permissions.
- UI must distinguish generating, executing, awaiting approval, validating, completed, failed and cancelled.
- Preserve a usable chat-only path when no tools are needed or agent execution is disabled.

## 16. Test strategy and quality gates

Test layers:
1. Unit tests for schema validation, policy resolution, transitions, context budgets, skill parsing, retrieval and redaction.
2. Service tests with fake ModelProvider and fake tools for deterministic control of decisions.
3. API tests for task start/status/cancel/approval/resume, events and project scoping.
4. End-to-end orchestration test: request → Task → model decision → persisted ToolCall → policy/approval → tool execution → ToolResult observation → second model turn → validation → final persisted result.
5. Safety tests: traversal, symlink escape, shell timeout, output cap, denied tool, private network destination, prompt injection, malformed model output and duplicate-resume prevention.
6. Restart/persistence tests for task state, approvals, events and artifacts.
7. Knowledge evaluation with known questions and expected source references.
8. Frontend production build and UI/API integration checks.
9. Optional real Ollama smoke tests separate from deterministic CI.

No phase is accepted on module presence alone. Record exact commands/results and known limitations.

## 17. Implementation roadmap

Work incrementally, but target the complete architecture. A phase may add new modules or schema when its acceptance tests require them.

### Phase 0 — Baseline, inspect and reconcile
- Run backend tests and frontend production build in a clean environment.
- Inspect the full current repository and document real pass/fail results.
- Reconcile Artifact/Setting schema discrepancy and migration strategy.
- Establish baseline end-to-end test harness with fake provider.

### Phase 1 — Execution substrate and safety
- Centralize task transitions and policy/approval decisions.
- Complete tool schema validation.
- Confine filesystem and terminal execution to project workspace and resource limits.
- Harden network tool requests.
- Add cancellation and duplicate-execution protections.

### Phase 2 — Provider-backed Harness core
- Define provider-neutral structured decisions.
- Connect real ModelProvider to the existing agent loop.
- Support planning, tool calling, observations, finalization, failure, retry and stop conditions.
- Persist and resume approvals for the same task/call.
- Add artifact validation.

### Phase 3 — Event model and observability backend
- Define event contract, correlation IDs, redaction, retention and storage choice.
- Emit events from all Harness lifecycle transitions.
- Ensure task traces remain useful after restart.

### Phase 4 — Knowledge K0/K1 and retrieval evaluation
- Add safe file access, document metadata/extraction and lexical retrieval.
- Record provenance and expose retrieved source IDs.
- Build fixed retrieval tests before considering embeddings.

### Phase 5 — Skills and context budgets
- Implement a minimal versioned skill format and registry/loader.
- Add skill selection trace, enable/disable and policy boundaries.
- Add context budgeting and relevant observation selection.

### Phase 6 — UI for Harness and observability
- Add task execution controls, live timeline, logs, tool details, approval inbox, skills and source inspector.
- Preserve current chat and project UI.

### Phase 7 — Measured retrieval upgrade (conditional)
- Evaluate K1 results on fixed questions.
- Add local embeddings/vector index only if results show meaningful lexical gaps.
- Benchmark quality, latency, memory footprint and rebuild behavior.

### Phase 8 — Full acceptance and runbook
- Run complete end-to-end and safety suite.
- Document local setup, tool boundaries, profiles, data locations, recovery and known limitations.
- Confirm architecture docs match code.

## 18. Definition of done — Harness milestone

The Harness milestone is accepted when a real configured model can take a user request, create/use a Task, make a validated decision, propose a ToolCall, pass backend policy and approval, execute a scoped tool, persist and observe its result, continue the same task, validate the requested output, and return a final result visible in the UI.

Additionally:
- approval pause/resume is durable and does not duplicate side effects;
- cancellation, timeout, provider failure, malformed decisions and iteration/resource limits are explicit;
- filesystem and terminal boundaries are enforced and tested;
- task timeline and operational logs are correlated and inspectable;
- memory and project/conversation isolation tests pass;
- document retrieval provides source provenance and a measured baseline;
- skills are reusable but cannot grant permissions;
- frontend build and backend suite pass in a recorded clean environment;
- all new persistent structures have documented migrations and lifecycle;
- code, tests and architecture contract agree.

## 19. Required workflow for Chat 01

For every increment:
1. Read this contract and the relevant v1.0 entity/schema sections.
2. Inspect the current branch and working tree.
3. State the architectural gap, existing modules to reuse, new modules/schema (if any), and files expected to change.
4. Implement the smallest coherent increment that moves toward the complete Harness.
5. Add regression, failure and safety tests.
6. Run focused tests, then relevant full backend tests and frontend build.
7. Review the diff for unrelated changes, data loss, secrets, scope escape and contract drift.
8. Commit one coherent increment.
9. Report changed files, exact commands/results, commit SHA and limitations.
10. Stop for Master review before starting the next phase.

If implementation evidence requires a new capability not specified here, propose it with the smallest design and tests; do not silently omit it merely because it was absent from the old MVP. If a change conflicts with a current entity schema, stop and propose an explicit contract amendment/migration.

---

**Master decision:** Build the complete Harness as a modular subsystem of Mosaic Core, extending existing components where they fit and adding new components where justified by the execution, knowledge and observability contracts above. Prioritize end-to-end behavior, safety and inspectability over isolated feature count.
