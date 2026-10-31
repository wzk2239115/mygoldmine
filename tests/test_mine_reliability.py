import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("durable_reliability", ROOT / "scripts/mine/durable_recovery.py")
durable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(durable)

VALID_REPORT = {
    "findings": [
        {
            "id": "F-1",
            "title": "未认证接口允许关闭服务",
            "severity": "high",
            "root_cause": "接口缺少认证",
            "impact": "服务被拒绝",
            "reproduction": "启动服务后调用接口",
            "remediation": "增加认证检查",
            "evidence": ["app.py:10"],
        }
    ]
}


class FakeClock:
    def __init__(self, on_sleep=None):
        self.value = 0.0
        self.on_sleep = on_sleep

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds
        if self.on_sleep:
            self.on_sleep()


class FakeProcess:
    def poll(self):
        return None


def watch_with_fake_clock(raw, clock, *, idle, setup_idle, wall):
    stopped = []

    def stop():
        stopped.append(clock())

    result = durable.watch_process(
        FakeProcess(),
        raw,
        idle=idle,
        setup_idle=setup_idle,
        timeout=wall,
        stop=stop,
        poll=10,
        clock=clock,
        sleeper=clock.sleep,
    )
    return result, stopped


def test_setup_without_raw_uses_longer_setup_budget(tmp_path):
    clock = FakeClock()
    result, stopped = watch_with_fake_clock(
        tmp_path / "raw.jsonl", clock, idle=10, setup_idle=25, wall=100
    )
    assert result == (125, "setup_timeout")
    assert stopped == [30]


def test_model_without_events_uses_model_idle_budget(tmp_path):
    raw = tmp_path / "raw.jsonl"

    def emit_model_event():
        if not raw.exists():
            raw.write_text('{"type":"assistant","message":{"content":[]}}\n')

    clock = FakeClock(emit_model_event)
    result, stopped = watch_with_fake_clock(raw, clock, idle=10, setup_idle=25, wall=100)
    assert result == (125, "model_idle_timeout")
    assert stopped == [20]


def test_pending_tool_is_not_idle_killed_but_wall_limit_remains(tmp_path):
    raw = tmp_path / "raw.jsonl"

    def emit_tool():
        if not raw.exists():
            raw.write_text(
                '{"type":"assistant","message":{"content":'
                '[{"type":"tool_use","id":"long-tool","name":"Bash"}]}}\n'
            )

    clock = FakeClock(emit_tool)
    phases = []

    def stop():
        pass

    result = durable.watch_process(
        FakeProcess(),
        raw,
        idle=10,
        setup_idle=25,
        timeout=65,
        stop=stop,
        poll=10,
        clock=clock,
        sleeper=clock.sleep,
        status=lambda state: phases.append(state["phase"]),
    )
    assert result == (124, "wall_timeout")
    assert "tool_running" in phases
    assert clock.value == 70


