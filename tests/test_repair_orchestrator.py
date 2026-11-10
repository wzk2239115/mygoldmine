import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))
import repair_orchestrator as repair_module
from submission import submit


def fixture_run(tmp_path):
    run = tmp_path / "runs/demo/one"
    run.mkdir(parents=True)
    (run / "audit-report.json").write_text(json.dumps({"project": "demo", "findings": []}))
    (run / "raw.jsonl").write_text("original session")
    result = submit(
        "orchestrator",
        run,
        {"artifact": str(run / "audit-report.json"), "summary": "original", "limitations": []},
    )
    assert result["decision"] == "accepted"
    archive = Path(str(run) + ".meta/node-retries/orchestrator/retry/original-artifacts")
    return run, archive


def test_repair_requires_fresh_tool_receipt_and_preserves_snapshot(tmp_path):
    run, archive = fixture_run(tmp_path)
    original = (run / "audit-report.json").read_bytes()

    def agent(command, **kwargs):
        assert "mcp__stage_delivery__submit_audit_report" in command[-1]
        assert kwargs["cwd"] == tmp_path
        assert (archive / "audit-report.json").read_bytes() == original
        report = run / "audit-report.json"
        report.write_text(
            json.dumps({"project": "demo", "findings": [], "limitations": ["unverified"]})
        )
        result = submit(
            "orchestrator", run, {"artifact": str(report), "summary": "repaired", "limitations": []}
        )
        assert result["decision"] == "accepted"
        return SimpleNamespace(returncode=0)

    delivery = repair_module.repair(run, archive, "demo", repo=tmp_path, invoke=agent)
    assert delivery["accepted"] == 1
    assert (archive / "raw.jsonl").read_text() == "original session"
    assert (archive / "audit-report.json").read_bytes() == original
    assert len(list((archive / ".stage-submissions/orchestrator").glob("*.json"))) == 1
    assert len(list((run / ".stage-submissions/orchestrator").glob("*.json"))) == 2


def test_successful_exit_cannot_reuse_old_receipt(tmp_path):
    run, archive = fixture_run(tmp_path)
    with pytest.raises(ValueError, match="未通过工具重新提交"):
        repair_module.repair(
            run,
            archive,
            "demo",
            repo=tmp_path,
            invoke=lambda *a, **k: SimpleNamespace(returncode=0),
        )


def test_wrong_project_rejected_before_agent_runs(tmp_path):
    run, archive = fixture_run(tmp_path)
    with pytest.raises(ValueError, match="不属于指定项目"):
        repair_module.repair(run, archive, "other", repo=tmp_path)
