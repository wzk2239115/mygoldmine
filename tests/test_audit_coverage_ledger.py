import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit" / "coverage_ledger.py"
HOOK = ROOT / ".claude" / "hooks" / "coverage-ledger-guard.py"


def ledger(entries=None):
    return {
        "schema_version": 1,
        "project": "demo",
        "source_version": "abc123",
        "limitations": ["只审计已识别入口，没有全仓库分母"],
        "entries": entries
        or [
            {
                "id": "COV-001",
                "area": "pkg/a.py:10",
                "view": "entry",
                "risk": "high",
                "hypothesis": "配置可以到达执行入口",
                "status": "unchecked",
                "evidence": [],
                "missing_evidence": ["调用方", "防护条件"],
                "next_action": "追踪调用链",
                "history": [],
                "skill_versions": [{"name": "audit-coverage-planner", "sha256": "a" * 64}],
                "conclusion": "",
                "limitations": ["尚未读取调用方"],
            },
            {
                "id": "COV-002",
                "area": "pkg/b.py:20",
                "view": "dataflow",
                "risk": "critical",
                "hypothesis": "外部输入进入危险操作",
                "status": "analyzed",
                "evidence": ["pkg/b.py:20"],
                "missing_evidence": ["真实入口"],
                "next_action": "补入口证据",
                "history": [],
                "skill_versions": [{"name": "audit-hypothesis-tracer", "sha256": "b" * 64}],
                "conclusion": "尚未确认可达",
                "limitations": ["缺少入口"],
            },
        ],
    }


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def test_validate_and_plan_order(tmp_path):
    path = tmp_path / "coverage-ledger.json"
    path.write_text(json.dumps(ledger()), encoding="utf-8")
    assert (
        run([sys.executable, str(SCRIPT), "validate", "--ledger", str(path)], tmp_path).returncode
        == 0
    )
    out = tmp_path / "coverage-plan.json"
    completed = run(
        [sys.executable, str(SCRIPT), "plan", "--ledger", str(path), "--out", str(out)], tmp_path
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(out.read_text())
    assert [item["coverage_id"] for item in plan["tasks"]] == ["COV-002", "COV-001"]
    assert plan["signals"]["uncovered_high_risk"] == 1
    assert "没有完整分母" in plan["signals"]["scope_note"]
    assert out.with_suffix(".md").exists()


def test_review_respects_budget_and_conditions(tmp_path):
    data = ledger()
    data["entries"][0]["status"] = "needs_evidence"
    data["entries"][0]["evidence"] = ["pkg/a.py:10"]
    data["entries"][0]["review_conditions"] = ["新调用方"]
    data["entries"][1]["status"] = "blocked"
    data["entries"][1]["limitations"] = ["环境不可用"]
    path = tmp_path / "coverage-ledger.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "review-plan.json"
    completed = run(
        [
            sys.executable,
            str(SCRIPT),
            "review",
            "--ledger",
            str(path),
            "--out",
            str(out),
            "--budget",
            "1",
            "--seed",
            "demo",
        ],
        tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(out.read_text())
    assert plan["selected"] == ["COV-001"]
    assert plan["tasks"][0]["reason"] == "新条件触发复审"


def test_invalid_ledger_has_specific_feedback(tmp_path):
    data = ledger()
    data["entries"][0]["next_action"] = ""
    path = tmp_path / "coverage-ledger.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    completed = run([sys.executable, str(SCRIPT), "validate", "--ledger", str(path)], tmp_path)
    assert completed.returncode == 2
    assert "next_action" in completed.stderr


def test_pre_tool_hook_blocks_invalid_ledger_write(tmp_path):
    (tmp_path / ".workspace/findings").mkdir(parents=True)
    path = tmp_path / ".workspace/findings/coverage-ledger.json"
    data = ledger()
    data["entries"][0]["status"] = "needs_evidence"
    data["entries"][0]["missing_evidence"] = []
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": json.dumps(data)},
    }
    completed = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp_path,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 2
    assert "missing_evidence" in completed.stderr


def test_stop_hook_saves_progress_and_allows_after_one_retry(tmp_path):
    findings = tmp_path / ".workspace/findings"
    findings.mkdir(parents=True)
    path = findings / "coverage-ledger.json"
    data = ledger()
    data["entries"][0]["next_action"] = ""
    path.write_text(json.dumps(data), encoding="utf-8")
    payload = {"hook_event_name": "Stop", "cwd": str(tmp_path)}
    first = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp_path,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    assert first.returncode == 2
    assert (findings / "coverage-progress.md").exists()
    second = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp_path,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    assert second.returncode == 0
    assert "允许结束" in second.stderr


def test_stop_hook_respects_pause_marker(tmp_path):
    findings = tmp_path / ".workspace/findings"
    findings.mkdir(parents=True)
    (findings / "coverage-ledger.json").write_text(json.dumps(ledger()), encoding="utf-8")
    (findings / ".coverage-paused").write_text("budget exhausted\n", encoding="utf-8")
    payload = {"hook_event_name": "Stop", "cwd": str(tmp_path)}
    completed = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp_path,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0


def test_pre_compact_hook_saves_progress_without_blocking(tmp_path):
    findings = tmp_path / ".workspace/findings"
    findings.mkdir(parents=True)
    (findings / "coverage-ledger.json").write_text("{}", encoding="utf-8")
    payload = {"hook_event_name": "PreCompact", "cwd": str(tmp_path)}
    completed = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp_path,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0
    assert (findings / "coverage-progress.md").exists()