@pytest.fixture
def fake_mine(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("fake audit")
    binary = tmp_path / "bin"
    binary.mkdir()
    clock = tmp_path / "clock"
    clock.write_text("1000000")
    calls = tmp_path / "calls"

    claude = binary / "claude"
    claude.write_text(
        """#!/usr/bin/env python3
import json, os, pathlib, sys
mode = os.environ.get("FAKE_MODE", "invalid")
root = pathlib.Path(os.environ["TEST_TMP"])
count_file = root / "count"
count = int(count_file.read_text()) if count_file.exists() else 0
count += 1
count_file.write_text(str(count))
with pathlib.Path(os.environ["FAKE_CALLS"]).open("a") as stream:
    stream.write(str(count) + "\\n")
if mode == "deadline":
    clock = root / "clock"
    clock.write_text(str(int(clock.read_text()) + 30))
    print(f"429 attempt-{count}", file=sys.stderr)
    raise SystemExit(1)
if mode == "old-429":
    print("429 rate limit" if count == 1 else "permission denied", file=sys.stderr)
    raise SystemExit(1)
if mode == "125":
    raise SystemExit(125)
run = pathlib.Path(os.environ["RUN_DIR"])
if mode == "invalid":
    (run / "audit-report.json").write_text('{"findings":[{"id":"BAD"}]}')
    (run / "audit-report.md").write_text("# Invalid")
    raise SystemExit(0)
if mode in {"success", "partial"}:
    (run / "audit-report.json").write_text(os.environ["VALID_REPORT"])
    (run / "audit-report.md").write_text("# Valid")
    raise SystemExit(0 if mode == "success" else 7)
raise SystemExit(1)
"""
    )
    claude.chmod(0o755)
    date = binary / "date"
    date.write_text(
        """#!/usr/bin/env python3
import datetime, pathlib, sys
root = pathlib.Path(__import__('os').environ["TEST_TMP"])
value = int((root / "clock").read_text())
fmt = sys.argv[-1]
if fmt == "+%s":
    print(value)
else:
    print(datetime.datetime.fromtimestamp(value, datetime.timezone.utc).strftime(fmt[1:]))
"""
    )
    date.chmod(0o755)
    sleep = binary / "sleep"
    sleep.write_text(
        """#!/usr/bin/env python3
import os, pathlib, sys
root = pathlib.Path(os.environ["TEST_TMP"])
clock = root / "clock"
clock.write_text(str(int(clock.read_text()) + int(float(sys.argv[1]))))
"""
    )
    sleep.chmod(0o755)
    return target, prompt, binary, calls, clock


def run_fake_mine(fake_mine, tmp_path, mode, *, timeout="100", attempts="3", delay="0"):
    target, prompt, binary, calls, clock = fake_mine
    run = tmp_path / f"run-{mode}"
    env = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "CLAUDE_BIN": str(binary / "claude"),
        "JEV_TRIAGE": "0",
        "MAX_ATTEMPTS": attempts,
        "RETRY_DELAY": delay,
        "FAKE_MODE": mode,
        "FAKE_CALLS": str(calls),
        "TEST_TMP": str(tmp_path),
        "VALID_REPORT": json.dumps(VALID_REPORT, ensure_ascii=False),
        "AUDIT_IDLE_TIMEOUT": "5",
        "AUDIT_SETUP_IDLE_TIMEOUT": "10",
    }
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/mine/mine_one.sh"),
            "--target",
            str(target),
            "--run-dir",
            str(run),
            "--prompt",
            str(prompt),
            "--timeout",
            timeout,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    meta = json.loads((run / "run-meta.json").read_text())
    return result, run, meta, calls


def test_retries_share_deadline_and_have_independent_stderr(fake_mine, tmp_path):
    result, run, meta, calls = run_fake_mine(fake_mine, tmp_path, "deadline", delay="60")
    assert result.returncode == 124, result.stderr
    assert meta["status"] == "timeout" and meta["attempts"] == 2
    assert len(calls.read_text().splitlines()) == 2
    first = (run / "claude.stderr.attempt-01.log").read_text()
    second = (run / "claude.stderr.attempt-02.log").read_text()
    assert "attempt-1" in first and "attempt-2" not in first
    assert "attempt-2" in second and "attempt-1" not in second
    assert "剩余 10s" in result.stderr


def test_previous_attempt_429_does_not_trigger_another_retry(fake_mine, tmp_path):
    result, run, meta, calls = run_fake_mine(fake_mine, tmp_path, "old-429")
    assert result.returncode == 1
    assert meta["attempts"] == 2 and len(calls.read_text().splitlines()) == 2
    assert not (run / "claude.stderr.attempt-03.log").exists()


def test_idle_exit_125_is_timeout(fake_mine, tmp_path):
    result, _, meta, _ = run_fake_mine(fake_mine, tmp_path, "125")
    assert result.returncode == 125
    assert meta["status"] == "timeout" and meta["timed_out"] is True


