import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("durable", ROOT / "scripts/mine/durable_recovery.py")
durable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(durable)


def artifact():
    return {"findings": [], "hypotheses": [], "coverage": {"files_read": 3}, "limitations": []}


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    root = tmp_path / "engine"
    mine = root / "scripts/mine"
    mine.mkdir(parents=True)
    wrapper = mine / "mine_one_docker.sh"
    wrapper.write_text("""#!/usr/bin/env bash
set -eu
agent=""
while [ "$#" -gt 0 ]; do
 case "$1" in
  --run-dir) output="$2"; shift;;
  --agent) agent="$2"; shift;;
 esac
 shift
done
mkdir -p "$output"
printf '%s\\n' "$agent" >> "$TEST_CALLS"
if [ "$agent" = recovery-infra-worker ] && [ "${TEST_FAIL_WORKER:-0}" = 1 ]; then exit 1; fi
if [ "${TEST_FAIL_ONCE:-0}" = 1 ] && [ ! -f "$TEST_CALLS.once" ]; then
 touch "$TEST_CALLS.once"; exit 1
fi
cat > "$output/audit-report.json" <<'JSON'
{"findings":[],"hypotheses":[],"coverage":{"files_read":3},"limitations":[]}
JSON
printf '# Report' > "$output/audit-report.md"
echo '{"type":"assistant","message":{"content":[]}}' > "$output/raw.jsonl"
""")
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(target),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    source = tmp_path / "source"
    source.mkdir()
    events = []
    for key in ("config", "filesystem"):
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": key,
                            "name": "Agent",
                            "input": {
                                "description": key,
                                "prompt": f"Write .workspace/findings/infra-{key}.json",
                            },
                        }
                    ]
                },
            }
        )
    (source / "raw.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    seed = source / "recovery/findings-before-timeout"
    seed.mkdir(parents=True)
    (seed / "infra-config.json").write_text(json.dumps(artifact()))
    calls = tmp_path / "calls"
    monkeypatch.setenv("TEST_CALLS", str(calls))
    monkeypatch.setattr(durable, "ROOT", root)
    args = SimpleNamespace(
        target=str(target),
        recover_from=str(source),
        run_dir=str(tmp_path / "runs/demo/run-1"),
        budget=30,
        task_timeout=5,
        idle_timeout=2,
        max_attempts=2,
        model="test-model",
    )
    return args, calls


def test_reuses_completed_task_and_resume_does_not_call_worker_again(recovery):
    args, calls = recovery
    job = durable.Recovery(args)
    assert job.run_all() == 0
    assert job.state["tasks"]["infra-config"]["status"] == "reused"
    assert calls.read_text().splitlines() == ["recovery-infra-worker", "recovery-report-assembler"]
    assert durable.Recovery(args).run_all() == 0
    assert len(calls.read_text().splitlines()) == 2
    report = json.loads((Path(args.run_dir) / "audit-report.json").read_text())
    assert report["coverage"]["analysis_mode"] == "assembly-only"
    from submission import accepted_submissions
    delivered = accepted_submissions("orchestrator", args.run_dir)
    names = {Path(item["path"]).relative_to(args.run_dir).as_posix()
             for item in delivered["deliveries"][0]["files"]}
    assert {"audit-report.json", "audit-report.md",
            "artifacts/infra-config.json", "artifacts/infra-filesystem.json"} <= names
    assert json.loads((Path(args.run_dir) / "run-meta.json").read_text())["delivery_accepted"]


def test_only_failed_attempt_is_retried(recovery, monkeypatch):
    args, calls = recovery
    monkeypatch.setenv("TEST_FAIL_ONCE", "1")
    job = durable.Recovery(args)
    assert job.run_all() == 0
    task = job.state["tasks"]["infra-filesystem"]
    assert [a["status"] for a in task["attempts"]] == ["failed", "completed"]
    assert (Path(args.run_dir) / "attempts/infra-filesystem/01/wrapper.log").exists()
    assert calls.read_text().splitlines().count("recovery-infra-worker") == 2


def test_exhausted_task_does_not_block_report_assembly(recovery, monkeypatch):
    args, calls = recovery
    monkeypatch.setenv("TEST_FAIL_WORKER", "1")
    job = durable.Recovery(args)
    assert job.run_all() == 2
    assert job.state["status"] == "partial"
    assert job.state["tasks"]["infra-config"]["status"] == "reused"
    assert job.state["tasks"]["infra-filesystem"]["status"] == "failed"
    assert calls.read_text().splitlines()[-1] == "recovery-report-assembler"
    assert (Path(args.run_dir) / "audit-report.json").exists()
    report = Path(args.run_dir) / "audit-report.json"
    original = report.read_bytes()
    assert durable.Recovery(args).run_all() == 2
    assert report.read_bytes() == original
    assert json.loads((Path(args.run_dir) / "run-meta.json").read_text())["delivery_accepted"]


def test_delivery_rejection_cannot_report_recovery_success(recovery, tmp_path):
    args, _ = recovery
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    job = durable.Recovery(args)
    extra = Path(args.run_dir) / "artifacts/untrusted.json"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.symlink_to(outside)
    assert job.run_all() == 2
    meta = json.loads((Path(args.run_dir) / "run-meta.json").read_text())
    assert meta["status"] == "failed"
    assert meta["reports_complete"] is False
    assert meta["delivery_accepted"] is False
    assert "符号链接" in meta["delivery_error"]
    assert durable.valid_report(args.run_dir)


def test_existing_recovery_can_submit_once_without_restarting_model(recovery, monkeypatch):
    args, calls = recovery
    source = Path(args.run_dir).with_name("old-run")
    shutil.copytree(args.recover_from, source)
    args.recover_from = str(source)
    args.run_dir = str(source) + "-recovery"
    original = durable.deliver_recovery_report
    monkeypatch.setattr(durable, "deliver_recovery_report",
                        lambda _run: (_ for _ in ()).throw(ValueError("delivery unavailable")))
    assert durable.Recovery(args).run_all() == 2
    assert durable.valid_report(args.run_dir)
    receipts = Path(args.run_dir) / ".stage-submissions/orchestrator"
    assert not list(receipts.glob("*.json"))
    before = calls.read_text().splitlines()
    monkeypatch.setattr(durable, "deliver_recovery_report", original)
    first = durable.finalize_existing_recovery(args.run_dir)
    assert first["accepted"] == 1
    assert calls.read_text().splitlines() == before
    assert json.loads((Path(args.run_dir) / "run-meta.json").read_text())["status"] == "success"
    count = len(list(receipts.glob("*.json")))
    second = durable.finalize_existing_recovery(args.run_dir)
    assert second["accepted"] == 1
    assert len(list(receipts.glob("*.json"))) == count
    assert calls.read_text().splitlines() == before


def test_existing_recovery_rejects_changed_accepted_report(recovery):
    args, _ = recovery
    source = Path(args.run_dir).with_name("old-run")
    shutil.copytree(args.recover_from, source)
    args.recover_from = str(source)
    args.run_dir = str(source) + "-recovery"
    assert durable.Recovery(args).run_all() == 0
    report = Path(args.run_dir) / "audit-report.json"
    data = json.loads(report.read_text())
    data["notice"] = "changed after accepted"
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="已验收恢复报告的内容已改变"):
        durable.finalize_existing_recovery(args.run_dir)
    assert json.loads(report.read_text())["notice"] == "changed after accepted"


