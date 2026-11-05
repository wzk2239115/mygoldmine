import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "stages"))
from skill_bank import SkillBank  # noqa: E402


def test_orchestrator_references_new_audit_skills_and_filter():
    text = (ROOT / ".claude/agents/security-orchestrator.md").read_text(encoding="utf-8")
    for name in ("audit-coverage-planner", "audit-hypothesis-tracer", "audit-review-planner"):
        assert name in text
    assert "以 `-planner` 结尾" in text
    assert "以 `-tracer` 结尾" in text


def test_new_skills_have_required_frontmatter_and_references():
    for name in ("audit-coverage-planner", "audit-hypothesis-tracer", "audit-review-planner"):
        skill = ROOT / ".claude/skills" / name
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "description:" in text
        assert list((skill / "references").glob("*.md"))


def test_coverage_hook_is_registered_and_tasks_edit_is_covered():
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    pre = settings["hooks"]["PreToolUse"]
    assert any(item.get("matcher") == "Write|Edit" for item in pre)
    commands = [
        hook["command"]
        for item in settings["hooks"]["PreToolUse"] + settings["hooks"]["Stop"]
        for hook in item["hooks"]
    ]
    assert any("coverage-ledger-guard.py" in command for command in commands)
    compact = [
        hook["command"] for item in settings["hooks"]["PreCompact"] for hook in item["hooks"]
    ]
    assert any("coverage-ledger-guard.py" in command for command in compact)


def test_stage_feedback_includes_coverage_artifacts(tmp_path):
    repo = tmp_path / "repo"
    run = repo / "runs/demo/one"
    artifacts = run / "task-artifacts"
    artifacts.mkdir(parents=True)
    (run / "task-state").mkdir()
    (run / "report-quality.json").write_text(
        json.dumps({"valid": True, "incomplete": 0}), encoding="utf-8"
    )
    (run / "task-state/security-orchestrator-tasks.json").write_text(
        json.dumps({"tasks": []}), encoding="utf-8"
    )
    (artifacts / "coverage-ledger.json").write_text(
        json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8"
    )
    (artifacts / "coverage-plan.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")
    (artifacts / "review-plan.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")
    records = SkillBank(repo).feedback(run, "demo")
    orchestrator = next(item for item in records if item["stage"] == "orchestrator")
    evidence = {item["path"] for item in orchestrator["evidence"]}
    assert "runs/demo/one/task-artifacts/coverage-ledger.json" in evidence
    assert "runs/demo/one/task-artifacts/coverage-plan.json" in evidence
    assert "runs/demo/one/task-artifacts/review-plan.json" in evidence


def test_progress_feedback_enters_existing_candidate_queue(tmp_path):
    repo = tmp_path / "repo"
    run = repo / "runs/demo/one"
    proposals = run / ".stage-skill-proposals"
    proposals.mkdir(parents=True)
    (run / "task-artifacts").mkdir()
    evidence = run / "task-artifacts/coverage-ledger.json"
    evidence.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    request = {
        "id": "proposal-001",
        "stage": "orchestrator",
        "project": "demo",
        "scope": "project",
        "content": "当高风险入口仍为未被检查时，下一批任务优先安排假设追踪。",
        "evidence": [str(evidence)],
        "conditions": {"commit": "abc123"},
    }
    (proposals / "proposal-001.json").write_text(json.dumps(request), encoding="utf-8")
    bank = SkillBank(repo)
    records = bank.feedback(run, "demo")
    imported = json.loads((run / "rsi/stage-learning-imports.json").read_text(encoding="utf-8"))
    assert imported["imported"]
    candidates = list((repo / "rsi/stage-skills/candidates").glob("*.json"))
    assert candidates
    candidate = json.loads(candidates[0].read_text(encoding="utf-8"))
    assert candidate["stage"] == "orchestrator"
    assert candidate["evidence"][0]["path"].endswith("coverage-ledger.json")
    assert any(item["stage"] == "orchestrator" for item in records)
