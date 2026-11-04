from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE0 = REPO_ROOT / "scripts" / "env" / "phase0_env.sh"


def _write_executable(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _fake_baseline(tmp_path: Path) -> Path:
    return _write_executable(
        tmp_path / "baseline.sh",
        """#!/usr/bin/env bash
set -eu
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --env-dir) out="$2"; shift ;;
  esac
  shift
done
mkdir -p "$out"
printf 'FROM baseline\\n' > "$out/Dockerfile"
printf 'baseline log\\n' > "$out/build.log"
cat > "$out/env-manifest.json" <<'JSON'
{"project":"demo","env_status":"partial","image":"fake:demo","build_exit_code":0,"partial_reasons":["baseline is partial"],"limitations":[]}
JSON
exit 10
""",
    )


def _fake_agent(tmp_path: Path, *, status: str = "ready") -> Path:
    return _write_executable(
        tmp_path / "agent.sh",
        f"""#!/usr/bin/env bash
set -eu
out="$ENV_BUILD_OUT_DIR"
mkdir -p "$out"
printf 'FROM improved\\n' > "$out/Dockerfile"
printf 'agent log\\n' >> "$out/build.log"
cat > "$out/env-manifest.json" <<'JSON'
{{"project":"demo","env_status":"{status}","image":"fake:demo-agent","build_exit_code":0,"partial_reasons":[],"limitations":[]}}
JSON
exit 0
""",
    )


def _run_phase0(
    tmp_path: Path,
    *,
    agent: str = "on",
    baseline: Path,
    agent_script: Path,
    claude_bin: str = "bash",
) -> subprocess.CompletedProcess[str]:
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    skill = tmp_path / "skill.md"
    skill.write_text("# environment skill\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "BUILD_ENV_SCRIPT": str(baseline),
            "BUILD_ENV_AGENT_SCRIPT": str(agent_script),
            "ENV_SKIP_IMAGE_CHECK": "1",
        }
    )
    return subprocess.run(
        [
            "bash", str(PHASE0), str(source),
            "--project", "demo", "--mode", "auto",
            "--meta-dir", str(tmp_path / "meta"),
            "--env-root", str(tmp_path / "env"),
            "--agent", agent, "--agent-timeout", "10", "--agent-rounds", "1",
            "--skill", str(skill), "--claude-bin", claude_bin,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _manifest(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "env" / "demo" / "env-manifest.json").read_text(encoding="utf-8"))


def _phase(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "meta" / "env-phase.json").read_text(encoding="utf-8"))


def test_phase0_agent_runs_first_and_uses_its_environment(tmp_path: Path) -> None:
    result = _run_phase0(
        tmp_path,
        agent="on",
        baseline=_fake_baseline(tmp_path),
        agent_script=_fake_agent(tmp_path, status="ready"),
    )
    assert result.returncode == 0, result.stderr
    assert _manifest(tmp_path)["env_status"] == "ready"
    assert "improved" in (tmp_path / "env" / "demo" / "Dockerfile").read_text(encoding="utf-8")
    assert not (tmp_path / "meta" / "env-build.log").exists()
    phase = _phase(tmp_path)
    assert phase["baseline"]["status"] == "not_run"
    assert phase["baseline"]["exit_code"] is None
    assert phase["agent"]["status"] == "ready"
    assert phase["agent"]["reason"] == "agent_primary"
    assert phase["agent"]["prerequisites"]["claude_available"] is True
    assert phase["agent"]["prerequisites"]["missing"] == []
    assert phase["final"]["status"] == "ready"


def test_phase0_uses_baseline_fallback_when_agent_breaks_image(tmp_path: Path) -> None:
    result = _run_phase0(
        tmp_path,
        agent="on",
        baseline=_fake_baseline(tmp_path),
        agent_script=_fake_agent(tmp_path, status="blocked"),
    )
    assert result.returncode == 10, result.stderr
    assert _manifest(tmp_path)["env_status"] == "partial"
    assert "baseline" in (tmp_path / "env" / "demo" / "Dockerfile").read_text(encoding="utf-8")
    phase = _phase(tmp_path)
    assert phase["baseline"]["status"] == "partial"
    assert phase["agent"]["status"] == "failed_fallback"
    assert phase["agent"]["reason"] == "fallback_baseline"
    assert phase["final"]["status"] == "partial"