def test_changed_target_revision_refuses_checkpoint_reuse(recovery):
    args, _ = recovery
    durable.Recovery(args)
    subprocess.run(
        [
            "git",
            "-C",
            args.target,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "new revision",
        ],
        check=True,
    )
    with pytest.raises(ValueError, match="revision changed"):
        durable.Recovery(args)


def test_corrupted_artifact_is_not_silently_accepted(recovery):
    args, calls = recovery
    job = durable.Recovery(args)
    assert job.run_all() == 0
    path = Path(args.run_dir) / "artifacts/infra-filesystem.json"
    path.write_text("{}")
    assert durable.Recovery(args).run_all() == 0
    assert calls.read_text().splitlines().count("recovery-infra-worker") == 2


def test_idle_timeout_stops_process_and_preserves_partial_file(tmp_path):
    partial = tmp_path / "partial.json"
    partial.write_text('{"progress":"saved"}')
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    stopped = []

    def stop():
        stopped.append(True)
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)

    code, reason = durable.watch_process(
        process, tmp_path / "raw.jsonl", idle=0.1, timeout=2, stop=stop, poll=0.02
    )
    assert (code, reason) == (125, "setup_timeout")
    assert stopped and process.poll() is not None
    assert json.loads(partial.read_text())["progress"] == "saved"


