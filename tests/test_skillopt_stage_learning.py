from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/stages"))
from learn_round import learn  # noqa: E402
from skill_bank import SkillBank, write  # noqa: E402
from skillopt_adapter import optimize_request  # noqa: E402


def _request(repo: Path, target: str = "verify") -> Path:
    agent = repo / ".claude/agents/verify-agent.md"
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text("# 验证任务\n读取实际证据，保持现有结论枚举，不伪造运行结果。")
    run = repo / "runs/demo/one"
    run.mkdir(parents=True)
    evidence = run / "proof.json"
    evidence.write_text(
        json.dumps({"status": "blocked", "reason": "缺少最小环境"}), encoding="utf-8"
    )
    queue = run / "rsi/skillopt-requests"
    queue.mkdir(parents=True)
    request = {
        "id": "request-001",
        "run_dir": str(run),
        "project": "demo",
        "target_stage": target,
        "scope": "project",
        "problem": "验证阶段把环境缺失写成不确定",
        "suggestions": [
            {
                "type": "add",
                "title": "记录受阻",
                "instruction": "缺少最小能力时记录受阻原因。",
            }
        ],
        "evidence": [str(evidence)],
        "source_stages": ["verify"],
        "source_commit": "abc123",
        "expected_improvement": "减少错误结论",
        "possible_regression": "增加受阻记录",
        "conditions": {},
    }
    path = queue / "request-001.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return path


def _suite(repo: Path) -> Path:
    program = repo / "evaluate.py"
    program.write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "p=Path(os.environ['STAGE_EVAL_OUTPUT'])\n"
        "p.write_text(json.dumps({'valid': True, 'quality': 2 if "
        "os.environ.get('STAGE_SKILL_OVERRIDE') else 1, 'errors': 0}))\n",
        encoding="utf-8",
    )
    suite = repo / "config/stage-evals/verify.json"
    write(
        suite,
        {
            "stage": "verify",
            "metrics": {"quality": "higher", "errors": "lower"},
            "cases": [
                {"id": "wire-case", "project": "demo", "argv": [sys.executable, str(program)]}
            ],
        },
    )
    return suite


