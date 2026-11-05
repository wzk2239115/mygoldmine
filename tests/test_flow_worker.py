# ruff: noqa: E501
from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.workflow import flow_worker as flow

KEY = "demo/r1/F-1"


def _item(tmp_path: Path) -> dict:
    report = tmp_path / "runs" / "demo" / "r1" / "audit-report.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"findings":[]}', encoding="utf-8")
    return {
        "occurrence_id": KEY,
        "semantic_id": "sem-F-1",
        "project": "demo",
        "run_id": "r1",
        "local_id": "F-1",
        "finding_id": "F-1",
        "severity": "high",
        "report": str(report),
        "raw": {"id": "F-1", "root_cause": "fixture", "evidence": []},
    }


def _script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _wrapper(tmp_path: Path, name: str, body: str) -> Path:
    impl = tmp_path / f"{name}_impl.py"
    impl.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    return _script(tmp_path / f"{name}.sh", f"""#!/usr/bin/env bash
exec python3 "$(dirname "$0")/{name}_impl.py" "$@"
""")

def _fake_phase4(tmp_path: Path) -> Path:
    return _wrapper(tmp_path, "phase4", """import argparse, json, os
from pathlib import Path
p = argparse.ArgumentParser()
for name in ["project", "run-dir", "image", "source", "max", "severity", "timeout", "agent-timeout", "claude-bin", "output", "finding-id", "occurrence-id", "semantic-id", "run-id", "model"]:
    p.add_argument("--" + name, default="")
a = p.parse_args()
out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
marker = os.environ.get("FAKE_PHASE4_MARKER")
if marker:
    Path(marker).open("a", encoding="utf-8").write("called\\n")
verdict = os.environ.get("FAKE_VERDICT", "confirmed")
report = out / "verify-report.json"
report.write_text(json.dumps({"verdict": verdict, "evidence_class": "runtime", "occurrence_id": a.occurrence_id}), encoding="utf-8")
(out / "summary.json").write_text(json.dumps({"findings": [{"finding_id": a.finding_id, "occurrence_id": a.occurrence_id, "semantic_id": a.semantic_id, "run_id": a.run_id, "verdict": verdict, "report_path": str(report)}]}), encoding="utf-8")
""")


def _fake_phase5(tmp_path: Path) -> Path:
    return _wrapper(tmp_path, "phase5", """import argparse, json, os
from pathlib import Path
p = argparse.ArgumentParser()
for name in ["project", "run-dir", "max", "severity", "finding-id", "model", "base-url", "api-key", "build-timeout", "agent-timeout", "judge-timeout", "judge-claude", "judge-claude-model", "output"]:
    p.add_argument("--" + name, default="")
a = p.parse_args()
out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
(out / "summary.json").write_text(json.dumps({"status": os.environ.get("FAKE_REDTEAM_STATUS", "completed"), "results": [{"project": a.project, "id": a.finding_id, "status": os.environ.get("FAKE_REDTEAM_OUTCOME", "judge_approved")}]}), encoding="utf-8")
""")


def _fake_visual(tmp_path: Path) -> Path:
    return _wrapper(tmp_path, "visual", """import argparse, os
from pathlib import Path
p = argparse.ArgumentParser()
for name in ["project", "run-dir", "max", "finding-id", "timeout", "agent-timeout", "claude-bin", "output", "model"]:
    p.add_argument("--" + name, default="")
a = p.parse_args()
out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
(out / "report-illustrated.md").write_text("# illustrated\\n", encoding="utf-8")
(out / f"scene-{a.finding_id}.webp").write_bytes(b"RIFF")
(out / "visual-summary.json").write_text('{"status":"ready"}', encoding="utf-8")
""")


