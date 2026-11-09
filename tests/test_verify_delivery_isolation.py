"""Candidate delivery failures must not abort unrelated verification results."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/stages"))
from submission import accepted_submissions, submit

spec = importlib.util.spec_from_file_location("verify_parallel", ROOT / "scripts/verify/parallel.py")
parallel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parallel)


def candidate(output, sid):
    folder = output / sid
    folder.mkdir(parents=True)
    report = folder / "verify-report.json"
    report.write_text(json.dumps({
        "project": "demo", "finding_id": sid, "verdict": "rejected",
        "reason": "安全检查有效", "evidence": [],
    }))
    receipt = submit("verify", folder, {
        "artifact": str(report), "summary": "验证结束", "limitations": [],
    })
    assert receipt["decision"] == "accepted"
    return report


def test_invalid_candidate_is_blocked_while_valid_candidate_is_preserved(tmp_path):
    workspace = tmp_path / "output"
    output = workspace / "verify/agent"
    good = candidate(output, "GOOD")
    bad = candidate(output, "BAD")
    original = good.read_bytes()
    bad.write_text(bad.read_text() + " ")
    results = parallel.finalize_deliveries(output, [
        {"finding_id": "BAD", "verdict": "rejected"},
        {"finding_id": "GOOD", "verdict": "rejected"},
    ], "demo")
    assert results[0]["delivery_status"] == "rejected"
    assert results[0]["verdict"] == "blocked"
    assert Path(results[0]["delivery_archive"], "verify-report.json").is_file()
    assert results[1]["delivery_status"] == "accepted"
    assert results[1]["verdict"] == "rejected"
    assert good.read_bytes() == original
    (output / "summary.json").write_text(json.dumps({"findings": results}))
    assert accepted_submissions("verify", workspace, minimum=2)["accepted"] == 2
    # Actual corruption in a current delivery still fails closed.
    good.write_text("changed")
    with pytest.raises(ValueError, match="内容已改变"):
        accepted_submissions("verify", workspace, minimum=2)


def test_historical_receipt_does_not_validate_a_new_attempt(tmp_path):
    output = tmp_path / "verify/agent"
    report = candidate(output, "RETRY")
    history = output / "retry-history/RETRY/1"
    history.parent.mkdir(parents=True)
    report.parent.rename(history)
    report.parent.mkdir()
    report.write_text(json.dumps({
        "project": "demo", "finding_id": "RETRY", "verdict": "blocked",
        "synthesized": True, "reason": "第二次尝试超时", "evidence": [],
    }))
    results = parallel.finalize_deliveries(
        output, [{"finding_id": "RETRY", "verdict": "blocked"}], "demo",
    )
    assert results[0]["delivery_status"] == "accepted"
    (output / "summary.json").write_text(json.dumps({"findings": results}))
    assert accepted_submissions("verify", tmp_path)["accepted"] == 1


def test_no_valid_candidates_does_not_fabricate_confirmation(tmp_path):
    output = tmp_path / "verify/agent"
    output.mkdir(parents=True)
    results = parallel.finalize_deliveries(
        output, [{"finding_id": "MISSING", "verdict": "confirmed"}], "demo",
    )
    assert results[0]["verdict"] == "blocked"
    assert json.loads((output / "MISSING/verify-report.json").read_text())["evidence"] == []
