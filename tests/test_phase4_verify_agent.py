from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE4 = REPO_ROOT / "scripts" / "verify" / "phase4_verify_agent.sh"


def _write_executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _fake_report(tmp_path: Path) -> Path:
    run_dir = tmp_path / "runs" / "demo" / "20260101T000000Z"
    run_dir.mkdir(parents=True)
    report = {
        "findings": [
            {
                "id": "F-high",
                "title": "high severity finding",
                "severity": "high",
                "file": "app.py",
                "description": "benign test finding",
            },
            {
                "id": "F-low",
                "title": "low severity finding",
                "severity": "low",
                "file": "app.py",
            },
            {
                "id": "F-critical",
                "title": "critical severity finding",
                "severity": "critical",
                "file": "server.py",
            },
        ]
    }
    (run_dir / "audit-report.json").write_text(json.dumps(report), encoding="utf-8")
    return run_dir


def _fake_claude(tmp_path: Path, *, write_harness: bool = True) -> Path:
    if write_harness:
        body = """
sid="$PHASE4_SAFE_ID"
hdir="$PHASE4_HARNESS_DIR"
mkdir -p "$hdir"
cat > "$hdir/harness.sh" <<'HARNESS'
#!/usr/bin/env bash
set -eu
printf 'benign marker\\n'
exit 0
HARNESS
chmod +x "$hdir/harness.sh"
exit 0
"""
    else:
        body = "\nexit 0\n"
    return _write_executable(
        tmp_path / "fake-claude.sh",
        """#!/usr/bin/env bash
set -eu
{
  echo "=== CALL ==="
  printf 'ARG:%s\\n' "$@"
} >> "$PHASE4_TEST_CLAUDE_CAPTURE"
"""
        + body,
    )


def _fake_runner(tmp_path: Path) -> Path:
    return _write_executable(
        tmp_path / "fake-runner.sh",
        """#!/usr/bin/env bash
set -eu
run_dir=""
finding=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-dir) run_dir="$2"; shift ;;
    --finding) finding="$2"; shift ;;
    --harness) harness="$2"; shift ;;
    --network) network="$2"; shift ;;
    --timeout) timeout="$2"; shift ;;
    --project) project="$2"; shift ;;
    --image) image="$2"; shift ;;
    --source) source="$2"; shift ;;
  esac
  shift
done
printf 'run_dir=%s\\n' "$run_dir" >> "$PHASE4_TEST_RUNNER_CAPTURE"
printf 'finding=%s\\n' "$finding" >> "$PHASE4_TEST_RUNNER_CAPTURE"
printf 'harness=%s\\n' "$harness" >> "$PHASE4_TEST_RUNNER_CAPTURE"
printf 'network=%s\\n' "$network" >> "$PHASE4_TEST_RUNNER_CAPTURE"
printf 'timeout=%s\\n' "$timeout" >> "$PHASE4_TEST_RUNNER_CAPTURE"
test -f "$harness"
mkdir -p "$run_dir/evidence"
printf 'benign evidence\\n' > "$run_dir/evidence/fake.log"
jq -n --arg run_dir "$run_dir" --arg finding "$finding" '{
  schema_version: "1",
  project: "demo",
  finding_id: ($finding | split("/") | .[-2]),
  verdict: "confirmed",
  reason: "fake runner produced runtime evidence",
  evidence: ["fake.log"],
  evidence_class: "runtime",
  network: "none",
  run_dir: $run_dir
}' > "$run_dir/verify-report.json"
printf '# fake report\\n' > "$run_dir/verify-report.md"
exit 0
""",
    )


