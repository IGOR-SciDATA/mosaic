# Phase 10 — RAGNES R1: explicit artifact context integration

## Scope

Wire the bounded artifact reader into Context Manager only when the current user message explicitly names a workspace-relative file path. This is an incremental integration; it does not add an API, schema, index, or frontend selection UI.

## Behavior

- Selects at most 3 explicit paths from the current user message.
- Reads at most 100 lines per artifact, with an aggregate excerpt budget of 8,000 characters.
- Uses the active conversation's selected project workspace; path confinement, symlink rejection, UTF-8 checks, and file-size limits remain enforced by `app.context.artifacts`.
- Adds path and line provenance to each excerpt.
- Marks excerpt content as untrusted data, not instructions or authorization.
- Does not inventory or read project files when no explicit path is mentioned.
- Does not replace or bypass the approved FilesystemTool for actions requiring tool policy/approval.

## Limitations

This increment does not add fuzzy filename resolution, lexical search, a frontend picker, or an API-level source-selection field. The explicit path must exist relative to the active workspace. Invalid paths are ignored rather than triggering broader retrieval.

## Validation

Run from `backend`:

```bash
python -m pytest tests/test_ragnes_r1_context.py tests/test_ragnes_r1_artifacts.py tests/test_ragnes_r0.py tests/test_context.py tests/test_tools.py -q
```

Tests were added but not executed by the implementation agent.
