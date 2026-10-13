# Phase 8 — RAGNES R0: scope-aware bounded context

## Scope

This increment starts Master roadmap Phase 4 and implements only the first RAGNES R0 slice. It does not implement lexical retrieval, nested instruction discovery, embeddings, session compaction, or a frontend source inspector.

## Changes

- Load a root-level \`AGENTS.md\` only from the workspace of the conversation's selected project.
- Resolve the workspace and candidate file before reading; reject paths that resolve outside the workspace, including symlink escapes.
- Ignore missing, unreadable, non-UTF-8, non-file, or oversized instruction files. The current maximum is 12,000 bytes.
- Include a SHA-256 content fingerprint and a clear trust boundary in the context entry. Project instructions are untrusted data and cannot override Core safety policy or grant permissions.
- Limit tool observations to the five most recent results and 3,000 characters per observation.
- Bound serialized active task context to 4,000 characters.
- Preserve the current identity, memory scoping, recent-history window, and current-user-message ordering.

## Deliberate limitations

- Only root-level \`AGENTS.md\` is supported in this increment. Nested instruction files and \`AGENT.md\` alias are deferred until a separate scoped implementation.
- No database schema changes or new runtime dependencies are introduced.
- A fingerprint is calculated from the content read for this request; this increment does not maintain a long-lived cache.
- This change improves deterministic bounds, but does not claim a complete token budget or provider-specific token accounting.

## Validation

Run from \`backend\`:

\`\`\`bash
python -m pytest tests/test_ragnes_r0.py tests/test_context.py tests/test_agent.py tests/test_harness.py -q
\`\`\`

Tests were added but were not executed by the implementation agent. Results must be recorded after a local run.