def _run_phase4(
    tmp_path: Path,
    run_dir: Path,
    *,
    claude_bin: Path | str,
    runner: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    (source / "app.py").write_text("print('hello')\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "VERIFY_RUNNER": str(runner),
            "PHASE4_TEST_CLAUDE_CAPTURE": str(tmp_path / "claude.capture"),
            "PHASE4_TEST_RUNNER_CAPTURE": str(tmp_path / "runner.capture"),
        }
    )
    args = [
        "bash",
        str(PHASE4),
        "--project",
        "demo",
        "--run-dir",
        str(run_dir),
        "--image",
        "fake:demo",
        "--source",
        str(source),
        "--max",
        "10",
        "--severity",
        "critical,high",
        "--timeout",
        "30",
        "--agent-timeout",
        "30",
        "--claude-bin",
        str(claude_bin),
        "--model",
        "360-proxy/deepseek/deepseek-v4.1-flash",
        "--output",
        str(tmp_path / "verify-out"),
    ]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(
        args,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_phase4_invokes_verify_agent_and_real_runner(tmp_path: Path) -> None:
    run_dir = _fake_report(tmp_path)
    claude = _fake_claude(tmp_path, write_harness=True)
    runner = _fake_runner(tmp_path)

    result = _run_phase4(tmp_path, run_dir, claude_bin=claude, runner=runner)

    assert result.returncode == 0, result.stderr
    out = tmp_path / "verify-out"

    claude_capture = (tmp_path / "claude.capture").read_text(encoding="utf-8")
    assert "ARG:--agent" in claude_capture
    assert "ARG:verify-agent" in claude_capture
    assert "ARG:--permission-mode=bypassPermissions" in claude_capture
    assert "ARG:--disallowed-tools" in claude_capture
    assert "ARG:WebSearch,WebFetch" in claude_capture
    assert "ARG:--model" in claude_capture
    assert "ARG:deepseek/deepseek-v4.1-flash" in claude_capture
    assert "360-proxy/" not in claude_capture
    assert "finding: " in claude_capture
    assert str(out / "inputs" / "F-high" / "finding.json") in claude_capture
    assert "run_verify.sh" in claude_capture or "fake-runner.sh" in claude_capture

    runner_capture = (tmp_path / "runner.capture").read_text(encoding="utf-8")
    assert "network=none" in runner_capture
    assert f"run_dir={out / 'F-high'}" in runner_capture
    assert f"run_dir={out / 'F-critical'}" in runner_capture
    assert f"finding={out / 'inputs' / 'F-high' / 'finding.json'}" in runner_capture

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["selected"] == 2
    assert summary["processed"] == 2
    assert summary["counts"] == {"confirmed": 2}
    assert [f["finding_id"] for f in summary["findings"]] == ["F-high", "F-critical"]
    assert all(f["agent_return_code"] == 0 for f in summary["findings"])
    assert all(f["runner_return_code"] == 0 for f in summary["findings"])
    assert (out / "summary.md").exists()

    assert (out / "inputs" / "F-high" / "finding.json").exists()
    assert (out / "inputs" / "F-critical" / "finding.json").exists()
    assert not (out / "inputs" / "F-low").exists()
    finding = json.loads((out / "inputs" / "F-high" / "finding.json").read_text(encoding="utf-8"))
    assert finding["id"] == "F-high"


def test_phase4_missing_claude_exits_4_without_confirmed_output(tmp_path: Path) -> None:
    run_dir = _fake_report(tmp_path)
    runner = _fake_runner(tmp_path)

    result = _run_phase4(
        tmp_path,
        run_dir,
        claude_bin="/definitely/missing/claude",
        runner=runner,
    )

    assert result.returncode == 4, result.stderr
    assert "claude" in result.stderr.lower()
    out = tmp_path / "verify-out"
    assert not (out / "summary.json").exists()
    assert not (out / "F-high" / "verify-report.json").exists()


def test_phase4_missing_harness_is_not_confirmed(tmp_path: Path) -> None:
    run_dir = _fake_report(tmp_path)
    claude = _fake_claude(tmp_path, write_harness=False)
    runner = _fake_runner(tmp_path)

    result = _run_phase4(tmp_path, run_dir, claude_bin=claude, runner=runner)

    assert result.returncode == 0, result.stderr
    out = tmp_path / "verify-out"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["selected"] == 2
    assert summary["processed"] == 2
    assert summary["counts"].get("confirmed", 0) == 0
    verdicts = {f["verdict"] for f in summary["findings"]}
    assert verdicts <= {"blocked", "inconclusive"}
    assert all(f["status"] == "agent_no_harness" for f in summary["findings"])
    assert not (tmp_path / "runner.capture").exists()

    for finding in summary["findings"]:
        report = json.loads(Path(finding["report_path"]).read_text(encoding="utf-8"))
        assert report["verdict"] in {"blocked", "inconclusive"}
        assert report["verdict"] != "confirmed"
        assert report["synthesized"] is True


def test_phase4_supports_vulnerabilities_and_records_malformed(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "demo" / "20260101T000000Z"
    run_dir.mkdir(parents=True)
    report = {
        "vulnerabilities": [
            {"id": "V-1", "title": "critical vuln", "severity": "critical"},
            "this-is-malformed",
        ]
    }
    (run_dir / "audit-report.json").write_text(json.dumps(report), encoding="utf-8")
    claude = _fake_claude(tmp_path, write_harness=True)
    runner = _fake_runner(tmp_path)

    result = _run_phase4(tmp_path, run_dir, claude_bin=claude, runner=runner)

    assert result.returncode == 0, result.stderr
    summary = json.loads((tmp_path / "verify-out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["selected"] == 1
    assert summary["malformed_count"] == 1
    assert summary["malformed"][0]["reason"] == "not-an-object"
    assert [f["finding_id"] for f in summary["findings"]] == ["V-1"]


def test_phase4_finding_filter_and_identity_are_recorded(tmp_path: Path) -> None:
    run_dir = _fake_report(tmp_path)
    claude = _fake_claude(tmp_path, write_harness=True)
    runner = _fake_runner(tmp_path)

    result = _run_phase4(
        tmp_path,
        run_dir,
        claude_bin=claude,
        runner=runner,
        extra_args=[
            "--finding-id",
            "F-critical",
            "--occurrence-id",
            "demo/20260101T000000Z/F-critical",
            "--semantic-id",
            "sem-critical",
            "--run-id",
            "20260101T000000Z",
        ],
    )

    assert result.returncode == 0, result.stderr
    out = tmp_path / "verify-out"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["selected"] == 1
    entry = summary["findings"][0]
    assert entry["finding_id"] == "F-critical"
    assert entry["occurrence_id"] == "demo/20260101T000000Z/F-critical"
    assert entry["semantic_id"] == "sem-critical"
    assert entry["run_id"] == "20260101T000000Z"
    report = json.loads(Path(entry["report_path"]).read_text(encoding="utf-8"))
    assert report["occurrence_id"] == "demo/20260101T000000Z/F-critical"
    assert report["semantic_id"] == "sem-critical"
    assert report["run_id"] == "20260101T000000Z"


def test_phase4_persists_full_candidate_disposition(tmp_path):
    run_dir = _fake_report(tmp_path)
    result = _run_phase4(
        tmp_path,
        run_dir,
        claude_bin=_fake_claude(tmp_path),
        runner=_fake_runner(tmp_path),
        extra_args=["--max", "1"],
    )
    assert result.returncode == 0, result.stderr
    plan = json.loads((tmp_path / "verify-out/selection.json").read_text())
    assert plan["total_findings"] == 3
    assert len(plan["selected"]) == 1
    assert {row["reason_code"] for row in plan["deferred"]} == {"severity_filter", "batch_limit"}
    assert len(plan["selected"]) + len(plan["deferred"]) == 3
    assert (tmp_path / "verify-out/source-report.json").read_bytes() == (
        run_dir / "audit-report.json"
    ).read_bytes()


def test_phase4_autonomous_drain_and_bounded_retry(tmp_path):
    run_dir = _fake_report(tmp_path)
    result = _run_phase4(
        tmp_path,
        run_dir,
        claude_bin=_fake_claude(tmp_path, write_harness=False),
        runner=_fake_runner(tmp_path),
        extra_args=["--drain", "--max", "1", "--severity", "critical,high,medium,low,info"],
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / "verify-out"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["selected"] == summary["processed"] == 3
    assert all(row["attempts"] == 2 and row["retry_exhausted"] for row in summary["findings"])
    assert len(list((out / "retry-history").glob("*/1/result.json"))) == 3


def test_phase4_retry_uses_previous_failure_to_recover_automatically(tmp_path):
    run_dir = _fake_report(tmp_path)
    claude = _fake_claude(tmp_path, write_harness=True)
    code = claude.read_text().replace(
        "set -eu", 'set -eu\n[ -n "${PHASE4_RETRY_CONTEXT:-}" ] || exit 0', 1
    )
    claude.write_text(code)
    result = _run_phase4(
        tmp_path,
        run_dir,
        claude_bin=claude,
        runner=_fake_runner(tmp_path),
        extra_args=["--drain", "--severity", "critical,high,medium,low,info"],
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads((tmp_path / "verify-out/summary.json").read_text())
    assert summary["counts"] == {"confirmed": 3}
    assert all(row["attempts"] == 2 and not row["retry_exhausted"] for row in summary["findings"])

def test_failed_agent_cannot_confirm_from_partial_report(tmp_path):
    run_dir = _fake_report(tmp_path)
    claude = _write_executable(tmp_path / "partial.sh", """#!/bin/sh
mkdir -p "$VERIFY_RUN_DIR"
printf '%s' '{"verdict":"confirmed","reason":"unfinished"}' > "$VERIFY_RUN_DIR/verify-report.json"
exit 7
""")
    result = _run_phase4(tmp_path, run_dir, claude_bin=claude, runner=_fake_runner(tmp_path))
    assert result.returncode == 0, result.stderr
    reports = list((tmp_path / "verify-out").rglob("verify-report.json"))
    assert reports
    assert all(json.loads(file.read_text())["verdict"] == "blocked" for file in reports)
