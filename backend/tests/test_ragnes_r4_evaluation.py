from app.context.evaluation import evaluate_ragnes


def test_evaluation_reports_recall_fact_coverage_and_source_correctness(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "approval.py").write_text(
        "def request_approval():\n    return 'pending approval'\n",
        encoding="utf-8",
    )
    (workspace / "unrelated.txt").write_text(
        "orchids and gardening", encoding="utf-8"
    )
    cases = [{
        "id": "approval",
        "query": "request approval",
        "relevant_paths": ["approval.py"],
        "required_facts": ["pending approval"],
    }]

    report = evaluate_ragnes(workspace, cases, max_results=2)

    assert report["schema_version"] == 1
    assert report["case_count"] == 1
    case = report["cases"][0]
    assert case["recall"] == 1.0
    assert case["source_correctness"] == 1.0
    assert case["required_fact_coverage"] == 1.0
    assert case["retrieved_paths"][0] == "approval.py"
    assert report["metrics"]["full_context_baseline_mean_recall"] == 1.0
    assert "not model-generated answer grounding" in " ".join(report["limitations"])


def test_evaluation_counts_irrelevant_results_and_missing_facts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "approval.py").write_text(
        "def request_approval():\n    return 'pending approval'\n",
        encoding="utf-8",
    )
    (workspace / "approval_notes.txt").write_text(
        "approval history without the required policy fact", encoding="utf-8"
    )
    cases = [{
        "id": "missing-fact",
        "query": "approval",
        "relevant_paths": ["approval.py"],
        "required_facts": ["the exact missing requirement"],
    }]

    report = evaluate_ragnes(workspace, cases, max_results=2)

    case = report["cases"][0]
    assert case["recall"] == 1.0
    assert case["irrelevant_context_ratio"] > 0.0
    assert case["required_fact_coverage"] == 0.0
    assert case["retrieved_chars"] <= 4_000


def test_evaluation_empty_case_set_is_well_defined(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    report = evaluate_ragnes(workspace, [])

    assert report["case_count"] == 0
    assert report["metrics"]["mean_retrieval_recall"] == 0.0
    assert report["cases"] == []
