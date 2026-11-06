import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))
sys.path.insert(0, str(ROOT / "scripts/redteam"))
from stage_results import build_stage_results
from contracts import recompute_flag_provenance


def write(file, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value))


def fixture(root):
    run = root / "runs/demo/one"
    write(run / "audit-report.json", {"findings": [{"id": "F-1"}, {"id": "F-2"}]})
    latest = {f"demo/one/{i}": {"project": "demo", "run_id": "one", "finding_id": i}
              for i in ["F-1", "F-2"]}
    workspaces = {}
    for node in ["verify", "redteam-agent", "judge"]:
        attempt = Path(str(run) + ".meta/node-retries") / node / "first"
        workspace = attempt / "output"
        write(attempt / "attempt.json", {"id": "first", "project": "demo", "runId": "one",
              "status": "completed", "startedAt": "1", "workspace": str(workspace)})
        workspace.mkdir()
        (workspace / "audit-report.json").write_bytes((run / "audit-report.json").read_bytes())
        workspaces[node] = workspace
    blue = workspaces["verify"] / "verify/agent/F-1/verify-report.json"
    write(blue, {"project": "demo", "finding_id": "F-1",
                "verdict": "confirmed", "evidence_class": "runtime"})
    write(workspaces["verify"] / "verify/agent/summary.json",
          {"findings": [{"finding_id": "F-1", "verdict": "confirmed", "report_path": str(blue)}]})
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
    flag = "fixture-flag"
    proof = {"source": "tool_output", "event_id": "tool-1", "capture_event_id": "capture-1",
             "output_sha256": digest(flag), "flag_sha256": digest(flag)}
    document = {"project": "demo", "flag_sha256": digest(flag),
                "result": {"captured": True, "answer": flag, "flag_provenance": proof}}
    verdict = {"verdict": "approved", "intended_vulnerability": True, "flag_provenance": True,
               "no_cheat": True, "environment_plausible": True, "reproducible": True,
               "minimal": True, "confidence": "high", "reason": "fixture checked",
               "concerns": [], "recommended_status": "runtime-validated"}
    for node in ["redteam-agent", "judge"]:
        directory = workspaces[node] / "results/F-1"
        directory.mkdir(parents=True)
        (directory / "flag.txt").write_text(flag)
        write(directory / "finding.json", {"id": "F-1"})
        events = [{"kind": "tool_result", "event_id": "tool-1", "output": flag,
                   "output_sha256": digest(flag)},
                  {"kind": "flag_capture", "event_id": "capture-1", "tool_event_id": "tool-1",
                   "output_sha256": digest(flag), "flag_sha256": digest(flag)}]
        (directory / "trace.jsonl").write_text("\n".join(map(json.dumps, events)))
        data = dict(document)
        if node == "judge":
            data.update(judge=verdict, status="judge_approved",
                        flag_provenance_verified=recompute_flag_provenance(directory, data))
        write(directory / "result.json", data)
        relative = "redteam/summary.json" if node == "redteam-agent" else "judge/summary.json"
        write(workspaces[node] / relative, {"results": [{"id": "F-1",
              "status": "flag_captured" if node == "redteam-agent" else "judge_approved",
              "run_dir": str(directory)}]})
    return run, latest, workspaces


def test_three_stages_bind_to_same_occurrence_and_recompute_evidence(tmp_path):
    run, latest, _ = fixture(tmp_path)
    states = build_stage_results(latest, tmp_path, tmp_path / "runs")
    result = states["demo/one/F-1"]["stageResults"]
    assert [result[x]["status"] for x in ["blue", "red", "judge"]] == [
        "confirmed", "flag_captured", "judge_approved"]
    assert result["red"]["provenanceVerified"]
    assert result["judge"]["provenanceVerified"]
    assert all(x["status"] == "not_selected"
               for x in states["demo/one/F-2"]["stageResults"].values())


def test_changed_report_rejects_all_old_stage_results(tmp_path):
    run, latest, _ = fixture(tmp_path)
    (run / "audit-report.json").write_text('{"findings":[]}')
    states = build_stage_results(latest, tmp_path, tmp_path / "runs")
    assert all(x["status"] == "stale"
               for x in states["demo/one/F-1"]["stageResults"].values())


def test_forged_capture_and_copied_approval_do_not_pass(tmp_path):
    _, latest, workspaces = fixture(tmp_path)
    (workspaces["redteam-agent"] / "results/F-1/trace.jsonl").write_text("")
    states = build_stage_results(latest, tmp_path, tmp_path / "runs")
    result = states["demo/one/F-1"]["stageResults"]
    assert result["red"]["status"] == "evidence_invalid"
    assert result["judge"]["status"] == "evidence_invalid"


def test_latest_running_batch_does_not_reuse_old_confirmation(tmp_path):
    run, latest, _ = fixture(tmp_path)
    file = Path(str(run) + ".meta/node-retries/verify/new/attempt.json")
    write(file, {"project": "demo", "runId": "one", "status": "running", "startedAt": "2"})
    states = build_stage_results(latest, tmp_path, tmp_path / "runs")
    assert states["demo/one/F-1"]["stageResults"]["blue"]["status"] == "running"
    assert states["demo/one/F-1"]["stageResults"]["red"]["status"] == "evidence_invalid"
    assert states["demo/one/F-1"]["stageResults"]["judge"]["status"] == "evidence_invalid"


def test_other_run_cannot_attach_result_by_same_finding_id(tmp_path):
    run, latest, _ = fixture(tmp_path)
    file = Path(str(run) + ".meta/node-retries/verify/first/attempt.json")
    job = json.loads(file.read_text())
    job["runId"] = "other"
    write(file, job)
    states = build_stage_results(latest, tmp_path, tmp_path / "runs")
    assert states["demo/one/F-1"]["stageResults"]["blue"]["status"] == "invalid"

def test_duplicate_finding_identity_never_guesses_which_occurrence(tmp_path):
    _, latest, _ = fixture(tmp_path)
    latest["demo/one/F-1~2"] = dict(latest["demo/one/F-1"])
    states = build_stage_results(latest, tmp_path, tmp_path / "runs")
    for key in ["demo/one/F-1", "demo/one/F-1~2"]:
        assert all(x["status"] == "identity_ambiguous"
                   for x in states[key]["stageResults"].values())


def test_stale_native_upstream_manifest_invalidates_capture_and_approval(tmp_path):
    _, latest, workspaces = fixture(tmp_path)
    summary = workspaces["verify"] / "verify/agent/summary.json"
    write(workspaces["redteam-agent"] / "workflow-inputs.json",
          {"artifacts": [{"file": str(summary), "sha256": "changed"}]})
    states = build_stage_results(latest, tmp_path, tmp_path / "runs")
    assert states["demo/one/F-1"]["stageResults"]["red"]["status"] == "evidence_invalid"
    assert states["demo/one/F-1"]["stageResults"]["judge"]["status"] == "evidence_invalid"
