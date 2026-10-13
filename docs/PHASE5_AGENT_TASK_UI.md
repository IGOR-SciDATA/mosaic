# Mosaic — Phase 5 Agent Task UI

**Branch:** `codex/phase5-agent-task-ui`  
**Scope:** expose the existing Agent Task run and human approval loop in the project's Tarefas tab.

## User flow

1. Open a project and select a conversation with an enabled model.
2. Open **Tarefas** and create a new Agent task.
3. The UI starts the task through `POST /tasks/{id}/run`.
4. If the Agent requests an approval-required tool, the task card presents **Aprovar ferramenta** and **Rejeitar**.
5. After the human decision, the task returns to executing; **Continuar Agent** calls the run endpoint again.
6. Completed output or a failure result is displayed in the task card.

## Boundaries

- Uses existing Task, Agent, tool approval, and run APIs; no schema changes.
- Tasks remain attached to the active conversation/project.
- Approval is explicit; the UI never executes the pending tool before the user approves it.
- Terminal tasks are not offered a retry button because the Agent loop intentionally does not revive failed/completed/cancelled tasks.
- This UI does not add streaming, background execution, or automatic polling. The user can navigate back to Tarefas to refresh task state.

## Validation

Build the frontend from `frontend/`:

```bash
npm run build
```

Then validate the backend integration from `backend/`:

```bash
python -m pytest tests/test_harness.py tests/test_task.py tests/test_agent.py tests/test_tools.py tests/test_action.py -q
```

The build and tests have not been executed in this implementation session.
