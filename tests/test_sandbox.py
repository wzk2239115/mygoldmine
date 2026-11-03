import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts/verify/run_verify.sh"
SANDBOX = ROOT / "scripts/env/sandbox.sh"


def fake_docker(tmp_path, networks="{}", state="running"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    script = bin_dir / "docker"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -uo pipefail\n"
        "printf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"\n"
        "case \"${1:-}\" in\n"
        "  image) echo sha256:fake; exit 0 ;;\n"
        "  ps) exit 0 ;;\n"
        "  container)\n"
        "    case \"${5:-}\" in\n"
        "      *State.Status*) printf '%s\\n' \"$FAKE_STATE\" ;;\n"
        "      *NetworkSettings.Networks*) printf '%s\\n' \"$FAKE_NETWORKS\" ;;\n"
        "    esac\n"
        "    exit 0 ;;\n"
        "  run) exit 0 ;;\n"
        "  exec)\n"
        "    shift\n"
        "    [ \"${1:-}\" = test ] && exit 0\n"
        "    verify_dir=''\n"
        "    while [ \"$#\" -gt 0 ]; do\n"
        "      if [ \"$1\" = -e ] && [[ \"${2:-}\" == VERIFY_DIR=* ]]; then verify_dir=\"${2#VERIFY_DIR=}\"; fi\n"
        "      shift\n"
        "    done\n"
        "    if [ -n \"$verify_dir\" ]; then\n"
        "      mkdir -p \"$verify_dir/evidence\"\n"
        "      printf 'runtime\\n' > \"$verify_dir/evidence/reused.txt\"\n"
        "      printf '{\"verdict\":\"confirmed\",\"reason\":\"reused\",\"evidence_class\":\"runtime\"}\\n' > \"$verify_dir/verdict.json\"\n"
        "    fi\n"
        "    exit 0 ;;\n"
        "  network|stop|rm|start) exit 0 ;;\n"
        "esac\n"
        "exit 0\n"
    )
    script.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "DOCKER_LOG": str(log),
        "FAKE_NETWORKS": networks,
        "FAKE_STATE": state,
    }
    return env, log


def verification_inputs(tmp_path):
    finding = tmp_path / "finding.json"
    finding.write_text('{"id":"F-1","title":"sandbox reuse"}\n')
    harness = tmp_path / "harness.sh"
    harness.write_text("#!/usr/bin/env bash\nexit 0\n")
    return finding, harness


