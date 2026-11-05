from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from test_mine_reliability import make_supervisor_engine, run_supervisor
from test_mining_repair import _evaluation_pair, _ledger, _pool, _record, _training_pair

from audit_rsi.mining_driver import SubprocessCandidateRunner, drive_mining_repairs
from audit_rsi.mining_repair import (
    load_active_mining_repairs,
    propose_mining_repairs,
    save_mining_repair_candidates,
)
from audit_rsi.verification import write_jsonl


def _candidate(records: list[dict]) -> dict:
    return propose_mining_repairs(
        _pool(records), ledger=_ledger(records)["occurrences"]
    )[0]


def _install_candidate(root: Path, candidate: dict) -> None:
    save_mining_repair_candidates(
        [candidate], root / "rsi/mining-repairs/seed-candidates"
    )
    agentic = root / "rsi/mining-repairs/agentic"
    agentic.mkdir(parents=True, exist_ok=True)
    (agentic / f"{candidate['candidate_id']}.md").write_text(
        candidate["content"], encoding="utf-8"
    )


def _install_baseline(root: Path, project: str, records: list[dict]) -> Path:
    run = root / "runs" / project / "before"
    run.mkdir(parents=True)
    (run / "audit-report.json").write_text("{}", encoding="utf-8")
    write_jsonl(root / "rsi/verification-experience.jsonl", _pool(records))
    return run


def test_project_driver_executes_candidate_and_publishes(tmp_path: Path) -> None:
    training = [_record("alpha", "sem-fp-a", "fp")]
    candidate = _candidate(training)
    _install_candidate(tmp_path, candidate)
    baseline = [
        _record("alpha", "sem-fp-a", "fp", run="before"),
        _record("alpha", "sem-tp-a", "runtime-confirmed", run="before"),
    ]
    baseline_run = _install_baseline(tmp_path, "alpha", baseline)
    target = tmp_path / "target"
    target.mkdir()
    calls = []

    def runner(**request):
        calls.append(request)
        context = request["context_file"].read_text(encoding="utf-8")
        assert candidate["content"] in context
        assert "尚未发布" in context
        assert tmp_path / "runs" not in request["run_dir"].parents
        return [
            _record(
                "alpha",
                "sem-tp-a",
                "runtime-confirmed",
                run=request["run_dir"].name,
            )
        ]

    report = drive_mining_repairs(
        tmp_path,
        scope="project",
        project="alpha",
        target=target,
        baseline_run=baseline_run,
        image="env-image",
        miner_image="miner-image",
        runner=runner,
    )
    assert report["status"] == "ok"
    assert report["published"] == 1
    assert report["candidate_execution"] == "isolated_real_mining_verify_redteam"
    assert len(calls) == 1
    assert calls[0]["image"] == "env-image"
    assert calls[0]["miner_image"] == "miner-image"
    assert load_active_mining_repairs(tmp_path, "alpha")[0][0]["kind"] == "false_positive"
    assert (tmp_path / "rsi/mining-repairs/attempts").is_dir()


def test_driver_rejects_true_positive_regression_without_publishing(tmp_path: Path) -> None:
    training = [_record("alpha", "sem-fp-a", "fp")]
    _install_candidate(tmp_path, _candidate(training))
    baseline = [
        _record("alpha", "sem-fp-a", "fp", run="before"),
        _record("alpha", "sem-tp-1", "runtime-confirmed", run="before"),
        _record("alpha", "sem-tp-2", "runtime-confirmed", run="before"),
    ]
    baseline_run = _install_baseline(tmp_path, "alpha", baseline)

    def runner(**request):
        return [
            _record(
                "alpha",
                "sem-tp-1",
                "runtime-confirmed",
                run=request["run_dir"].name,
            )
        ]

    report = drive_mining_repairs(
        tmp_path,
        scope="project",
        project="alpha",
        target=tmp_path,
        baseline_run=baseline_run,
        runner=runner,
    )
    assert report["status"] == "rejected"
    assert report["published"] == 0
    assert load_active_mining_repairs(tmp_path, "alpha") == ([], [])


