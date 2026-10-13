# Phase 11 — RAGNES R2: bounded lexical retrieval

## Scope

Adds deterministic lexical search over the active project workspace and uses it as a fallback in Context Manager when the current user request does not resolve to an explicit artifact path. No database schema, persistent index, API, or frontend changes.

## Search behavior

- Searches bounded workspace inventory metadata and UTF-8 text for terms in the current user request.
- Ranks exact path/name matches ahead of content-only matches, then orders ties deterministically by path.
- Returns matched terms, relative file path, score, bounded snippets, and source line ranges.
- Skips root/nested instruction aliases `AGENTS.md` and `AGENT.md`, which are handled separately as project instructions.
- Ignores unreadable, binary, symlinked, missing, and oversized files.

## Resource limits

- At most 200 inventory entries and 3 directory levels (existing inventory contract).
- At most 100 files scanned and 5 MB of file bytes per search.
- At most 10 results from the search primitive; Context Manager requests no more than 3.
- At most 3 snippets per file, 700 characters per snippet, and 4,000 aggregate excerpt characters in context.
- No embeddings, vector database, external dependency, or persistent index.

## Trust boundary

Retrieved content is untrusted evidence, not instructions or authorization. Search does not grant tool permissions or bypass approval. Explicitly selected paths take precedence; lexical search is used only when no explicit artifact excerpt could be resolved.

## Validation

Run from `backend`:

```bash
python -m pytest tests/test_ragnes_r2_search.py tests/test_ragnes_r2_context.py tests/test_ragnes_r1_context.py tests/test_ragnes_r1_artifacts.py tests/test_ragnes_r0.py tests/test_context.py tests/test_tools.py -q
```

Tests were added but not executed by the implementation agent.
