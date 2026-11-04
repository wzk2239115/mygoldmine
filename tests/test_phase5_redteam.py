import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "redteam" / "phase5_redteam.sh"

FAKE_BATCH = '''#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--report", default="")
parser.add_argument("--candidates", required=True)
parser.add_argument("--out-dir", required=True)
parser.add_argument("--model", default="")
parser.add_argument("--base-url", default="")
parser.add_argument("--api-key", default="")
parser.add_argument("--build-timeout", type=int, default=0)
parser.add_argument("--agent-timeout", type=int, default=0)
parser.add_argument("--judge-timeout", type=int, default=0)
parser.add_argument("--judge-claude", default="")
parser.add_argument("--judge-claude-model", default="")
args = parser.parse_args()

marker = os.environ.get("FAKE_BATCH_MARKER")
if marker:
    Path(marker).write_text("called\\n", encoding="utf-8")

out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "invocation.json").write_text(json.dumps(vars(args)), encoding="utf-8")
candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8")).get("candidates", [])
statuses = ["blocked", "judge_rejected", "judge_approved"]
results = []
for index, candidate in enumerate(candidates):
    results.append({
        "project": candidate["project"],
        "id": candidate["id"],
        "key": candidate["project"] + ":" + candidate["id"],
        "status": statuses[index % len(statuses)],
    })
summary = {"generated_at": "fixture", "model": args.model, "results": results}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"batch": str(out), "counts": {}}))
'''

FAKE_BUILD_STATE = '''#!/usr/bin/env python3
import os
from pathlib import Path

marker = os.environ.get("FAKE_BUILD_STATE_MARKER")
if marker:
    Path(marker).write_text("ran\\n", encoding="utf-8")
raise SystemExit(int(os.environ.get("FAKE_BUILD_STATE_RC", "0")))
'''


def write_script(path, body):
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def fixtures(tmp_path):
    batch = write_script(tmp_path / "fake_batch.py", FAKE_BATCH)
    build_state = write_script(tmp_path / "fake_build_state.py", FAKE_BUILD_STATE)
    batch_marker = tmp_path / "batch-called"
    build_marker = tmp_path / "build-state-called"
    env = os.environ.copy()
    env.update({
        "PYTHON": sys.executable,
        "REDTEAM_BATCH_PY": str(batch),
        "REDTEAM_BUILD_STATE_PY": str(build_state),
        "FAKE_BATCH_MARKER": str(batch_marker),
        "FAKE_BUILD_STATE_MARKER": str(build_marker),
    })
    return env, batch_marker, build_marker


def write_report(tmp_path, findings, key="findings", run_name="run-A"):
    run_dir = tmp_path / "runs" / "proj" / run_name
    run_dir.mkdir(parents=True)
    (run_dir / "audit-report.json").write_text(
        json.dumps({key: findings}, ensure_ascii=False), encoding="utf-8"
    )
    return run_dir


def invoke(tmp_path, run_dir, *extra):
    command = [
        "bash", str(WRAPPER),
        "--project", "proj",
        "--run-dir", str(run_dir),
        *extra,
    ]
    return subprocess.run(command, capture_output=True, text=True, timeout=60)


