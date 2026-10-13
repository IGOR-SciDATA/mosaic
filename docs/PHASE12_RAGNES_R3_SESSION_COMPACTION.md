# Phase 12 — RAGNES R3: bounded session compaction

## Scope

This increment derives a versioned, structured session summary from older persisted conversation messages and the current active Task state. It is added to Context Manager only when history exceeds the existing recent-history window.

The summary is deterministic and bounded. It records source message references, the current objective, active task state, explicit user messages that match constraint markers, prior assistant statements, tool-role observations, and possible open issues. Assistant statements are deliberately not labeled as verified outcomes.

## Source-of-truth and safety rules

- The summary is a derived view; original messages, Task records, ToolCall/ToolResult records, and workspace artifacts remain canonical.
- Each selected historical item retains a message ID reference.
- The current request and recent history remain present in the context.
- Summary content is untrusted conversation data, not instructions or authorization.
- The summary does not infer a next step or claim that assistant statements are verified.
- This increment does not persist generated summaries, add database tables/columns, or introduce a new Session entity.
- Selection is heuristic and deterministic; absence from the summary does not prove a decision or issue never existed.

## Bounds

- Structured summary serialized target: 6,000 characters.
- At most 8 selected entries per summary category.
- Each historical entry is clipped to 900 characters.
- At most 40 source references are emitted; total source count and a truncation flag remain available.
- The existing recent-history and task-context bounds remain in effect.

## Validation

Tests have not been run by the implementation agent. From `backend`:

```bash
python -m pytest tests/test_ragnes_r3_compaction.py tests/test_ragnes_r2_search.py tests/test_ragnes_r2_context.py tests/test_ragnes_r1_context.py tests/test_ragnes_r1_artifacts.py tests/test_ragnes_r0.py tests/test_context.py tests/test_tools.py -q
```

## Limitations / next work

This is the first R3 increment, not semantic model-generated summarization. Constraint and open-issue detection use transparent marker matching and can miss implicit constraints. A future increment should use the fixed retrieval/continuity evaluation set before adding model-based compaction or persistence. Stale-summary detection is not applicable to this derived-on-demand summary; source records are read at context-build time.
