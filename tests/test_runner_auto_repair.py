import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/runner"))
import auto_repair as repair  # noqa: E402


def setup(tmp_path, monkeypatch):
    (tmp_path / "runner").mkdir()
    (tmp_path / "runner/requirements.txt").write_text("openai>=2,<3\n")
    (tmp_path / "runner/allowed-packages.txt").write_text("openai\n")
    monkeypatch.setattr(repair, "ROOT", tmp_path)
    monkeypatch.setattr(repair, "claude_connection", lambda model: ("test", {}))


def smoke(ok):
    return {
        "ok": ok,
        "modules": [{"name": "openai", "status": "ok" if ok else "missing"}],
        "commands": [],
    }


def test_healthy_skips_agent_and_install(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "run_checks", lambda *a: smoke(True))
    monkeypatch.setattr(
        repair,
        "command",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected repair")),
    )
    result = repair.ensure_runner(sys.executable, tmp_path)
    assert result["status"] == "ready"
    assert result["repaired"] is False


def test_repair_smoke_then_reuse_without_repeat(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(repair, "run_checks", lambda python, *a: smoke("/venv/" in python))
    calls = []
    monkeypatch.setattr(repair, "command", lambda argv, *a, **k: calls.append(argv) or 0)
    result = repair.ensure_runner("/usr/bin/python3", tmp_path / "a")
    assert result["status"] == "ready" and result["repaired"]
    assert len(calls) == 3
    assert calls[0][calls[0].index("--agent") + 1] == "runner-builder"
    assert calls[0][calls[0].index("--tools") + 1] == "Read"
    assert "-m" in calls[1] and "venv" in calls[1]
    assert "--isolated" in calls[2]
    again = repair.ensure_runner("/usr/bin/python3", tmp_path / "b")
    assert again["python"] == result["python"]
    assert len(calls) == 3


def test_failed_smoke_never_requeues_and_does_not_repeat(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(repair, "run_checks", lambda *a: smoke(False))
    calls = []
    monkeypatch.setattr(repair, "command", lambda argv, *a, **k: calls.append(argv) or 0)
    result = repair.ensure_runner(sys.executable, tmp_path / "a")
    assert result["status"] == "blocked" and not result["auto_retry"]
    assert "requeue" not in result
    repair.ensure_runner(sys.executable, tmp_path / "b")
    assert len(calls) == 3


def test_foreign_module_does_not_launch_runner(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(repair, "run_checks", lambda *a: smoke(False))
    monkeypatch.setattr(repair, "command", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    assert (
        repair.ensure_runner(sys.executable, tmp_path / "a", missing=["target_secret_package"])[
            "status"
        ]
        == "blocked"
    )


def test_install_failure_never_smokes_or_executes(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(repair, "run_checks", lambda *a: smoke(False))
    monkeypatch.setattr(repair, "command", lambda argv, *a, **k: 124 if "pip" in argv else 0)
    result = repair.ensure_runner(sys.executable, tmp_path / "a")
    assert result["status"] == "blocked"
    assert "安装失败" in result["reason"]


def test_wrapper_retries_known_import_failure_once(tmp_path, monkeypatch):
    calls = []

    def ensure(python, output, model, missing=None):
        calls.append(missing)
        Path(output).mkdir(parents=True, exist_ok=True)
        return {
            "status": "ready",
            "python": "/fixed/python" if missing else "/old/python",
            "repaired": bool(missing),
        }

    monkeypatch.setattr(repair, "ensure_runner", ensure)

    def run(argv, log, *a, **k):
        Path(log).write_text(
            "ModuleNotFoundError: No module named 'openai'" if argv[0] == "/old/python" else "ok"
        )
        return 1 if argv[0] == "/old/python" else 0

    monkeypatch.setattr(repair, "command", run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["repair", "--output", str(tmp_path), "--execute-agent", "--", "--project", "demo"],
    )
    assert repair.main() == 0
    assert calls == [None, ["openai"]]
    assert (tmp_path / "execution-first.log").is_file()
    assert (tmp_path / "execution-retry.log").is_file()


def test_version_declaration_rejects_injected_source(tmp_path):
    from validate_requirements import read_packages

    file = tmp_path / "requirements.txt"
    file.write_text(
        "openai>=2 --extra-index-url https://evil.invalid\nopenai @ https://evil.invalid/pkg\n"
    )
    packages, errors = read_packages(file)
    assert not packages and len(errors) == 2


def test_concurrent_missing_dependency_repairs_only_once(tmp_path, monkeypatch):
    import time
    from concurrent.futures import ThreadPoolExecutor

    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(repair, "run_checks", lambda python, *a: smoke("/venv/" in python))
    calls = []

    def run(argv, *a, **k):
        calls.append(argv)
        time.sleep(0.03)
        return 0

    monkeypatch.setattr(repair, "command", run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(repair.ensure_runner, "/old/python", tmp_path / name) for name in ("a", "b")
        ]
        results = [future.result() for future in futures]
    assert all(row["status"] == "ready" for row in results)
    assert len(calls) == 3