def test_verify_reuses_persistent_workspace_without_docker_run(tmp_path):
    env, log = fake_docker(tmp_path)
    finding, harness = verification_inputs(tmp_path)
    run_dir = tmp_path / "run/verify/case"
    result = subprocess.run(
        [
            "bash", str(VERIFY), "--project", "demo", "--image", "demo:image",
            "--finding", str(finding), "--harness", str(harness),
            "--run-dir", str(run_dir), "--sandbox", "sandbox-demo", "--timeout", "30",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert "exec --workdir /workspace/repo" in commands
    assert "TARGET_DIR=/workspace/repo" in commands
    assert "docker run" not in commands
    report = json.loads((run_dir / "verify-report.json").read_text())
    assert report["verdict"] == "confirmed"


def test_verify_rejects_networked_sandbox_for_offline_mode(tmp_path):
    env, log = fake_docker(tmp_path, networks='{"bridge":{}}')
    finding, harness = verification_inputs(tmp_path)
    result = subprocess.run(
        [
            "bash", str(VERIFY), "--project", "demo", "--image", "demo:image",
            "--finding", str(finding), "--harness", str(harness),
            "--run-dir", str(tmp_path / "run/verify/case"),
            "--sandbox", "sandbox-demo", "--network", "none",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 30
    assert "sandbox.sh isolate" in result.stderr


def test_sandbox_start_preserves_source_boundary_and_writes_no_credentials(tmp_path):
    env, log = fake_docker(tmp_path, state="")
    source = tmp_path / "source"
    source.mkdir()
    run_dir = tmp_path / "run"
    result = subprocess.run(
        [
            "bash", str(SANDBOX), "start", "--project", "demo", "--run-dir", str(run_dir),
            "--source", str(source), "--image", "demo:image",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert "run -d" in commands
    assert "dst=/target,readonly" in commands
    assert "--cap-drop ALL" in commands
    assert "ANTHROPIC" not in commands
    state = json.loads((tmp_path / "run.meta/sandbox.json").read_text())
    assert state["container"].startswith("mygoldmine-sandbox-demo-")
    assert state["image"] == "demo:image"


def test_prepared_entrypoint_preserves_workspace_edits(tmp_path):
    source = tmp_path / 'source'
    work = tmp_path / 'work'
    home = tmp_path / 'framework'
    bin_dir = tmp_path / 'bin'
    for directory in [source, work, home / 'scripts/mine', home / '.claude', bin_dir]:
        directory.mkdir(parents=True)
    (source / 'code.txt').write_text('original')
    (work / 'code.txt').write_text('edited by audit')
    (work / 'evidence.txt').write_text('preserve evidence')
    Path(f'{work}.mygoldmine-ready').touch()
    executor = home / 'scripts/mine/mine_one.sh'
    executor.write_text('#!/bin/bash\nexit 0\n')
    executor.chmod(0o755)
    claude = bin_dir / 'claude'
    claude.write_text('#!/bin/bash\nexit 91\n')
    claude.chmod(0o755)
    env = {**os.environ, 'MYGOLDMINE_HOME': str(home), 'TARGET_DIR': str(source),
           'WORK_DIR': str(work), 'RUN_DIR': str(tmp_path / 'run'),
           'WORKSPACE_PREPARED': '1', 'ANTHROPIC_AUTH_TOKEN': 'test-only',
           'ALLOW_DOCKER_SOCKET': '1',
           'PATH': f"{bin_dir}:{os.environ['PATH']}"}
    result = subprocess.run(['bash', str(ROOT / 'scripts/mine/entrypoint.sh')], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (work / 'code.txt').read_text() == 'edited by audit'
    assert (work / 'evidence.txt').exists()
    assert (source / 'code.txt').read_text() == 'original'


def test_start_rejects_unprepared_existing_sandbox(tmp_path):
    env, log = fake_docker(tmp_path)
    docker = tmp_path / 'bin/docker'
    script = docker.read_text().replace('  exec)\n', '  exec)\n    if [[ "$*" == *"test -f /workspace/repo.mygoldmine-ready"* ]]; then exit 1; fi\n')
    docker.write_text(script)
    source = tmp_path / 'source'
    source.mkdir()
    result = subprocess.run(['bash', str(SANDBOX), 'start', '--project', 'demo',
                             '--run-dir', str(tmp_path / 'run'), '--source', str(source), '--image', 'demo:image'],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 5, result.stderr
    assert '未完成准备' in result.stderr
    assert not (tmp_path / 'run.meta/sandbox.json').exists()
    assert 'cp -a' not in log.read_text()


def test_failed_copy_does_not_publish_ready_state(tmp_path):
    env, log = fake_docker(tmp_path, state='')
    docker = tmp_path / 'bin/docker'
    docker.write_text(docker.read_text().replace('  exec)\n', '  exec)\n    if [[ "$*" == *"cp -a /target/."* ]]; then exit 1; fi\n'))
    source = tmp_path / 'source'
    source.mkdir()
    result = subprocess.run(['bash', str(SANDBOX), 'start', '--project', 'demo',
                             '--run-dir', str(tmp_path / 'run'), '--source', str(source), '--image', 'demo:image'],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 5, result.stderr
    assert '源码复制失败' in result.stderr
    assert not (tmp_path / 'run.meta/sandbox.json').exists()
    assert 'stop --time 20' in log.read_text()
