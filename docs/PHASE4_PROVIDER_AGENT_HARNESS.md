# Mosaic — Phase 4 Provider-backed Agent Harness

**Branch:** `codex/phase4-provider-agent-harness`  
**Scope:** connect the existing Agent loop to the conversation's configured ModelProvider.

## Flow

```text
POST /tasks/{task_id}/run
        ↓
Task / Conversation / Model lookup
        ↓
Provider.generate(context + Agent JSON protocol)
        ↓
Parse one decision (final OR tool_call)
        ↓
Existing run_agent loop
        ↓
Tool validation / permission / approval / execution / observation
        ↺
Provider.generate(updated context)
```

## API

- `POST /tasks/{task_id}/run` starts or resumes an Agent Task using its conversation's model.
- The response is the Agent run result, including `status`, `iterations`, and either `output`, `tool_call_id`, or `error` as applicable.
- Unknown task/conversation/model references return 404; invalid task state/configuration returns 409. Provider/decision exceptions are handled by the existing Agent loop and persisted as a failed Task result.

## Decision protocol

The provider must return one JSON object:

```json
{"type":"final","content":"user-facing answer"}
```

or

```json
{"type":"tool_call","tool":"calculator","arguments":{"expression":"2+2"}}
```

Malformed JSON, unknown decision types, and malformed arguments fail closed as a decision error. The harness does not execute tools directly; it delegates decisions to the existing Agent loop, which owns validation, permissions, approval, execution and persistence.

## Boundaries

- Uses the conversation's existing model/provider and configuration.
- Does not add tables, fields, queues, workers, or provider abstractions.
- Does not change normal chat behavior.
- Approval endpoints remain a separate human decision; after approve/reject, the caller can POST `/tasks/{task_id}/run` again to continue.
- This increment does not add frontend controls or background execution.

## Validation

Run from `backend/`:

```bash
python -m pytest tests/test_harness.py tests/test_task.py tests/test_agent.py tests/test_tools.py tests/test_action.py -q
```

Tests were added but have not been executed by this implementation session. Verify locally before merging.