def test_phase0_auto_still_runs_agent_when_baseline_could_be_ready(tmp_path: Path) -> None:
    baseline = _write_executable(
        tmp_path / "baseline-ready.sh",
        """#!/usr/bin/env bash
set -eu
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in --env-dir) out="$2"; shift ;; esac
  shift
done
mkdir -p "$out"
printf 'FROM baseline\\n' > "$out/Dockerfile"
cat > "$out/env-manifest.json" <<'JSON'
{"project":"demo","env_status":"ready","image":"fake:demo","build_exit_code":0,"partial_reasons":[],"limitations":[]}
JSON
exit 0
""",
    )
    result = _run_phase0(
        tmp_path,
        agent="auto",
        baseline=baseline,
        agent_script=_fake_agent(tmp_path, status="ready"),
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "meta" / "env-build-agent-1.log").exists()
    assert not (tmp_path / "meta" / "env-build.log").exists()
    phase = _phase(tmp_path)
    assert phase["baseline"]["status"] == "not_run"
    assert phase["agent"]["status"] == "ready"
    assert phase["agent"]["reason"] == "agent_primary"


def test_phase0_reports_missing_prerequisites_at_runtime(tmp_path: Path) -> None:
    result = _run_phase0(
        tmp_path,
        agent="on",
        baseline=_fake_baseline(tmp_path),
        agent_script=_fake_agent(tmp_path, status="ready"),
        claude_bin="/definitely/missing/claude",
    )
    assert result.returncode == 10, result.stderr
    phase = _phase(tmp_path)
    assert phase["agent"]["status"] == "skipped_unavailable"
    assert phase["agent"]["reason"] == "missing_prerequisites"
    assert phase["agent"]["prerequisites"]["claude_available"] is False
    assert "claude" in phase["agent"]["prerequisites"]["missing"]
    assert not (tmp_path / "meta" / "env-build-agent-1.log").exists()


def test_phase0_agent_off_runs_only_deterministic_fallback(tmp_path: Path) -> None:
    result = _run_phase0(
        tmp_path,
        agent="off",
        baseline=_fake_baseline(tmp_path),
        agent_script=_fake_agent(tmp_path, status="ready"),
    )
    assert result.returncode == 10, result.stderr
    assert not (tmp_path / "meta" / "env-build-agent-1.log").exists()
    assert (tmp_path / "meta" / "env-build.log").exists()
    phase = _phase(tmp_path)
    assert phase["baseline"]["status"] == "partial"
    assert phase["agent"]["status"] == "off"
    assert phase["agent"]["reason"] == "disabled"
    assert phase["final"]["status"] == "partial"


def test_phase0_snapshots_capabilities_without_promoting_partial(tmp_path: Path) -> None:
    agent = _fake_agent(tmp_path, status="partial")
    text = agent.read_text().replace('"partial_reasons":[],"limitations":[]',
        '"partial_reasons":["GPU 未验证"],"limitations":["仅支持 CPU"],'
        '"platform":{"torch":"2.13.0+cpu"},"acceptance":[{"check":"CPU","exit_code":0}]')
    agent.write_text(text)
    result = _run_phase0(tmp_path, baseline=_fake_baseline(tmp_path), agent_script=agent)
    assert result.returncode == 10, result.stderr
    snapshot = _phase(tmp_path)["final"]["capabilities"]
    assert _phase(tmp_path)["final"]["status"] == "partial"
    assert snapshot["platform"]["torch"] == "2.13.0+cpu"
    assert snapshot["acceptance"] == [{"check": "CPU", "exit_code": 0}]
    assert snapshot["limitations"] == ["仅支持 CPU"]
    (tmp_path / "env/demo/env-manifest.json").write_text('{}')
    assert _phase(tmp_path)["final"]["capabilities"] == snapshot
