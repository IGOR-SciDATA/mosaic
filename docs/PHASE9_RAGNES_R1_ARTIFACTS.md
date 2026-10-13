# Phase 9 — RAGNES R1: safe artifact inventory and direct excerpts

## Scope

This increment adds the backend primitive for RAGNES R1. It complements the existing approved FilesystemTool; it is read-only context/retrieval infrastructure and does not replace tool policy or authorization.

## Implemented

- Bounded workspace inventory of regular files with relative path, name, suffix, and size metadata; it does not read file contents.
- Excludes common generated/vendor directories such as \`.git\`, \`.venv\`, \`node_modules\`, \`__pycache__\`, and \`.mosaic\`.
- Caps inventory at 200 entries and three directory levels by default, with explicit truncation metadata.
- Bounded UTF-8 excerpts by relative path, start line, line count, and character count; returns path and line provenance.
- Rejects absolute paths, traversal, missing files, symlinks, non-files, binary/non-UTF-8 content, and files over 1 MB.
- No database changes, external dependencies, or file writes.

## Integration boundary

The functions are exposed in \`app.context.artifacts\` for context/retrieval services to call. This increment does not automatically inject an inventory into every model prompt, add a new API endpoint, or change frontend behavior. Explicit source selection and end-to-end source display require their own integration increment.

## Validation

Run from \`backend\`:

\`\`\`bash
python -m pytest tests/test_ragnes_r1_artifacts.py tests/test_ragnes_r0.py tests/test_context.py tests/test_tools.py -q
\`\`\`

Tests were added but not executed by the implementation agent.
