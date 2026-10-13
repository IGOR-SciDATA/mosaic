"""Run the fixed RAGNES retrieval evaluation and print a JSON report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.context.evaluation import evaluate_ragnes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Mosaic repository/workspace root (defaults to repository root)",
    )
    parser.add_argument(
        "--max-results", type=int, default=3,
        help="Maximum lexical results per evaluation case (1-10)",
    )
    parser.add_argument(
        "--max-context-chars", type=int, default=4000,
        help="Maximum combined excerpt characters per case",
    )
    args = parser.parse_args()
    report = evaluate_ragnes(
        args.workspace,
        max_results=args.max_results,
        max_context_chars=args.max_context_chars,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
