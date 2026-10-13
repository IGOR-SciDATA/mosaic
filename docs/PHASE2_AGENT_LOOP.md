# Mosaic — Phase 2 Agent Loop Hardening

**Branch:** `codex/phase2-agent-loop`  
**Scope:** lifecycle safety and cancellation/error handling in the existing synchronous agent loop.

## Contract alignment

This increment stays within Phase L of the MVP contract: bounded agent loop, cancellation, and basic error recovery. It does not introduce a new worker system, queue, scheduler, agent framework, or database entity.

## Changes

- A task already marked `cancelled`, `completed`, or `failed` is not restarted by `run_agent`.
- A task paused at `awaiting_approval` stays paused if the runner is invoked again; it does not ask the model for a new decision or create another ToolCall.
- Cancellation observed while the decision callback is running is preserved even if that callback raises.
- Cancellation is checked again before persisting a proposed ToolCall and before completing the task.
- Tool execution exceptions remain observations for the next iteration where safe; they do not automatically revive or overwrite a cancelled task.
- Added regression tests for these lifecycle boundaries.

## Explicit limitation

This does **not** implement approval/resume orchestration. A paused task remains paused; a later increment must provide a controlled approval endpoint/service path that resumes the same task and ToolCall, appends the tool result to context, and continues the bounded loop without duplicate execution.

## Validation

New tests are included in `backend/tests/test_agent.py`. Runtime execution is pending in the developer environment; run:

```bash
cd backend
python -m pytest tests/test_agent.py tests/test_tools.py tests/test_task.py tests/test_action.py -q
```
