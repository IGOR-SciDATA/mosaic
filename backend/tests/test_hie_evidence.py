import hashlib
import json
from types import SimpleNamespace

from app.services import hie_evidence


def test_persisted_evidence_is_registered_and_hash_verified(tmp_path, monkeypatch):
    registered = []

    monkeypatch.setattr(hie_evidence, "DATA_DIR", tmp_path)
    def register(**kwargs):
        artifact = SimpleNamespace(id=len(registered) + 1, path=kwargs["path"])
        registered.append((kwargs, artifact))
        return artifact
    monkeypatch.setattr(hie_evidence, "create_artifact", register)

    outputs = hie_evidence.persist_output_evidence(
        7, "baseline output", "candidate output", max_bytes=1024
    )
    for role, output in (
        ("baseline_output", "baseline output"),
        ("candidate_output", "candidate output"),
    ):
        ref = outputs[role]
        assert open(ref["path"], "rb").read() == output.encode("utf-8")
        assert ref["sha256"] == hashlib.sha256(output.encode("utf-8")).hexdigest()
    assert len(registered) == 2

    record = {"task_id": 7, "record_sha256": "abc123"}
    artifact = hie_evidence.persist_record_evidence(7, record, max_bytes=1024)
    stored = json.loads(open(artifact["path"], encoding="utf-8").read())
    assert stored == record
    assert registered[-1][0]["type"] == "hie_experiment_record"
    assert registered[-1][0]["metadata"]["record_sha256"] == "abc123"


def test_persist_output_evidence_enforces_combined_size_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(hie_evidence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(hie_evidence, "create_artifact", lambda **kwargs: None)
    try:
        hie_evidence.persist_output_evidence(7, "123", "456", max_bytes=5)
    except ValueError as exc:
        assert "Combined HIE output evidence" in str(exc)
    else:
        raise AssertionError("Expected combined evidence budget to be enforced")
