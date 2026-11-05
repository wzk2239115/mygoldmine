import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "runner" / "smoke_runner.py"
VALIDATE = ROOT / "scripts" / "runner" / "validate_requirements.py"
BUILD = ROOT / "scripts" / "runner" / "build_runner.sh"


def run(command):
    return subprocess.run(command, capture_output=True, text=True, cwd=ROOT)


def test_smoke_runner_accepts_present_modules_and_commands():
    completed = run([
        sys.executable, str(SMOKE),
        "--module", "json",
        "--module", "sys",
        "--command", f"{sys.executable} --version",
        "--json",
    ])
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert [item["status"] for item in payload["modules"]] == ["ok", "ok"]


def test_smoke_runner_reports_missing_module():
    completed = run([
        sys.executable, str(SMOKE),
        "--module", "definitely_missing_runner_module",
        "--json",
    ])
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["modules"][0]["status"] == "missing"


def test_runner_requirements_are_in_allowlist():
    completed = run([sys.executable, str(VALIDATE), "--json"])
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["ok"] is True


def test_runner_requirements_reject_unlisted_and_remote_sources(tmp_path):
    requirements = tmp_path / "requirements.txt"
    allowlist = tmp_path / "allowed.txt"
    requirements.write_text("openai>=2,<3\nunlisted-package\n", encoding="utf-8")
    allowlist.write_text("openai\n", encoding="utf-8")
    completed = run([
        sys.executable, str(VALIDATE),
        "--requirements", str(requirements),
        "--allowlist", str(allowlist),
        "--json",
    ])
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert any("不在允许清单" in item for item in payload["errors"])

    requirements.write_text("git+https://example.com/package.git\n", encoding="utf-8")
    completed = run([
        sys.executable, str(VALIDATE),
        "--requirements", str(requirements),
        "--allowlist", str(allowlist),
        "--json",
    ])
    assert completed.returncode == 2
    assert any("不是普通包声明" in item for item in json.loads(completed.stdout)["errors"])


def test_runner_build_dry_run_does_not_require_docker():
    completed = run([
        "bash", str(BUILD),
        "--dry-run",
        "--skip-validation",
        "--image", "fixture/runner:test",
    ])
    assert completed.returncode == 0
    assert "docker build" in completed.stdout
    assert "smoke_runner.py" in completed.stdout
    assert "fixture/runner:test-candidate-" in completed.stdout
