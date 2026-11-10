import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))
from stage_tools import SPECS, materialize, submit_structured, tool, validate
from submission import accepted_submissions


@pytest.mark.parametrize("stage", list(SPECS))
def test_each_stage_exposes_only_its_own_inputs(stage):
    api = tool(stage)
    assert api["name"] == SPECS[stage][0]
    properties = api["inputSchema"]["properties"]
    assert "artifact" not in properties
    assert "project" not in properties
    assert "finding_id" not in properties
    with pytest.raises(ValueError, match="不允许"):
        validate(
            {
                "summary": "真实说明",
                "limitations": [],
                "project": "other",
                **{
                    key: []
                    for key in api["inputSchema"]["required"]
                    if key not in {"summary", "limitations"}
                },
            },
            {
                "type": "object",
                "properties": {"summary": {}, "limitations": {}},
                "additionalProperties": False,
            },
        )


@pytest.mark.parametrize(
    ("stage", "data", "filename"),
    [
        (
            "environment",
            {"env_status": "blocked", "reason": "Docker unavailable"},
            "env-manifest.json",
        ),
        ("orchestrator", {"findings": []}, "audit-report.json"),
        (
            "verify",
            {"verdict": "blocked", "reason": "missing runtime", "evidence": []},
            "verify-report.json",
        ),
        ("redteam-agent", {}, "stage-result.json"),
        (
            "learner",
            {
                "status": "no_changes",
                "proposal_ids": [],
                "conclusions": [
                    {
                        "stage": "verify",
                        "category": "no_change",
                        "reason": "未取得新证据",
                        "next_action": "等待证据",
                        "evidence": ["feedback.txt"],
                    }
                ],
            },
            "rsi/learning-result.json",
        ),
    ],
)
def test_domain_submission_generates_bound_artifact(stage, data, filename, tmp_path):
    (tmp_path / "feedback.txt").write_text("actual feedback")
    (tmp_path / "result.json").write_text(
        json.dumps({"project": "demo", "result": {"status": "not_captured", "captured": False}})
    )
    args = {**data, "summary": "真实交付", "limitations": ["未动态确认"]}
    result = submit_structured(stage, tmp_path, args, task={"project": "demo", "finding_id": "F-1"})
    assert result["success"], result
    document = json.loads((tmp_path / filename).read_text())
    assert document["project"] == "demo"
    assert document["finding_id"] == "F-1"
    assert accepted_submissions(stage, tmp_path)["accepted"] == 1


def test_rejected_revision_does_not_overwrite_previous_report(tmp_path):
    task = {"project": "demo"}
    args = {"findings": [], "summary": "完整交付", "limitations": []}
    accepted = submit_structured("orchestrator", tmp_path, args, task)
    assert accepted["success"]
    old = (tmp_path / "audit-report.json").read_bytes()
    rejected = submit_structured(
        "orchestrator", tmp_path, {**args, "findings": [{"id": "F-1", "title": "不完整"}]}, task
    )
    assert not rejected["success"]
    assert rejected["tool"] == "submit_audit_report"
    assert rejected["repair"]["arguments_example"]
    assert (tmp_path / "audit-report.json").read_bytes() == old


def test_execution_tool_cannot_invent_success(tmp_path):
    args = {"summary": "测试", "limitations": [], "captured": True}
    result = submit_structured("redteam-agent", tmp_path, args, {"project": "demo"})
    assert not result["success"]
    assert "captured" in str(result["errors"])
    assert not (tmp_path / "stage-result.json").exists()


def test_lab_tool_injects_source_and_candidate_binding(tmp_path):
    task = {
        "project": "demo",
        "finding_id": "F-1",
        "finding_sha256": "abc",
        "source_binding": {"commit": "123"},
    }
    path, data = materialize(
        "redteam-lab",
        tmp_path,
        {"blocked": {"reason": "no runtime"}, "limitations": ["missing"]},
        task,
    )
    assert path.name == "blocked.json"
    assert data["source"] == task["source_binding"]
    assert data["finding_sha256"] == "abc"
    assert data["finding_id"] == "F-1"