def test_shared_driver_selects_unseen_holdout_from_batch_manifest(tmp_path: Path) -> None:
    training = _training_pair()
    candidate = _candidate(training)
    _install_candidate(tmp_path, candidate)
    baseline, _ = _evaluation_pair()
    baseline_run = _install_baseline(tmp_path, "holdout", baseline)
    target = tmp_path / "holdout-target"
    target.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "projects": {
            "alpha": {"path": str(tmp_path / "alpha-target")},
            "beta": {"path": str(tmp_path / "beta-target")},
            "holdout": {"path": str(target)},
        }
    }), encoding="utf-8")
    env_dir = tmp_path / "env/holdout"
    env_dir.mkdir(parents=True)
    (env_dir / "env-manifest.json").write_text(json.dumps({
        "image": "holdout-env",
        "base_image": "holdout-miner",
    }), encoding="utf-8")
    calls = []

    def runner(**request):
        calls.append(request)
        assert candidate["content"] in request["context_file"].read_text(encoding="utf-8")
        return [
            _record(
                "holdout",
                "sem-tp-h",
                "runtime-confirmed",
                run=request["run_dir"].name,
            )
        ]

    report = drive_mining_repairs(
        tmp_path,
        scope="shared",
        manifest=manifest,
        runner=runner,
    )
    assert report["status"] == "ok"
    assert calls[0]["project"] == "holdout"
    assert calls[0]["target"] == target
    assert calls[0]["image"] == "holdout-env"
    assert calls[0]["miner_image"] == "holdout-miner"
    assert report["results"][0]["baseline_run"] == str(baseline_run)
    assert load_active_mining_repairs(tmp_path, "another-project")[0]


def test_driver_records_execution_failure_without_publishing(tmp_path: Path) -> None:
    training = [_record("alpha", "sem-fp-a", "fp")]
    _install_candidate(tmp_path, _candidate(training))
    baseline = [
        _record("alpha", "sem-fp-a", "fp", run="before"),
        _record("alpha", "sem-tp-a", "runtime-confirmed", run="before"),
    ]
    baseline_run = _install_baseline(tmp_path, "alpha", baseline)

    def runner(**request):
        raise RuntimeError("candidate mining failed")

    report = drive_mining_repairs(
        tmp_path,
        scope="project",
        project="alpha",
        target=tmp_path,
        baseline_run=baseline_run,
        runner=runner,
    )
    assert report["status"] == "error"
    assert report["published"] == 0


def test_default_runner_invokes_real_mining_verify_and_redteam(tmp_path: Path, monkeypatch) -> None:
    runner = SubprocessCandidateRunner(tmp_path)
    calls = []

    def execute(command, log_path, env):
        calls.append((command, log_path, dict(env)))

    monkeypatch.setattr(runner, "_execute", execute)
    context = tmp_path / "context.md"
    context.write_text("candidate", encoding="utf-8")
    attempt = tmp_path / "attempt"
    runner(
        project="alpha",
        target=tmp_path,
        run_dir=tmp_path / "candidate-run",
        image="env-image",
        miner_image="miner-image",
        context_file=context,
        attempt_dir=attempt,
    )
    assert len(calls) == 4
    assert "mine_one_docker.sh" in calls[0][0][1]
    assert "check_report.py" in calls[1][0][1]
    assert "phase4_verify_agent.sh" in calls[2][0][1]
    assert "phase5_redteam.sh" in calls[3][0][1]
    for _, _, env in calls:
        assert env["PERSIST_SANDBOX"] == "0"
        assert env["RSI_REPAIR_CONTEXT_FILE"] == str(context)
        assert env["RSI_VALIDATION_TRAJECTORY"] == str(attempt / "validation.jsonl")
    assert calls[0][1] == attempt / "mining.log"


