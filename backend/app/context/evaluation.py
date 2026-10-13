"""Fixed, deterministic evaluation for RAGNES lexical retrieval.

This measures retrieval against labeled workspace artifacts. It does not call a
model and therefore does not claim to measure generated-answer quality or task
success; those require a separately labeled end-to-end evaluation.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable

from app.context.artifacts import list_workspace_artifacts
from app.context.search import search_workspace_artifacts


RAGNES_EVAL_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "explicit-tool-approval",
        "query": "tool approval",
        "relevant_paths": ["docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md"],
        "required_facts": ["approval"],
    },
    {
        "id": "context-compaction",
        "query": "session compaction source references",
        "relevant_paths": ["backend/app/context/session_compaction.py"],
        "required_facts": ["source_refs", "constraints"],
    },
    {
        "id": "artifact-safe-read",
        "query": "workspace artifact excerpt symlink",
        "relevant_paths": ["backend/app/context/artifacts.py"],
        "required_facts": ["symlink"],
    },
    {
        "id": "lexical-search-bounds",
        "query": "lexical search max files snippets",
        "relevant_paths": ["backend/app/context/search.py"],
        "required_facts": ["MAX_FILES_SCANNED", "MAX_MATCHES_PER_FILE"],
    },
    {
        "id": "task-events-reconnect",
        "query": "task events reconnect Last-Event-ID",
        "relevant_paths": ["docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md"],
        "required_facts": ["event"],
    },
)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _all_text_for_path(workspace: Path, relative_path: str) -> str:
    try:
        return (workspace / relative_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return ""


def evaluate_ragnes(
    workspace: str | Path,
    cases: Iterable[dict[str, Any]] = RAGNES_EVAL_CASES,
    *,
    max_results: int = 3,
    max_context_chars: int = 4_000,
) -> dict[str, Any]:
    """Evaluate lexical retrieval and compare it with an all-artifacts baseline.

    Recall is measured over labeled relevant paths. Irrelevant-context ratio is
    the fraction of selected result files not labeled relevant. Fact coverage
    checks whether each labeled fact appears in the selected excerpts. Source
    correctness checks that each result path exists in the workspace inventory.
    The full-context baseline includes every readable inventory artifact, making
    its recall an upper bound rather than a quality claim.
    """
    root = Path(workspace).resolve(strict=True)
    case_list = list(cases)
    inventory = list_workspace_artifacts(root)
    inventory_paths = {item["path"] for item in inventory["entries"]}
    all_readable_paths = [
        path for path in sorted(inventory_paths)
        if _all_text_for_path(root, path)
    ]

    rows: list[dict[str, Any]] = []
    retrieval_chars_total = 0
    baseline_chars_total = sum(len(_all_text_for_path(root, path)) for path in all_readable_paths)

    for case in case_list:
        relevant = set(case.get("relevant_paths", []))
        started = time.perf_counter()
        search = search_workspace_artifacts(root, str(case["query"]), max_results=max_results)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        results = search["results"]
        selected_paths = [item["path"] for item in results]
        selected_set = set(selected_paths)
        retrieved_relevant = relevant & selected_set
        recall = len(retrieved_relevant) / len(relevant) if relevant else 1.0
        irrelevant_ratio = (
            sum(path not in relevant for path in selected_paths) / len(selected_paths)
            if selected_paths else (0.0 if not relevant else 1.0)
        )
        excerpts = "\n".join(
            snippet["content"]
            for item in results
            for snippet in item.get("snippets", [])
        )
        normalized_excerpt = _normalize(excerpts)
        required_facts = [str(fact) for fact in case.get("required_facts", [])]
        covered_facts = [fact for fact in required_facts if _normalize(fact) in normalized_excerpt]
        retrieved_chars = len(excerpts)
        retrieval_chars_total += retrieved_chars
        rows.append({
            "id": str(case["id"]),
            "query": str(case["query"]),
            "expected_paths": sorted(relevant),
            "retrieved_paths": selected_paths,
            "recall": round(recall, 4),
            "irrelevant_context_ratio": round(irrelevant_ratio, 4),
            "source_correctness": round(
                sum(path in inventory_paths for path in selected_paths) / len(selected_paths),
                4,
            ) if selected_paths else 1.0,
            "required_facts": required_facts,
            "covered_facts": covered_facts,
            "required_fact_coverage": round(
                len(covered_facts) / len(required_facts), 4
            ) if required_facts else 1.0,
            "retrieved_chars": retrieved_chars,
            "latency_ms": latency_ms,
            "truncated": bool(search.get("truncated", False)),
            "baseline_recall": round(
                len(relevant & set(all_readable_paths)) / len(relevant), 4
            ) if relevant else 1.0,
            "baseline_artifact_count": len(all_readable_paths),
        })

    count = len(rows)
    average = lambda key: round(sum(row[key] for row in rows) / count, 4) if count else 0.0
    return {
        "schema_version": 1,
        "evaluation": "ragnes-r4-lexical-retrieval",
        "case_count": count,
        "metrics": {
            "mean_retrieval_recall": average("recall"),
            "mean_irrelevant_context_ratio": average("irrelevant_context_ratio"),
            "mean_source_correctness": average("source_correctness"),
            "mean_required_fact_coverage": average("required_fact_coverage"),
            "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / count, 3) if count else 0.0,
            "mean_retrieved_chars": round(retrieval_chars_total / count, 2) if count else 0.0,
            "full_context_baseline_mean_recall": average("baseline_recall"),
            "full_context_baseline_chars": baseline_chars_total,
            "lexical_context_chars": retrieval_chars_total,
            "context_char_reduction_ratio": round(
                1 - retrieval_chars_total / baseline_chars_total, 4
            ) if baseline_chars_total else 0.0,
        },
        "cases": rows,
        "limitations": [
            "This evaluates labeled retrieval behavior, not model-generated answer grounding or end-to-end task success.",
            "The full-context baseline is a simple all-readable-artifacts upper bound, not a reproduction of every historical context assembly behavior.",
            "Required-fact coverage is a literal excerpt check; it does not prove semantic correctness.",
            "Results are environment-specific; latency and corpus inventory can vary by workspace.",
        ],
    }