def test_invalid_report_is_not_complete_or_successful(fake_mine, tmp_path):
    result, run, meta, _ = run_fake_mine(fake_mine, tmp_path, "invalid")
    assert result.returncode == 2
    assert meta["status"] == "failed" and meta["reports_complete"] is False
    assert json.loads((run / "report-quality.json").read_text())["incomplete"] == 1


@pytest.mark.parametrize(
    ("mode", "expected_rc", "expected_status"),
    [("success", 0, "success"), ("partial", 7, "partial")],
)
def test_valid_report_distinguishes_success_and_partial(
    fake_mine, tmp_path, mode, expected_rc, expected_status
):
    result, _, meta, _ = run_fake_mine(fake_mine, tmp_path, mode)
    assert result.returncode == expected_rc
    assert meta["status"] == expected_status and meta["reports_complete"] is True


def make_supervisor_engine(tmp_path):
    engine = tmp_path / "engine"
    mine = engine / "scripts/mine"
    mine.mkdir(parents=True)
    (engine / "scripts/env").mkdir(parents=True)
    (engine / "scripts/verify").mkdir(parents=True)
    (engine / "scripts/workflow").mkdir(parents=True)
    agent = engine / ".claude/agents/security-orchestrator.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("fixture")
    shutil.copy2(ROOT / "run.sh", engine / "run.sh")
    shutil.copy2(ROOT / "scripts/mine/check_report.py", mine / "check_report.py")
    shutil.copy2(
        ROOT / "scripts/workflow/report_quality.py", engine / "scripts/workflow/report_quality.py"
    )
    (mine / "render_claude_log.py").write_text(
        "import pathlib,sys\nargs=sys.argv\n"
        "pathlib.Path(args[args.index('--output')+1]).write_text('rendered')\n"
    )
    (mine / "mine_one_docker.sh").write_text(
        """#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
 if [ "$1" = --run-dir ]; then run="$2"; shift; fi
 shift
done
mkdir -p "$run"
echo '{"type":"system","subtype":"init"}' > "$run/raw.jsonl"
if [ "${INITIAL_MODE:-recovery}" = invalid ]; then
 echo '{"findings":[{"id":"BAD"}]}' > "$run/audit-report.json"
 echo '# Invalid' > "$run/audit-report.md"
 exit 2
fi
exit 125
"""
    )
    (mine / "mine_one_docker.sh").chmod(0o755)
    (mine / "durable_recovery.py").write_text(
        """import json, pathlib, sys

def plan_from_trace(source):
    return {"infra-filesystem": {"status": "pending"}}

if __name__ == "__main__":
    args = sys.argv
    destination = pathlib.Path(args[args.index("--run-dir") + 1])
    destination.mkdir(parents=True)
    (destination / "audit-report.json").write_text('{"findings":[]}')
    (destination / "audit-report.md").write_text('# Recovered')
    (destination / "run-meta.json").write_text(json.dumps({
        "status": "success", "reports_complete": True, "exit_code": 0
    }))
"""
    )
    (engine / "scripts/env/build_env.sh").write_text(
        """#!/usr/bin/env bash
root="$(cd "$(dirname "$0")/../.." && pwd)"
while [ "$#" -gt 0 ]; do
 if [ "$1" = --project ]; then project="$2"; shift; fi
 shift
done
mkdir -p "$root/env/$project"
printf '{"image":"fake-image","env_status":"ready"}\n' > "$root/env/$project/env-manifest.json"
"""
    )
    (engine / "scripts/verify/auto_verify.sh").write_text(
        """#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
 case "$1" in
  --run-dir) run="$2"; shift;;
  --output) output="$2"; shift;;
 esac
 shift
done
printf '%s\n' "$run" >> "$TEST_VERIFY"
mkdir -p "$output"
echo '# Verified' > "$output/summary.md"
echo '{"counts":{}}' > "$output/summary.json"
"""
    )
    binary = tmp_path / "docker-bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o755)
    target = tmp_path / "supervisor-target"
    target.mkdir()
    return engine, binary, target