def test_run_sh_executes_project_driver_in_main_pipeline(tmp_path: Path, monkeypatch) -> None:
    engine, binary, target = make_supervisor_engine(tmp_path)
    rsi_dir = engine / "scripts/rsi"
    rsi_dir.mkdir(parents=True)
    post = rsi_dir / "post_validation.sh"
    post.write_text(
        "#!/usr/bin/env bash\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = --run-dir ]; then run=\"$2\"; shift; fi\n"
        "  shift\n"
        "done\n"
        "mkdir -p \"$run/rsi\"\n"
        "echo '{\"status\":\"completed\"}' > \"$run/rsi/post-validation.json\"\n",
        encoding="utf-8",
    )
    post.chmod(0o755)
    package = engine / "audit_rsi"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "assert args[0] == 'mining-repair-drive'\n"
        "pathlib.Path(os.environ['TEST_DRIVER']).write_text(' '.join(args))\n"
        "output = pathlib.Path(args[args.index('--output') + 1])\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "output.write_text(json.dumps({'status': 'ok', 'published': 1}))\n",
        encoding="utf-8",
    )
    python = binary / "python3"
    python.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"${1:-}\" = -m ] && [ \"${2:-}\" = audit_rsi ]; then\n"
        f"  exec /usr/bin/python3 {package}/__main__.py \"${{@:3}}\"\n"
        "fi\n"
        "exec /usr/bin/python3 \"$@\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    driver_calls = tmp_path / "driver-calls.txt"
    monkeypatch.setenv("TEST_DRIVER", str(driver_calls))
    result, run, _ = run_supervisor(engine, binary, target, tmp_path, "recovery")
    assert result.returncode == 0, result.stderr
    driver_run = Path(str(run) + "-recovery")
    assert json.loads((driver_run / "rsi/driver.json").read_text())["published"] == 1
    arguments = driver_calls.read_text()
    assert "--scope project" in arguments
    assert "--project demo" in arguments
    assert f"--baseline-run {driver_run}" in arguments


def test_parallel_mine_executes_shared_driver_in_batch_pipeline(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    engine = tmp_path / "engine"
    mine_dir = engine / "scripts/mine"
    mine_dir.mkdir(parents=True)
    parallel = mine_dir / "parallel_mine.sh"
    shutil.copy2(root / "scripts/mine/parallel_mine.sh", parallel)
    agent = engine / ".claude/agents/security-orchestrator.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("fixture", encoding="utf-8")
    rsi_dir = engine / "scripts/rsi"
    rsi_dir.mkdir(parents=True)
    post = rsi_dir / "post_validation.sh"
    post.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    post.chmod(0o755)
    package = engine / "audit_rsi"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "assert args[0] == 'mining-repair-drive'\n"
        "pathlib.Path(os.environ['TEST_SHARED_DRIVER']).write_text(' '.join(args))\n"
        "output = pathlib.Path(args[args.index('--output') + 1])\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "output.write_text(json.dumps({'status': 'ok', 'published': 1}))\n",
        encoding="utf-8",
    )
    target = tmp_path / "target"
    target.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "projects": {"demo": {"path": str(target), "status": "ok"}}
    }), encoding="utf-8")
    executor = tmp_path / "executor.sh"
    executor.write_text(
        "#!/usr/bin/env bash\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = --run-dir ]; then run=\"$2\"; shift; fi\n"
        "  shift\n"
        "done\n"
        "mkdir -p \"$run\"\n"
        "echo '{\"findings\":[]}' > \"$run/audit-report.json\"\n"
        "echo '# Report' > \"$run/audit-report.md\"\n"
        "echo '{\"status\":\"success\",\"reports_complete\":true,"
        "\"exit_code\":0,\"timed_out\":false}' > \"$run/run-meta.json\"\n",
        encoding="utf-8",
    )
    executor.chmod(0o755)
    binary = tmp_path / "bin"
    binary.mkdir()
    python = binary / "python3"
    python.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"${1:-}\" = -m ] && [ \"${2:-}\" = audit_rsi ]; then\n"
        f"  exec /usr/bin/python3 {package}/__main__.py \"${{@:3}}\"\n"
        "fi\n"
        "exec /usr/bin/python3 \"$@\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    driver_calls = tmp_path / "shared-driver-calls.txt"
    env = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "TEST_SHARED_DRIVER": str(driver_calls),
    }
    state = tmp_path / "state"
    completed = subprocess.run(
        [
            "bash",
            str(parallel),
            "--foreground",
            "--manifest",
            str(manifest),
            "--runs-root",
            str(tmp_path / "runs"),
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
            "5",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads((state / "rsi/shared-driver.json").read_text())["published"] == 1
    arguments = driver_calls.read_text()
    assert "--scope shared" in arguments
    assert f"--manifest {manifest}" in arguments