def test_wrapper_filters_caps_and_preserves_batch_statuses(tmp_path):
    run_dir = write_report(tmp_path, [
        {"id": "VULN-001", "severity": "critical"},
        {"id": "VULN-002", "severity": "low"},
        {"id": "VULN-003", "severity": "high"},
        {"id": "VULN-004", "severity": "medium"},
        {"id": "VULN-005", "severity": "critical"},
        {"id": "VULN-006", "severity": "high"},
    ])
    env, batch_marker, build_marker = fixtures(tmp_path)
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            "bash", str(WRAPPER),
            "--project", "proj",
            "--run-dir", str(run_dir),
            "--max", "3",
            "--severity", "critical,high",
            "--model", "test-model",
            "--base-url", "http://example.test/v1",
            "--api-key", "test-key",
            "--build-timeout", "11",
            "--agent-timeout", "22",
            "--judge-timeout", "33",
            "--judge-claude", "/bin/true",
            "--judge-claude-model", "judge-model",
            "--output", str(output),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert completed.returncode == 0, completed.stderr

    candidates = json.loads((output / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    assert [item["id"] for item in candidates] == ["VULN-001", "VULN-003", "VULN-005"]
    assert all(item["project"] == "proj" and item["run_id"] == "run-A" for item in candidates)

    invocation = json.loads((output / "batch" / "invocation.json").read_text(encoding="utf-8"))
    assert invocation["report"] == str(run_dir / "audit-report.json")
    assert invocation["candidates"] == str(output / "candidates.json")
    assert Path(invocation["out_dir"]) == output / "batch"
    assert invocation["model"] == "test-model"
    assert invocation["base_url"] == "http://example.test/v1"
    assert invocation["api_key"] == "test-key"
    assert invocation["build_timeout"] == 11
    assert invocation["agent_timeout"] == 22
    assert invocation["judge_timeout"] == 33
    assert invocation["judge_claude"] == "/bin/true"
    assert invocation["judge_claude_model"] == "judge-model"

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "partial"
    assert summary["completed"] is False
    assert summary["counts"] == {
        "blocked": 1,
        "judge_rejected": 1,
        "judge_approved": 1,
    }
    statuses = {item["id"]: item["status"] for item in summary["results"]}
    assert statuses == {
        "VULN-001": "blocked",
        "VULN-003": "judge_rejected",
        "VULN-005": "judge_approved",
    }
    markdown = (output / "summary.md").read_text(encoding="utf-8")
    assert "VULN-001" in markdown
    assert "judge_rejected" in markdown
    assert summary["build_state"] == {
        "attempted": True,
        "returncode": 0,
        "log": str(output / "build-state.log"),
    }
    assert batch_marker.exists()
    assert build_marker.exists()


def test_wrapper_reads_vulnerabilities_and_uses_default_severity(tmp_path):
    run_dir = write_report(
        tmp_path,
        [{"id": "VULN-100", "severity": "high"}, {"id": "VULN-101", "severity": "low"}],
        key="vulnerabilities",
    )
    env, _, _ = fixtures(tmp_path)
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            "bash", str(WRAPPER),
            "--project", "proj",
            "--run-dir", str(run_dir),
            "--max", "5",
            "--judge-claude", "/bin/true",
            "--output", str(output),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert completed.returncode == 0, completed.stderr
    candidates = json.loads((output / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    assert [item["id"] for item in candidates] == ["VULN-100"]


@pytest.mark.parametrize("case", ["missing", "invalid", "wrong_type"])
def test_wrapper_rejects_malformed_or_missing_report(tmp_path, case):
    run_dir = tmp_path / "runs" / "proj" / "run-A"
    run_dir.mkdir(parents=True)
    if case == "invalid":
        (run_dir / "audit-report.json").write_text("{not json", encoding="utf-8")
    elif case == "wrong_type":
        (run_dir / "audit-report.json").write_text(
            json.dumps({"findings": "not-a-list"}), encoding="utf-8"
        )
    env, batch_marker, _ = fixtures(tmp_path)
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            "bash", str(WRAPPER),
            "--project", "proj",
            "--run-dir", str(run_dir),
            "--judge-claude", "/bin/true",
            "--output", str(output),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert completed.returncode == 3
    assert not batch_marker.exists()
    assert not (output / "summary.json").exists()


def test_wrapper_no_matching_findings_writes_summary_without_batch(tmp_path):
    run_dir = write_report(tmp_path, [
        {"id": "LOW-001", "severity": "low"},
        {"id": "MED-001", "severity": "medium"},
    ])
    env, batch_marker, build_marker = fixtures(tmp_path)
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            "bash", str(WRAPPER),
            "--project", "proj",
            "--run-dir", str(run_dir),
            "--output", str(output),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert completed.returncode == 0, completed.stderr
    candidates = json.loads((output / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    assert candidates == []
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "no_findings"
    assert summary["completed"] is True
    assert summary["results"] == []
    assert summary["counts"] == {}
    assert summary["batch"]["returncode"] is None
    assert summary["build_state"]["attempted"] is False
    markdown = (output / "summary.md").read_text(encoding="utf-8")
    assert "batch was not run" in markdown
    assert not batch_marker.exists()
    assert not build_marker.exists()


def test_batch_out_dir_and_judge_options_are_forwarded(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "scripts" / "redteam"))
    import batch as batch_module

    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps({"candidates": [{"project": "project", "id": "F-1", "run_id": "r1"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(batch_module, "ROOT", tmp_path)
    monkeypatch.setattr(batch_module, "BATCH_ROOT", tmp_path / "batches")
    occurrence_id = "project/r1/F-1"
    ledger = {
        "occurrences": {occurrence_id: {"occurrence_id": occurrence_id, "run_id": "r1"}},
        "findings": {"sem_fixture": {"occurrence_ids": [occurrence_id]}},
        "indexes": {
            "legacy_to_semantics": {"project:F-1": ["sem_fixture"]},
            "legacy_to_occurrences": {"project:F-1": [occurrence_id]},
        },
    }
    monkeypatch.setattr(batch_module.base.finding_ledger, "build_ledger", lambda: ledger)
    monkeypatch.setattr(batch_module.base, "latest_findings", lambda _ledger: {
        occurrence_id: {"raw": {"id": "F-1", "title": "fixture"}}
    })
    scenario = tmp_path / "scenario.json"
    scenario.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(batch_module, "scenario_path", lambda *_: scenario)
    monkeypatch.setattr(batch_module, "resolve_scenario", lambda *_: (scenario, {}))

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(batch_module.subprocess, "run", fake_run)
    out_dir = tmp_path / "exact-out"
    monkeypatch.setattr(sys, "argv", [
        "batch.py",
        "--candidates", str(candidates),
        "--out-dir", str(out_dir),
        "--judge-claude", "/bin/fake-judge",
        "--judge-claude-model", "judge-model",
    ])
    assert batch_module.main() == 0
    assert (out_dir / "summary.json").exists()
    assert not (tmp_path / "batches").exists()
    judge_commands = [command for command in commands if "judge.py" in command[1]]
    assert len(judge_commands) == 1
    assert judge_commands[0][judge_commands[0].index("--claude") + 1] == "/bin/fake-judge"
    assert judge_commands[0][judge_commands[0].index("--claude-model") + 1] == "judge-model"
    capsys.readouterr()


def test_wrapper_finding_id_filter_selects_only_requested_candidate(tmp_path):
    run_dir = write_report(tmp_path, [
        {"id": "VULN-001", "severity": "critical"},
        {"id": "VULN-002", "severity": "high"},
    ])
    env, _, _ = fixtures(tmp_path)
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            "bash", str(WRAPPER),
            "--project", "proj",
            "--run-dir", str(run_dir),
            "--finding-id", "VULN-002",
            "--judge-claude", "/bin/true",
            "--output", str(output),
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert completed.returncode == 0, completed.stderr
    candidates = json.loads((output / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    assert [item["id"] for item in candidates] == ["VULN-002"]


def test_wrapper_all_candidates_blocked_is_not_completed(tmp_path):
    run_dir = write_report(tmp_path, [{'id': 'F-1', 'severity': 'high'}])
    env, _, _ = fixtures(tmp_path)
    output = tmp_path / 'out'
    result = subprocess.run(['bash', str(WRAPPER), '--project', 'proj',
                             '--run-dir', str(run_dir), '--output', str(output)],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['status'] == 'blocked'
    assert summary['completed'] is False