def run_supervisor(engine, binary, target, tmp_path, mode):
    run = engine / "runs/demo/run-1"
    verify = tmp_path / f"verify-{mode}"
    result = subprocess.run(
        [
            "bash",
            str(engine / "run.sh"),
            "--supervise",
            "--target",
            str(target),
            "--project",
            "demo",
            "--run-dir",
            str(run),
            "--timeout",
            "10",
        ],
        env={
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "AUTO_RECOVER": "1" if mode == "recovery" else "0",
            "INITIAL_MODE": mode,
            "TEST_VERIFY": str(verify),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result, run, verify


def test_successful_recovery_returns_to_phase4(tmp_path):
    engine, binary, target = make_supervisor_engine(tmp_path)
    result, run, verify = run_supervisor(engine, binary, target, tmp_path, "recovery")
    assert result.returncode == 0, result.stderr
    assert verify.read_text().strip() == str(run) + "-recovery"
    original = json.loads(Path(str(run) + ".meta/status.json").read_text())
    recovered = json.loads(Path(str(run) + "-recovery.meta/status.json").read_text())
    assert original["state"] == "timeout" and original["exit_code"] == 125
    assert recovered["state"] == "success"


def test_quality_failure_does_not_auto_verify(tmp_path):
    engine, binary, target = make_supervisor_engine(tmp_path)
    result, run, verify = run_supervisor(engine, binary, target, tmp_path, "invalid")
    assert result.returncode == 2, result.stderr
    assert not verify.exists()
    status = json.loads(Path(str(run) + ".meta/status.json").read_text())
    assert status["state"] == "failed"


def make_batch_fixture(tmp_path):
    target = tmp_path / "batch-target"
    target.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"projects": {"demo": {"path": str(target), "status": "ok"}}})
    )
    executor = tmp_path / "executor.sh"
    executor.write_text(
        """#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
 if [ "$1" = --run-dir ]; then run="$2"; shift; fi
 shift
done
mkdir -p "$run"
if [ "${BATCH_MODE}" = timeout ]; then exit 125; fi
echo '{"findings":[{"id":"BAD"}]}' > "$run/audit-report.json"
echo '# Invalid' > "$run/audit-report.md"
echo '{"status":"failed","reports_complete":false,"exit_code":0,"timed_out":false}' > "$run/run-meta.json"
exit 0
"""
    )
    executor.chmod(0o755)
    return target, manifest, executor


def run_batch(tmp_path, manifest, executor, mode):
    runs = tmp_path / f"runs-{mode}"
    state = tmp_path / f"state-{mode}"
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/mine/parallel_mine.sh"),
            "--foreground",
            "--manifest",
            str(manifest),
            "--runs-root",
            str(runs),
            "--state-dir",
            str(state),
            "--executor",
            str(executor),
            "--retries",
            "0",
            "--max-parallel",
            "1",
            "--min-free-gb",
            "0",
            "--timeout",
            "10",
        ],
        env={**os.environ, "BATCH_MODE": mode},
        capture_output=True,
        text=True,
        timeout=10,
    )
    status = json.loads((state / "projects/demo.json").read_text())
    return result, status


def test_batch_rejects_files_when_quality_completion_is_false(tmp_path):
    _, manifest, executor = make_batch_fixture(tmp_path)
    result, status = run_batch(tmp_path, manifest, executor, "invalid")
    assert result.returncode == 1
    assert status["status"] == "failed" and status["exit_code"] == 2


def test_batch_treats_125_as_timeout_without_retry(tmp_path):
    _, manifest, executor = make_batch_fixture(tmp_path)
    result, status = run_batch(tmp_path, manifest, executor, "timeout")
    assert result.returncode == 1
    assert status["status"] == "timeout" and status["exit_code"] == 125
    assert status["attempt"] == 1
