# Mosaic — Phase 6: transparent tool approval

**Branch:** `codex/phase6-tool-approval-details`  
**Scope:** show the exact pending tool name and arguments before the user approves or rejects execution.

## Changes

- Add a read-only endpoint for the exact ToolCall currently awaiting approval on a Task.
- Reuse the existing pending-approval checks: task status, ToolCall identity, ownership, and pending status.
- Return details only when the existing tool policy says human approval is required.
- Show the tool name and JSON arguments in the Tarefas UI.
- Disable approval/rejection controls when the details cannot be loaded, so the user cannot approve an opaque request from this UI.
- Add a focused backend regression test. No schema changes or new dependencies.

## Validation

Run from `backend/`:

```bash
python -m pytest tests/test_task.py tests/test_agent.py tests/test_harness.py tests/test_tools.py tests/test_action.py -q
```

Run from `frontend/`:

```bash
npm run build
```

Tests and build have not been executed in this implementation session.
