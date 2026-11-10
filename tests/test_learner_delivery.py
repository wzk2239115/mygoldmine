import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))
from submission import submit, accepted_submissions
from learn_round import learning_delivery


def result(root, status="no_changes"):
    evidence = root / "rsi/stage-feedback/index.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("{}")
    return {
        "schema_version": 1, "project": "demo", "status": status,
        "conclusions": [{"stage": "orchestrator", "category": "no_change",
                         "reason": "已有要求覆盖本次反馈", "evidence": [str(evidence)],
                         "next_action": "等待下一轮真实反馈"}],
        "proposal_ids": [], "limitations": [],
    }


def test_learning_producer_can_repair_and_resubmit(tmp_path):
    file = tmp_path / "rsi/learning-result.json"
    data = result(tmp_path)
    file.write_text("{}")
    args = {"artifact": str(file), "summary": "学习结束", "limitations": []}
    assert submit("learner", tmp_path, args)["decision"] == "needs_revision"
    file.write_text(json.dumps(data))
    assert submit("learner", tmp_path, args)["decision"] == "accepted"
    assert learning_delivery(tmp_path)["accepted"] == 1
    assert len(list((tmp_path / ".stage-submissions/learner").glob("*.json"))) == 2
    evidence = tmp_path / "rsi/stage-feedback/index.json"
    evidence.write_text("changed")
    with pytest.raises(ValueError, match="内容已改变"):
        learning_delivery(tmp_path)


def test_learning_rejects_fabricated_proposal_and_allows_honest_blocked(tmp_path):
    file = tmp_path / "rsi/learning-result.json"
    data = result(tmp_path, "completed")
    data["proposal_ids"] = ["invented"]
    file.write_text(json.dumps(data))
    args = {"artifact": str(file), "summary": "学习结束", "limitations": []}
    assert submit("learner", tmp_path, args)["decision"] == "needs_revision"
    data.update(status="blocked", proposal_ids=[], limitations=["证据不足"])
    file.write_text(json.dumps(data))
    assert submit("learner", tmp_path, args)["decision"] == "accepted"


def test_other_learning_file_cannot_substitute_for_final_delivery(tmp_path):
    data = result(tmp_path)
    file = tmp_path / "rsi/other.json"
    file.write_text(json.dumps(data))
    assert submit("learner", tmp_path, {
        "artifact": str(file), "summary": "学习结束", "limitations": [],
    })["decision"] == "accepted"
    with pytest.raises(ValueError, match="最终产物"):
        learning_delivery(tmp_path)


@pytest.mark.parametrize("deliver", [False, True])
def test_launcher_requires_agent_delivery_not_just_zero_exit(tmp_path, monkeypatch, deliver):
    import subprocess
    from types import SimpleNamespace
    import learn_round
    monkeypatch.setattr(learn_round, "SkillBank", lambda _: SimpleNamespace(
        feedback=lambda *a: [], render=lambda *a, **kw: {"versions": []}))
    monkeypatch.setattr(learn_round, "_run_skillopt", lambda *a, **kw: {
        "status": "optional_disabled", "results": [], "candidates": []})

    def agent(command, **kwargs):
        context = command[command.index("--append-system-prompt") + 1]
        assert "submit_stage_result" in context
        assert "--mcp-config" in command
        if deliver:
            data = result(tmp_path)
            file = tmp_path / "rsi/learning-result.json"
            file.write_text(json.dumps(data))
            receipt = submit("learner", tmp_path, {
                "artifact": str(file), "summary": "分析结束", "limitations": []})
            assert receipt["decision"] == "accepted"
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(learn_round, "run_session", agent)
    summary = learn_round.learn(tmp_path, "demo")
    assert summary["exit_code"] == (0 if deliver else 1)
    if not deliver:
        assert not (tmp_path / ".stage-submissions").exists()
