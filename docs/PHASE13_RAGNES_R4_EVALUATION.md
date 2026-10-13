# Phase 13 — RAGNES R4: retrieval evaluation

## Purpose

Provide a fixed, repeatable evaluation set before deciding whether lexical retrieval is insufficient. This phase measures the existing RAGNES retrieval behavior; it does not add embeddings, a vector database, model calls, persistence, API routes, or frontend changes.

## Run

From the `backend` directory with the project's Python dependencies installed:

```bash
python -m pytest tests/test_ragnes_r4_evaluation.py -q
python scripts/evaluate_ragnes.py
```

To evaluate a different workspace root:

```bash
python scripts/evaluate_ragnes.py --workspace /path/to/mosaic
```

The CLI prints a JSON report. Save the report with the test/revision information when recording a baseline; do not treat unrecorded or unexecuted metrics as evidence.

## Fixed cases

The default set covers:
- tool approval and Harness contract lookup;
- R3 session compaction and source references;
- safe artifact reading and symlink behavior;
- lexical retrieval bounds;
- task event/reconnection concepts.

Each case labels expected relevant path(s) and required fact strings. The set is intentionally small and versioned with code; expand it only with explicit labels and stable expected outcomes.

## Metrics

- **Retrieval recall:** fraction of labeled relevant paths returned.
- **Irrelevant context ratio:** fraction of returned result paths not labeled relevant.
- **Source correctness:** fraction of returned paths present in the bounded workspace inventory.
- **Required-fact coverage:** literal fact strings found in the combined bounded excerpts.
- **Latency:** elapsed lexical-search time per case, in milliseconds.
- **Context characters:** bounded excerpt characters compared with an all-readable-artifacts baseline.
- **Full-context baseline recall:** whether expected paths are present among readable inventory artifacts.

The all-artifacts baseline is an upper bound for path recall, not a reproduction of every historical context-assembly behavior. Its character count is the total text length of readable inventoried files, not a tokenizer estimate.

## Important limitations

- The evaluator does not call a model. It cannot establish semantic answer grounding or end-to-end task success.
- Required-fact coverage is a literal substring check, not a semantic correctness judgment.
- Latency and inventory results depend on the workspace and machine.
- The initial cases are a small smoke/evaluation set, not a statistically representative benchmark.
- No evaluation results are included in this PR because the implementation agent has not run the tests or CLI.

Before considering embeddings/hybrid retrieval, run and record this baseline, inspect per-case misses and false positives, and review whether the failures are material. RAGNES source material explicitly makes embeddings conditional on demonstrated lexical-retrieval gaps.