def test_review_submission_preserves_input_execution(tmp_path):
    snapshot = {
        "schema_version": 2,
        "project": "demo",
        "result": {"status": "not_captured", "captured": False},
    }
    original = json.dumps(snapshot).encode()
    for name in ("result.json", "judge-input-result.json"):
        (tmp_path / name).write_bytes(original)
    (tmp_path / "finding.json").write_text('{"id":"F-1"}')
    (tmp_path / "trace.jsonl").write_text("{}")
    args = {
        "summary": "证据不足",
        "limitations": ["未成功捕获"],
        "verdict": "needs_review",
        "reason": "证据不足",
        "concerns": ["需补证据"],
        "confidence": "low",
        "recommended_status": "needs-rerun",
        **{
            key: False
            for key in (
                "intended_vulnerability",
                "flag_provenance",
                "no_cheat",
                "environment_plausible",
                "reproducible",
                "minimal",
            )
        },
    }
    receipt = submit_structured("judge", tmp_path, args, {"finding_id": "F-1"})
    assert receipt["success"], receipt
    assert (tmp_path / "result.json").read_bytes() == original
    assert receipt["sha256"] == hashlib.sha256((tmp_path / "judge.json").read_bytes()).hexdigest()
    accepted_submissions("judge", tmp_path)


@pytest.mark.parametrize("stage", list(SPECS))
def test_mcp_discovers_current_domain_api_only(stage, tmp_path):
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts/stages/submission.py"
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    response = subprocess.run(
        [sys.executable, str(script), "serve", "--stage", stage, "--root", str(tmp_path)],
        input=request + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    names = {row["name"] for row in json.loads(response.stdout)["result"]["tools"]}
    specific = {spec[0] for spec in SPECS.values()}
    assert names & specific == {SPECS[stage][0]}


def test_environment_submission_keeps_build_operational_metadata(tmp_path):
    (tmp_path / "env-manifest.json").write_text(
        json.dumps({"source": "/source/demo", "commit": "123", "run_script": "/env/run.sh"})
    )
    result = submit_structured(
        "environment",
        tmp_path,
        {
            "env_status": "blocked",
            "reason": "runtime unavailable",
            "summary": "环境受阻",
            "limitations": ["尚无环境"],
        },
        {"project": "demo"},
    )
    assert result["success"]
    data = json.loads((tmp_path / "env-manifest.json").read_text())
    assert data["commit"] == "123"
    assert data["run_script"] == "/env/run.sh"

def test_attack_design_without_image_is_accepted_and_partial_batch_continues(tmp_path):
    task = {"project": "demo", "finding_id": "F-1"}
    result = submit_structured("visual", tmp_path, {
        "design": {"mechanism": {"missing_check": "未验证调用者权限"}},
        "summary": "机制设计", "limitations": ["生图失败，暂无图片"]}, task)
    assert result["success"], result
    file = tmp_path / "scene-F-1.director.json"
    assert file.exists()
    (tmp_path / ".stage-submissions/visual/broken.json").write_text(json.dumps({
        "stage": "visual", "decision": "accepted",
        "artifact": str(tmp_path / "scene-F-2.director.json"), "checked_at": "later",
        "sha256": "bad"}))
    with pytest.raises(ValueError):
        accepted_submissions("visual", tmp_path)
    partial = accepted_submissions("visual", tmp_path, minimum=1, allow_partial=True)
    assert partial["accepted"] == 1
    assert len(partial["excluded"]) == 1


def test_empty_attack_design_and_zero_valid_deliveries_are_rejected(tmp_path):
    result = submit_structured("visual", tmp_path, {
        "design": {}, "summary": "空设计", "limitations": ["无图片"]},
        {"project": "demo", "finding_id": "F-1"})
    assert not result["success"]
    with pytest.raises(ValueError, match="至少 1"):
        accepted_submissions("visual", tmp_path, minimum=1, allow_partial=True)
