# Mosaic — Phase 3 Tool Approval and Resume

**Branch:** `codex/phase3-tool-approval-resume`  
**Scope:** minimal API path for approving or rejecting the exact ToolCall that paused an Agent Task.

## API

- `POST /tasks/{task_id}/tool-calls/{tool_call_id}/approve`
- `POST /tasks/{task_id}/tool-calls/{tool_call_id}/reject`

Both endpoints require the Task to be `awaiting_approval`, require the ToolCall ID to match the pending approval recorded on the Task, verify task/conversation ownership, and revalidate the tool schema/policy.

Approval:
1. validates that the selected tool requires approval;
2. transitions the existing ToolCall from `pending` to `approved`;
3. executes that same ToolCall through the Core service;
4. persists its ToolResult;
5. returns the Task to `executing` so the Agent runner can be invoked again.

Rejection:
1. validates the same ownership and approval constraints;
2. transitions the ToolCall to `rejected` without invoking its executor;
3. persists a failed ToolResult explaining the rejection;
4. returns the Task to `executing` so the next agent decision can account for the rejection.

The Context Manager already includes persisted ToolResults, so the resumed Agent can reconstruct its context without an additional table or schema change.

## Safety and limits

- Replays are rejected because the Task is no longer awaiting approval and the ToolCall is no longer pending.
- A different ToolCall ID cannot be used to approve a task's pending request.
- Tools without `approval_required=true` cannot be approved/rejected through these human-decision endpoints.
- This endpoint does not call a model provider itself. After the API returns the Task to `executing`, the application runner must invoke `run_agent(task_id, decide)` again. A provider-backed HTTP worker/scheduler is not introduced in this increment.
- No database tables or fields were added.

## Validation

Focused regression tests were added to `backend/tests/test_task.py`. Run from `backend/`:

```bash
python -m pytest tests/test_task.py tests/test_agent.py tests/test_tools.py tests/test_action.py -q
```

The new tests have not been executed by this implementation session; verify them locally before merging.