def _configure(tmp_path: Path, monkeypatch, *, status="triage", env_ready=True):
    item = _item(tmp_path)
    monkeypatch.setattr(flow, "ROOT", tmp_path)
    monkeypatch.setattr(flow, "DATA", tmp_path / "data")
    monkeypatch.setattr(flow, "FLOW_STATE", flow.DATA / "flow-state.json")
    monkeypatch.setattr(flow, "FLOW_QUEUE", flow.DATA / "flow-queue.json")
    monkeypatch.setattr(flow, "PAUSE", flow.DATA / "flow.pause")
    monkeypatch.setattr(flow, "STOP", flow.DATA / "flow.stop")
    monkeypatch.setattr(flow, "LOCK", flow.DATA / ".flow-worker.lock")
    monkeypatch.setattr(flow, "TRAJECTORY", tmp_path / "flow.jsonl")
    monkeypatch.setattr(flow, "PHASE4", _fake_phase4(tmp_path))
    monkeypatch.setattr(flow, "PHASE5", _fake_phase5(tmp_path))
    monkeypatch.setattr(flow, "VISUAL", _fake_visual(tmp_path))
    monkeypatch.setattr(flow, "BUILD_STATE", _script(tmp_path / "build_state.py", "import os\nfrom pathlib import Path\nPath(os.environ['FLOW_BUILD_STATE_MARKER']).write_text('ran')\n"))
    flow.DATA.mkdir(parents=True)
    (flow.DATA / "refine-state.json").write_text(json.dumps({"findings": {KEY: {"status": status}}}), encoding="utf-8")
    (flow.DATA / "auto-state.json").write_text('{"findings":{}}', encoding="utf-8")
    (flow.DATA / "curated.json").write_text("{}", encoding="utf-8")
    (flow.DATA / "state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(flow.base.finding_ledger, "build_ledger", lambda: {})
    monkeypatch.setattr(flow.base, "latest_findings", lambda ledger: {KEY: item})
    monkeypatch.setattr(
        flow.base.finding_ledger,
        "merge_manual_state",
        lambda ledger, payloads: (payloads[0].get("findings", payloads[0]) if isinstance(payloads[0], dict) else {}),
    )
    if env_ready:
        source = tmp_path / "source"
        source.mkdir()
        (tmp_path / "env" / "demo").mkdir(parents=True)
        (tmp_path / "env" / "demo" / "env-manifest.json").write_text(
            json.dumps({"env_status": "ready", "image": "fake:demo", "source": str(source)}),
            encoding="utf-8",
        )
    monkeypatch.setenv("FLOW_DOCKER_BIN", "/bin/true")
    monkeypatch.setenv("FLOW_BUILD_STATE_MARKER", str(tmp_path / "build-state.called"))
    monkeypatch.setenv("FAKE_PHASE4_MARKER", str(tmp_path / "phase4.called"))
    monkeypatch.setattr(sys, "argv", ["flow_worker.py", "--once"])
    return item


def test_flow_verify_confirmed_moves_to_reproduce(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    assert flow.main() == 0
    state = json.loads(flow.FLOW_STATE.read_text(encoding="utf-8"))
    record = state["findings"][KEY]
    assert record["status"] == "reproduce"
    assert record["source"] == "flow"
    assert record["flowStage"] == "verify"
    assert record["flowOutcome"] == "confirmed"
    assert record["verifyVerdict"] == "confirmed"
    assert (tmp_path / "phase4.called").exists()
    assert (tmp_path / "flow.jsonl").exists()


def test_flow_verify_rejected_closes_finding(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_VERDICT", "rejected")
    assert flow.main() == 0
    record = json.loads(flow.FLOW_STATE.read_text(encoding="utf-8"))["findings"][KEY]
    assert record["status"] == "closed"
    assert record["verdict"] == "fp"
    assert record["flowOutcome"] == "rejected"


def test_flow_blocked_is_not_retried_after_max_attempts(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_VERDICT", "inconclusive")
    assert flow.main() == 0
    marker = tmp_path / "phase4.called"
    first = marker.read_text(encoding="utf-8")
    record = json.loads(flow.FLOW_STATE.read_text(encoding="utf-8"))["findings"][KEY]
    assert record["status"] == "triage"
    assert record["flowAttempts"] == 1
    monkeypatch.setattr(sys, "argv", ["flow_worker.py", "--once"])
    assert flow.main() == 0
    assert marker.read_text(encoding="utf-8") == first


def test_flow_redteam_approved_calls_build_state(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, status="reproduce")
    assert flow.main() == 0
    record = json.loads(flow.FLOW_STATE.read_text(encoding="utf-8"))["findings"][KEY]
    assert record["status"] == "reproduce"
    assert record["flowStage"] == "redteam"
    assert record["flowOutcome"] == "judge_approved"
    assert record["visualStatus"] == "ready"
    assert (tmp_path / "build-state.called").exists()


def test_flow_missing_env_records_block_without_invoking_phase4(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, env_ready=False)
    assert flow.main() == 0
    record = json.loads(flow.FLOW_STATE.read_text(encoding="utf-8"))["findings"][KEY]
    assert record["flowOutcome"] == "blocked"
    assert record["flowBlocked"] is True
    assert record["status"] == "triage"
    assert not (tmp_path / "phase4.called").exists()