def test_request_tool_queues_only_for_learner(tmp_path):
    root = tmp_path / "runs/demo/one"
    root.mkdir(parents=True)
    evidence = root / "proof.json"
    evidence.write_text("{}", encoding="utf-8")
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "request_skillopt_optimization",
            "arguments": {
                "target_stage": "verify",
                "scope": "project",
                "problem": "验证结论缺少受阻原因",
                "suggestions": [{"type": "add", "instruction": "缺少能力时记录受阻。"}],
                "evidence": [str(evidence)],
                "expected_improvement": "更准确",
                "possible_regression": "更多受阻",
            },
        },
    }
    script = ROOT / "scripts/stages/submission.py"
    result = subprocess.run(
        [sys.executable, str(script), "serve", "--stage", "learner", "--root", str(root)],
        input=json.dumps(message) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    queued = json.loads(payload["result"]["content"][0]["text"])
    assert queued["status"] == "queued_skillopt_request"
    requests = list((root / "rsi/skillopt-requests").glob("*.json"))
    assert len(requests) == 1
    request = json.loads(requests[0].read_text())
    assert request["project"] == "demo"
    assert Path(request["evidence"][0]).is_file()
    assert Path(request["evidence"][0]).is_relative_to(root)

    denied = subprocess.run(
        [sys.executable, str(script), "serve", "--stage", "verify", "--root", str(root)],
        input=json.dumps(message) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    assert "error" in json.loads(denied.stdout)


def test_skillopt_result_becomes_candidate_and_uses_existing_release(tmp_path):
    repo = tmp_path / "repo"
    request = _request(repo)
    result = optimize_request(
        request,
        repo=repo,
        project="demo",
        rewrite=lambda base, patch, **kwargs: {
            "reasoning": "测试适配",
            "change_summary": ["记录受阻原因"],
            "new_skill": "# 验证阶段技能\n\n- 缺少最小能力时记录受阻原因。\n",
        },
    )
    assert result["status"] == "candidate"
    bank = SkillBank(repo)
    candidate = bank.candidate(result["candidate_id"])
    assert candidate["provenance"]["target_stage"] == "verify"
    assert candidate["provenance"]["engine"]["entry"].endswith("rewrite_skill_from_suggestions")
    assert not bank.active()
    assert bank.advance("demo")["results"][0]["status"] == "missing_evaluation_suite"
    assert not bank.active()

    suite = _suite(repo)
    evaluation = bank.evaluate(candidate["id"], suite)
    assert evaluation["decision"] == "accepted"
    bank.publish(evaluation["id"])
    assert bank.render("verify", "demo")["versions"][0]["id"] == candidate["id"]
    publication = next((bank.root / "publications").glob("*.json")).stem
    bank.rollback(publication)
    assert not bank.render("verify", "demo")["versions"]


def test_skillopt_empty_or_marked_output_is_not_candidate(tmp_path):
    repo = tmp_path / "repo"
    request = _request(repo)
    empty = optimize_request(
        request,
        repo=repo,
        project="demo",
        rewrite=lambda base, patch, **kwargs: {"new_skill": ""},
    )
    assert empty["status"] == "failed"
    assert not list((repo / "rsi/stage-skills/candidates").glob("*.json"))

    marked = optimize_request(
        request,
        repo=repo,
        project="demo",
        rewrite=lambda base, patch, **kwargs: {"new_skill": "记录 FLAG{0123456789abcdef} 后通过。"},
    )
    assert marked["status"] == "failed"
    assert not list((repo / "rsi/stage-skills/candidates").glob("*.json"))


def test_learning_is_skipped_inside_optimization_or_evaluation(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    run = repo / "runs/demo/one"
    run.mkdir(parents=True)
    monkeypatch.setenv("SKILLOPT_RUN", "1")
    result = learn(run, "demo", repo)
    assert result["status"] == "skipped"
    assert not (run / "rsi/stage-learning-attempts").exists()


def test_learn_round_invokes_adapter_for_queued_request(tmp_path, monkeypatch):
    import learn_round
    monkeypatch.setenv("RSI_SKILLOPT_ENABLED", "1")

    repo = tmp_path / "repo"
    run = repo / "runs/demo/one"
    queue = run / "rsi/skillopt-requests"
    queue.mkdir(parents=True)
    (queue / "request-1.json").write_text("{}", encoding="utf-8")
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        "import json,sys,pathlib\n"
        "pathlib.Path(sys.argv[sys.argv.index('--request')+1]).with_name('called').write_text('1')\n"
        "print(json.dumps({'status':'candidate','candidate_id':'candidate-1'}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(learn_round, "SKILLOPT_ADAPTER", adapter)
    result = learn_round._run_skillopt(run, "demo", repo, "", 30)
    assert result["status"] == "candidate"
    assert result["candidates"] == ["candidate-1"]
    assert (queue / "called").is_file()


def test_project_display_case_maps_to_runtime_owner_without_weakening_cross_project(tmp_path):
    path = _request(tmp_path)
    request = json.loads(path.read_text())
    request["project"] = "Demo"
    path.write_text(json.dumps(request))
    result = optimize_request(
        path,
        repo=tmp_path,
        project="demo",
        rewrite=lambda *a, **k: {
            "new_skill": "# 修正规则\n先读取真实环境证据再判断。",
            "reasoning": "保留项目归属",
        },
    )
    assert result["status"] == "candidate"
    candidate = SkillBank(tmp_path).candidate(result["candidate_id"])
    assert candidate["project"] == "demo"
    request["project"] = "other"
    path.write_text(json.dumps(request))
    import pytest

    with pytest.raises(ValueError, match="项目与当前运行不一致"):
        optimize_request(path, repo=tmp_path, project="demo", rewrite=lambda *a, **k: {})


def test_project_inference_uses_run_owner_not_report_display_name(tmp_path, monkeypatch):
    import skill_bank

    monkeypatch.setattr(skill_bank, "ROOT", tmp_path)
    root = tmp_path / "runs/openmuse/one.meta/node-retries/learner/new/output"
    write(root / "audit-report.json", {"project": "OpenMuse", "findings": []})
    assert skill_bank.infer_project(root) == "openmuse"


def test_optimizer_restores_process_marker_on_failure_and_exception(tmp_path, monkeypatch):
    import os

    monkeypatch.delenv("SKILLOPT_RUN", raising=False)
    repo = tmp_path / "repo"
    request = _request(repo)

    def rewrite(*args, **kwargs):
        assert os.environ["SKILLOPT_RUN"] == "1"
        return {"new_skill": ""}

    result = optimize_request(request, repo=repo, project="demo", rewrite=rewrite)
    assert result["status"] == "failed"
    assert "SKILLOPT_RUN" not in os.environ
    monkeypatch.setenv("SKILLOPT_RUN", "outer")
    with pytest.raises(ValueError):
        optimize_request(tmp_path / "missing.json", repo=repo, project="demo", rewrite=rewrite)
    assert os.environ["SKILLOPT_RUN"] == "outer"


def test_optimizer_reads_real_markdown_and_records_hash(tmp_path):
    request = _request(tmp_path)
    skill = tmp_path / ".claude/skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# 实际技能\n禁止伪造证据")
    agent = tmp_path / ".claude/agents/verify-agent.md"
    agent.write_text("# 实际智能体\n读取 .claude/skills/example/SKILL.md")

    def rewrite(base, patch, **kwargs):
        assert "禁止伪造证据" in base and "实际智能体" in base
        assert "补充规则" in patch["reasoning"]
        return {"new_skill": "# 必要补充\n缺少能力时保留受阻原因。"}

    result = optimize_request(request, repo=tmp_path, project="demo", rewrite=rewrite)
    assert len(result["base_documents"]) == 2
    assert result["change_mode"] == "stage_addendum"
    candidate = SkillBank(tmp_path).candidate(result["candidate_id"])
    from skill_bank import validate_execution_documents

    validate_execution_documents(tmp_path, candidate)
    skill.write_text("# 已变化的技能")
    with pytest.raises(ValueError, match="基线已变化"):
        validate_execution_documents(tmp_path, candidate)


def test_missing_actual_markdown_never_uses_title_only_baseline(tmp_path):
    request = _request(tmp_path)
    (tmp_path / ".claude/agents/verify-agent.md").unlink()
    with pytest.raises(ValueError, match="基线"):
        optimize_request(
            request,
            repo=tmp_path,
            project="demo",
            rewrite=lambda *a, **k: pytest.fail("不得调用优化器"),
        )
