import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("submit,model_exit", [(True, 0), (False, 0), (True, 7)])
def test_agent_exit_waits_for_owned_build_then_runs_acceptance_only(tmp_path, submit, model_exit):
    source = tmp_path / "source"
    source.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    fake_root = tmp_path / "fake"
    build = fake_root / "scripts/env/build_env.sh"
    build.parent.mkdir(parents=True)
    build.write_text(
        'sleep 0.4\nprintf build >> "$1/starts"\n'
        'printf \'{"env_status":"partial","image":"fixture:test"}\' '
        '> "$1/env-manifest.json"\nexit 10\n'
    )
    claude = tmp_path / "claude"
    claude.write_text(
        "#!/bin/bash\nset -e\n"
        'if [ "${ENV_BUILD_VERIFY_ONLY:-0}" = 1 ]; then\n'
        ' test -f "$ENV_BUILD_OUT_DIR/env-manifest.json"\n'
        ' printf accepted > "$ENV_BUILD_OUT_DIR/accepted"\n'
        + (
            " python3 - \"$ENV_BUILD_OUT_DIR\" <<'RECEIPT'\n"
            "import json,hashlib,sys\n"
            "from pathlib import Path\n"
            "p=Path(sys.argv[1]);d=p/'.stage-submissions/environment';d.mkdir(parents=True)\n"
            "h=hashlib.sha256((p/'env-manifest.json').read_bytes()).hexdigest()\n"
            "(d/'one.json').write_text(json.dumps({'decision':'accepted','sha256':h}))\n"
            "RECEIPT\n"
            if submit
            else ""
        )
        + "else\n"
        ' node "$REAL_ROOT/ui/server/durable-task.mjs" --start-build '
        '"$FAKE_ROOT" "$ENV_BUILD_OUT_DIR" "$ENV_BUILD_OUT_DIR"\n'
        "fi\n" + f"exit {model_exit}\n"
    )
    claude.chmod(0o755)
    skill = tmp_path / "skill.md"
    skill.write_text("# Test\n")
    env = {
        **os.environ,
        "ENV_BUILDER_SKILL_FILE": str(skill),
        "ENV_BUILD_PROJECT": "demo",
        "ENV_BUILD_REPO": str(source),
        "ENV_BUILD_OUT_DIR": str(out),
        "ENV_BUILD_TIMEOUT": "10",
        "CLAUDE_BIN": str(claude),
        "REAL_ROOT": str(ROOT),
        "FAKE_ROOT": str(fake_root),
    }
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/env/build_env_agent.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == (0 if submit else 6), result.stderr
    assert (out / "accepted").read_text() == "accepted"
    assert (out / "starts").read_text() == "build"
    current = json.loads((out / ".build-tasks/current.json").read_text())
    task = json.loads(Path(current["file"]).read_text())
    assert task["status"] == "completed"
    assert task["exitCode"] == 10


def test_build_hook_requires_durable_entry_point():
    hook = ROOT / ".claude/hooks/environment-build-guard.py"
    for command, denied in [
        ("docker build -t fixture .", True),
        ("docker buildx build .", True),
        ("bash scripts/env/build_env.sh /tmp/source", False),
        ("docker image inspect fixture", False),
    ]:
        result = subprocess.run(
            ["python3", str(hook)],
            input=json.dumps({"tool_input": {"command": command}}),
            text=True,
            capture_output=True,
            check=True,
        )
        assert bool(result.stdout.strip()) is denied
        if denied:
            assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

def test_source_only_mode_does_not_download_rust_toolchain(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "Cargo.toml").write_text('[package]\nname="fixture"\nversion="0.1.0"\n')
    out = tmp_path / "environment"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/env/build_env.sh"), str(source),
         "--project", "fixture", "--env-dir", str(out), "--mode", "none", "--dry-run"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    dockerfile = (out / "Dockerfile").read_text()
    assert "sh.rustup.rs" not in dockerfile
    assert "cargo fetch" not in dockerfile
    assert "apt-get install" not in dockerfile
    manifest = json.loads((out / "env-manifest.json").read_text())
    assert manifest["install_commands"] == []