def test_wrapper_log_activity_does_not_reset_worker_idle_timeout(tmp_path):
    log = tmp_path / "wrapper.log"
    with log.open("w") as stream:
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                'import time;\nwhile True: print("heartbeat"); time.sleep(.01)',
            ],
            stdout=stream,
            start_new_session=True,
        )
        code, reason = durable.watch_process(
            process,
            tmp_path / "raw.jsonl",
            idle=0.1,
            timeout=2,
            stop=lambda: (os.killpg(process.pid, signal.SIGTERM), process.wait(timeout=2)),
            poll=0.02,
        )
    assert (code, reason) == (125, "setup_timeout")
    assert log.stat().st_size > 0


def test_source_run_cannot_be_overwritten(recovery):
    args, _ = recovery
    original = Path(args.recover_from, "raw.jsonl").read_text()
    args.run_dir = args.recover_from
    with pytest.raises(ValueError, match="source evidence"):
        durable.Recovery(args)
    assert Path(args.recover_from, "raw.jsonl").read_text() == original


def test_interrupted_attempt_resumes_only_that_task(recovery, monkeypatch):
    args, calls = recovery
    job = durable.Recovery(args)
    task = job.state["tasks"]["infra-filesystem"]
    task["status"] = "running"
    task["attempts"] = [{"status": "running", "container": "mg-recover-test-stale"}]
    monkeypatch.setattr(durable.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    assert job.run_all() == 0
    assert [a["status"] for a in task["attempts"]] == ["interrupted", "completed"]
    assert calls.read_text().splitlines().count("recovery-infra-worker") == 1


def test_assembly_failure_preserves_task_artifacts_and_marks_partial(recovery):
    args, _ = recovery
    wrapper = durable.ROOT / "scripts/mine/mine_one_docker.sh"
    wrapper.write_text(
        wrapper.read_text().replace(
            'mkdir -p "$output"',
            'mkdir -p "$output"\nif [ "$agent" = recovery-report-assembler ]; then exit 1; fi',
        )
    )
    job = durable.Recovery(args)
    assert job.run_all() == 2
    assert (Path(args.run_dir) / "artifacts/infra-filesystem.json").exists()
    partial = json.loads((Path(args.run_dir) / "partial-report.json").read_text())
    assert partial["status"] == "partial"
    assert partial["limitations"]
    assert (
        json.loads((Path(args.run_dir) / "run-meta.json").read_text())["reports_complete"] is False
    )


def test_wall_timeout_bounds_even_continuous_worker_output(tmp_path):
    raw = tmp_path / "raw.jsonl"
    code = (
        "import time,pathlib; p=pathlib.Path("
        + repr(str(raw))
        + ");\nwhile True: p.open('a').write('progress\\n'); time.sleep(.01)"
    )
    process = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    result = durable.watch_process(
        process,
        raw,
        idle=1,
        timeout=0.15,
        stop=lambda: (os.killpg(process.pid, signal.SIGTERM), process.wait(timeout=2)),
        poll=0.02,
    )
    assert result == (124, "wall_timeout")


def test_custom_prompt_reaches_container_without_exposing_auth(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("bounded task")
    sentinel = "test-only-redaction-sentinel"
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/mine/mine_one_docker.sh"),
            "--dry-run",
            "--target",
            str(tmp_path),
            "--prompt",
            str(prompt),
        ],
        env={**os.environ, "ANTHROPIC_AUTH_TOKEN": sentinel},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "CUSTOM_PROMPT_FILE=/opt/custom-audit-prompt.txt" in result.stdout
    assert "custom-audit-prompt.txt" in result.stdout
    assert sentinel not in result.stdout


def test_native_guard_terminates_stalled_cli_and_records_reason(tmp_path):
    health = tmp_path / "health.json"
    raw = tmp_path / "raw.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/mine/progress_guard.py"),
            "--raw",
            str(raw),
            "--health",
            str(health),
            "--idle",
            ".1",
            "--setup-idle",
            ".1",
            "--wall",
            "2",
            "--",
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ],
        timeout=5,
    )
    assert result.returncode == 125
    assert json.loads(health.read_text())["reason"] == "setup_timeout"


