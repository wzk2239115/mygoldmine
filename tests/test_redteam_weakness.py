import json

import test_redteam_experience

from audit_rsi.adapters.redteam import build_redteam_experience
from audit_rsi.cli import main
from audit_rsi.weakness import mine_redteam_weaknesses


def test_weakness_mining_groups_failure_signatures_without_mutating_harness(tmp_path):
    run, payload = test_redteam_experience.make_run(tmp_path)
    payload["result"].update({
        "status": "model_timeout",
        "captured": False,
        "answer": "",
        "flag_provenance": None,
    })
    (run / "result.json").write_text(json.dumps(payload))
    with (run / "agent.jsonl").open("a") as stream:
        stream.write(json.dumps({"step": 2, "role": "assistant", "content": "not-json"}) + "\n")
    trace = json.loads((run / "trace.jsonl").read_text().splitlines()[1])
    trace["returncode"] = 124
    lines = (run / "trace.jsonl").read_text().splitlines()
    lines[1] = json.dumps(trace)
    (run / "trace.jsonl").write_text("\n".join(lines) + "\n")
    record, steps = build_redteam_experience(run)
    report = mine_redteam_weaknesses([record], steps)
    assert report["status"] == "ok"
    assert report["group_count"] == 3
    assert report["mutation"] == "none"
    assert report["requires_candidate_validation"] is True
    by_failure = {group["failure_class"]: group for group in report["groups"]}
    assert by_failure["model_timeout"]["editable_surface"] == (
        "runtime_control.model_timeout_and_retry"
    )
    assert by_failure["invalid_response"]["support"] == 1
    assert by_failure["tool_failure"]["event_support"] == 1
    assert by_failure["tool_failure"]["status"] == "candidate_only"
    assert "not-json" not in json.dumps(report)

    output = tmp_path / "weakness.json"
    assert main([
        "redteam-weakness",
        "--runs", str(tmp_path),
        "--output", str(output),
    ]) == 0
    assert json.loads(output.read_text())["group_count"] == 3


def test_successful_run_does_not_invent_weakness(tmp_path):
    run, _ = test_redteam_experience.make_run(tmp_path)
    record, steps = build_redteam_experience(run)
    report = mine_redteam_weaknesses([record], steps)
    assert report["status"] == "insufficient"
    assert report["groups"] == []
