import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/stages"))
from exploration import feedback, plan  # noqa: E402
from skill_bank import SkillBank, write  # noqa: E402


def setup_run(tmp_path, name="one"):
    source = tmp_path / "runs/demo" / name
    output = Path(str(source) + ".meta/output")
    source.mkdir(parents=True)
    output.mkdir(parents=True)
    write(
        source / "task-artifacts/read-coverage/summary.json",
        {"files": [{"file": "app.py", "file_sha256": "abc", "kind": "read"}]},
    )
    write(
        source / "task-artifacts/coverage-ledger.json",
        {
            "source_version": "commit",
            "entries": [
                {
                    "area": "auth",
                    "view": "guard",
                    "hypothesis": "check auth",
                    "risk": "high",
                    "evidence": ["file:10 guard"],
                    "status": "needs_evidence",
                }
            ],
        },
    )
    return source, output


def test_reward_dedup_and_energy(tmp_path):
    source, output = setup_run(tmp_path)
    reports = [{"semantic_id": "bug-one", "report_key": "first"}] * 2
    result = feedback(tmp_path, source, output, "demo", reports=reports)
    assert result["reward"] == 11.1
    assert len(result["verified_reports"]) == 1
    assert feedback(tmp_path, source, output, "demo", reports=reports) == result
    assert plan(tmp_path, "demo")["tasks"][0]["energy"] == 3
    source2, output2 = setup_run(tmp_path, "two")
    result2 = feedback(tmp_path, source2, output2, "demo", reports=reports)
    assert result2["reward"] == 0
    assert not result2["interesting"]


def test_arbitrary_intent_rename_is_not_reward(tmp_path):
    source, output = setup_run(tmp_path)
    feedback(tmp_path, source, output, "demo", reports=[])
    source2, output2 = setup_run(tmp_path, "two")
    file = source2 / "task-artifacts/coverage-ledger.json"
    data = json.loads(file.read_text())
    data["entries"][0]["hypothesis"] = "a renamed intention"
    write(file, data)
    assert feedback(tmp_path, source2, output2, "demo", reports=[])["reward"] == 0


def test_trial_is_project_local_pinned_and_does_not_publish(tmp_path, monkeypatch):
    source, output = setup_run(tmp_path)
    agent = tmp_path / ".claude/agents/security-orchestrator.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("# existing audit rules")
    bank = SkillBank(tmp_path)
    candidate = bank.propose(
        "orchestrator",
        "demo",
        "general",
        "Follow callers for guard checks",
        [str(agent)],
        provenance={"change_kind": "method"},
    )
    feedback(tmp_path, source, output, "demo", reports=[])
    result = feedback(tmp_path, source, output, "demo", [candidate["id"]], reports=[])
    assert result["status"] == "trial_selected" and result["interesting"]
    assert not bank.active()
    assert "Follow callers" in bank.render("orchestrator", "demo")["text"]
    assert not bank.render("orchestrator", "another")["text"]
    assert not bank.render("verify", "demo")["text"]
    baseline = tmp_path / "baseline.json"
    write(baseline, {})
    monkeypatch.setenv("STAGE_SKILL_BASELINE", str(baseline))
    assert not bank.render("orchestrator", "demo")["text"]
    write(baseline, {"trial/orchestrator/demo": candidate["id"]})
    assert bank.render("orchestrator", "demo")["text"]
    agent.write_text("# changed baseline")
    assert not bank.render("orchestrator", "demo")["text"]


def test_trial_is_withdrawn_on_failed_natural_run(tmp_path):
    source, output = setup_run(tmp_path)
    agent = tmp_path / ".claude/agents/security-orchestrator.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("# existing audit rules")
    bank = SkillBank(tmp_path)
    cid = bank.propose(
        "orchestrator",
        "demo",
        "project",
        "Check callers",
        [str(agent)],
        provenance={"change_kind": "method"},
    )["id"]
    feedback(tmp_path, source, output, "demo", [cid], reports=[])
    source2, output2 = setup_run(tmp_path, "two")
    write(source2 / "task-artifacts/exploration-plan.json", plan(tmp_path, "demo"))
    write(Path(str(source2) + ".meta/status.json"), {"state": "failed"})
    result = feedback(tmp_path, source2, output2, "demo", reports=[])
    assert not result["trial"]
    assert not bank.render("orchestrator", "demo")["text"]
    assert not bank.active()


def test_non_method_candidates_do_not_enter_probation(tmp_path):
    source, output = setup_run(tmp_path)
    bank = SkillBank(tmp_path)
    evidence = source / "proof.txt"
    evidence.write_text("runtime error")
    cid = bank.propose(
        "orchestrator",
        "demo",
        "project",
        "Change executor code",
        [str(evidence)],
        provenance={"change_kind": "code"},
    )["id"]
    assert not feedback(tmp_path, source, output, "demo", [cid], reports=[])["trial"]


def test_skillopt_optional_by_default(tmp_path, monkeypatch):
    from learn_round import _run_skillopt

    monkeypatch.delenv("RSI_SKILLOPT_ENABLED", raising=False)
    assert _run_skillopt(tmp_path, "demo", tmp_path, "", 1)["status"] == "optional_disabled"