def test_native_guard_preserves_successful_cli_exit(tmp_path):
    health = tmp_path / "health.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/mine/progress_guard.py"),
            "--raw",
            str(tmp_path / "raw"),
            "--health",
            str(health),
            "--idle",
            "1",
            "--wall",
            "2",
            "--",
            sys.executable,
            "-c",
            "pass",
        ],
        timeout=5,
    )
    assert result.returncode == 0
    assert json.loads(health.read_text())["reason"] == "exited"


def test_uncheckpointed_preparation_is_preserved_on_resume(recovery):
    args, _ = recovery
    orphan = Path(args.run_dir) / "attempts/assembly/01/target"
    orphan.mkdir(parents=True)
    (orphan / "old-notes.txt").write_text("before crash")
    job = durable.Recovery(args)
    assert job.run_all() == 0
    preserved = list(orphan.parent.parent.glob("1.abandoned-*/target/old-notes.txt"))
    assert len(preserved) == 1 and preserved[0].read_text() == "before crash"


def test_report_retry_receives_format_diagnostics(recovery):
    args, _ = recovery
    wrapper = durable.ROOT / "scripts/mine/mine_one_docker.sh"
    source = wrapper.read_text().replace(
        '--agent) agent="$2"; shift;;',
        '--agent) agent="$2"; shift;;\n  --prompt) prompt="$2"; shift;;',
    )
    source = source.replace(
        'mkdir -p "$output"',
        """mkdir -p "$output"
if [ "$agent" = recovery-report-assembler ] && [ ! -f "$TEST_CALLS.bad-report" ]; then
 touch "$TEST_CALLS.bad-report"
 echo '{"findings":[{"id":"BAD"}]}' > "$output/audit-report.json"
 exit 0
fi
if [ "$agent" = recovery-report-assembler ]; then
 cp "$prompt" "$TEST_CALLS.retry-prompt"
fi""",
    )
    wrapper.write_text(source)
    job = durable.Recovery(args)
    assert job.run_all() == 0
    assert len(job.state["assembly"]["attempts"]) == 2
    diagnostics = job.state["assembly"]["last_failure"]
    assert diagnostics["incomplete_findings"][0]["id"] == "BAD"
    assert "title" in diagnostics["incomplete_findings"][0]["missing"]
    assert "incomplete_findings" in Path(str(recovery[1]) + ".retry-prompt").read_text()


def test_default_entrypoint_automatically_recovers_after_native_idle_timeout(tmp_path):
    engine = tmp_path / "engine"
    mine = engine / "scripts/mine"
    mine.mkdir(parents=True)
    shutil.copy2(ROOT / "run.sh", engine / "run.sh")
    agent = engine / ".claude/agents/security-orchestrator.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("fixture")
    (mine / "mine_one_docker.sh").write_text("""#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
 if [ "$1" = --run-dir ]; then run="$2"; shift; fi
 shift
done
mkdir -p "$run/task-artifacts"
echo '{"type":"system","subtype":"init"}' > "$run/raw.jsonl"
echo '{"saved":true}' > "$run/task-artifacts/kept.json"
exit 125
""")
    (mine / "mine_one_docker.sh").chmod(0o755)
    (mine / "render_claude_log.py").write_text("""import sys,pathlib
args=sys.argv
pathlib.Path(args[args.index("--output")+1]).write_text("checkpoint saved")
""")
    (mine / "durable_recovery.py").write_text("""import sys,pathlib,argparse

def plan_from_trace(source):
    return {"infra-filesystem": {"status":"pending"}}

if __name__ == "__main__":
    args=sys.argv
    destination=pathlib.Path(args[args.index("--run-dir")+1])
    destination.mkdir(parents=True)
    (destination/"recovered.txt").write_text("automatic recovery invoked")
    (destination/"audit-report.json").write_text('{"findings":[]}')
    (destination/"audit-report.md").write_text('# Report')
""")
    (mine / "check_report.py").write_text("import sys\nraise SystemExit(0)\n")
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o755)
    target = tmp_path / "target"
    target.mkdir()
    run = engine / "runs/demo/run-1"
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
            "2",
            "--skip-env",
            "--skip-verify",
        ],
        env={
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "AUTO_RECOVER": "1",
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((run / "task-artifacts/kept.json").read_text())["saved"] is True
    assert Path(str(run) + "-recovery/recovered.txt").exists()
    original_status = json.loads(Path(str(run) + ".meta/status.json").read_text())
    assert original_status["state"] == "timeout" and original_status["exit_code"] == 125
