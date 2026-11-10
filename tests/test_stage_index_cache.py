import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/workflow"))
from stage_results import upstream_checker


def test_batch_reads_upstream_once_and_next_refresh_detects_changes(tmp_path, monkeypatch):
    import stage_results
    source = tmp_path / "source"
    source.mkdir()
    report = source / "summary.json"
    report.write_text("{}")
    (tmp_path / "workflow-inputs.json").write_text(json.dumps({"artifacts": [
        {"file": str(report), "sha256": hashlib.sha256(report.read_bytes()).hexdigest()}
    ]}))
    calls = []
    original = Path.read_bytes

    def counted(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", counted)
    contexts = {"blue": (source, "summary.json")}
    check = upstream_checker(tmp_path, contexts, "red")
    for _ in range(100):
        check("blue")
    assert calls == [report]
    report.write_text("changed")
    with pytest.raises(ValueError, match="已变化"):
        upstream_checker(tmp_path, contexts, "red")("blue")


def test_legacy_alias_and_mismatched_hash_still_checked(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    report = source / "summary.json"
    report.write_text("{}")
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    inputs = tmp_path / "workflow-inputs.json"
    inputs.write_text(json.dumps({"artifacts": [
        {"file": str(alias / "summary.json"),
         "sha256": hashlib.sha256(report.read_bytes()).hexdigest()}
    ]}))
    contexts = {"blue": (source, "summary.json")}
    upstream_checker(tmp_path, contexts, "red")("blue")
    inputs.write_text(json.dumps({"artifacts": [
        {"file": str(alias / "summary.json"), "sha256": "wrong"}
    ]}))
    with pytest.raises(ValueError, match="已变化"):
        upstream_checker(tmp_path, contexts, "red")("blue")
