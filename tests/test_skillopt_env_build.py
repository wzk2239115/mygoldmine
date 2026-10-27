from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from integrations.skillopt_env_build.dataloader import format_task_prompt
from integrations.skillopt_env_build.datasets.build_env_dataset import build_dataset
from integrations.skillopt_env_build.runner import RunnerConfig, format_command, run_task
from integrations.skillopt_env_build.scoring import score_manifest


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _manifest(status: str = "ready", image: bool = True, exit_code: int = 0) -> dict:
    return {
        "project": "demo",
        "env_status": status,
        "build_exit_code": exit_code,
        "image_id": "sha256:abc" if image else "",
        "partial_reasons": ["partial"] if status == "partial" else [],
        "limitations": ["gpu not verified"],
    }


def test_score_ready_partial_blocked() -> None:
    ready = score_manifest(_manifest(), {"env_status": "ready", "require_image": True})
    assert ready.hard == 1
    assert ready.soft > 0.9

    partial = score_manifest(_manifest("partial"), {"env_status": "ready"})
    assert partial.hard == 0
    assert 0.4 < partial.soft < 0.8

    blocked = score_manifest(_manifest("blocked", image=False), {"env_status": "ready"})
    assert blocked.hard == 0
    assert blocked.soft == 0.0

    no_image = score_manifest(
        _manifest("ready", image=False), {"env_status": "ready", "require_image": True}
    )
    assert no_image.hard == 0
    assert no_image.soft <= 0.75

    error = score_manifest(
        _manifest(), {"env_status": "ready"}, error="docker build failed"
    )
    assert error.hard == 0
    assert error.soft <= 0.1


def test_format_task_prompt_mentions_contract() -> None:
    prompt = format_task_prompt(
        {"project": "demo", "repo": "targets/demo", "commit": "abc", "mode": "auto"}
    )
    assert "env_status=ready" in prompt
    assert "env/<project>/env-manifest.json" in prompt
    assert "scripts/env/build_env.sh" in prompt


def test_existing_runner_reads_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    env = repo / "env" / "demo"
    _write(env / "env-manifest.json", _manifest())
    task = {"id": "demo", "project": "demo", "repo": "targets/demo", "commit": "abc"}
    run = run_task(
        task,
        "# skill\n",
        tmp_path / "out",
        RunnerConfig(mode="existing", repo_root=repo, env_dir=repo / "env"),
    )
    assert run["manifest"]["env_status"] == "ready"
    assert run["error"] == ""
    score = score_manifest(run["manifest"], {"env_status": "ready"})
    assert score.hard == 1


def test_command_runner_writes_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    script = tmp_path / "writer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "json.dump({'env_status':'ready','build_exit_code':0,"
        "'image_id':'sha256:xyz'}, open(out/'env-manifest.json','w'))\n",
        encoding="utf-8",
    )
    command = [sys.executable, str(script), "{env_dir}"]
    assert format_command(
        command,
        {"project": "demo", "repo": "targets/demo"},
        repo,
        repo / "env" / "demo",
        tmp_path / "skill.md",
    ) == [sys.executable, str(script), str(repo / "env" / "demo")]
    task = {"id": "demo", "project": "demo", "repo": "targets/demo", "commit": "abc"}
    run = run_task(
        task,
        "# skill\n",
        tmp_path / "out",
        RunnerConfig(
            mode="command",
            command=command,
            repo_root=repo,
            env_dir=repo / "env",
            timeout=10,
        ),
    )
    assert run["returncode"] == 0
    assert run["manifest"]["env_status"] == "ready"
    assert run["error"] == ""


def test_build_dataset_splits_by_project(tmp_path: Path) -> None:
    projects = ["a", "b", "c", "d", "e"]
    manifest = {"projects": {}}
    for name in projects:
        target = tmp_path / "targets" / name
        target.mkdir(parents=True)
        manifest["projects"][name] = {
            "status": "ok",
            "path": str(target),
            "commit": f"{name}1234567890",
        }
        _write(
            tmp_path / "env" / name / "env-manifest.json",
            {
                "project": name,
                "env_status": "ready" if name == "a" else "partial",
                "build_exit_code": 0,
                "image_id": "sha256:abc" if name == "a" else "",
                "mode": "auto",
                "partial_reasons": [],
                "limitations": [],
            },
        )
    _write(tmp_path / "targets" / "manifest.json", manifest)
    dataset = build_dataset(
        tmp_path,
        tmp_path / "targets" / "manifest.json",
        tmp_path / "env",
        seed=42,
    )
    assert dataset["counts"] == {"train": 3, "val": 1, "test": 1}
    seen: set[str] = set()
    for split in ("train", "val", "test"):
        names = {item["project"] for item in dataset["splits"][split]}
        assert not (seen & names)
        seen |= names
        for item in dataset["splits"][split]:
            assert item["expected"]["env_status"] == "ready"
            assert item["observed"]["env_status"] in {"ready", "partial"}


def test_adapter_imports_with_skillopt() -> None:
    pytest.importorskip("skillopt")
    from skillopt.envs.base import EnvAdapter

    from integrations.skillopt_env_build.adapter import EnvBuildAdapter

    assert issubclass(EnvBuildAdapter, EnvAdapter)


def test_adapter_rollout_with_existing_manifest(tmp_path: Path) -> None:
    pytest.importorskip("skillopt")
    from integrations.skillopt_env_build.adapter import EnvBuildAdapter

    repo = tmp_path / "repo"
    env = repo / "env" / "demo"
    _write(env / "env-manifest.json", _manifest())
    dataset = {
        "schema": "mygoldmine-rsi-dataset/v1",
        "name": "demo",
        "holdout_key": "project",
        "splits": {
            "train": [
                {
                    "id": "demo@abc",
                    "project": "demo",
                    "repo": "targets/demo",
                    "commit": "abc",
                    "mode": "auto",
                    "task_type": "env_build",
                    "expected": {"env_status": "ready", "require_image": True},
                }
            ],
            "val": [],
            "test": [],
        },
    }
    dataset_path = _write(tmp_path / "dataset.json", dataset)
    adapter = EnvBuildAdapter(
        dataset_path=str(dataset_path),
        runner_mode="existing",
        repo_root=str(repo),
        env_dir=str(repo / "env"),
    )
    adapter.setup({})
    env_manager = adapter.build_train_env(batch_size=1, seed=42)
    results = adapter.rollout(env_manager, "# skill\n", str(tmp_path / "rollout"))
    assert len(results) == 1
    assert results[0]["hard"] == 1
    conversation = (
        tmp_path
        / "rollout"
        / "predictions"
        / "demo_abc"
        / "conversation.json"
    )
    assert conversation.is_file()
    rows = json.loads(conversation.read_text(encoding="utf-8"))
    assert rows[0]["role"] == "system"
    assert rows[0]["content"] == "# skill\n"


def test_build_env_agent_wrapper_uses_candidate_skill(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    fake = tmp_path / "claude"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$CAPTURE\"\n"
        "mkdir -p \"$ENV_BUILD_OUT_DIR\"\n"
        "printf '{\"env_status\":\"ready\",\"build_exit_code\":0,"
        "\"image_id\":\"sha256:abc\"}\\n' "
        "> \"$ENV_BUILD_OUT_DIR/env-manifest.json\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    skill = tmp_path / "skill.md"
    skill.write_text("# candidate skill\n", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    out = tmp_path / "env" / "demo"
    capture = tmp_path / "args.txt"
    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_BIN": str(fake),
            "ENV_BUILDER_SKILL_FILE": str(skill),
            "ENV_BUILD_PROJECT": "demo",
            "ENV_BUILD_REPO": str(source),
            "ENV_BUILD_COMMIT": "abc",
            "ENV_BUILD_MODE": "auto",
            "ENV_BUILD_OUT_DIR": str(out),
            "CAPTURE": str(capture),
        }
    )
    subprocess.run(
        ["bash", str(repo / "scripts" / "env" / "build_env_agent.sh")],
        check=True,
        env=env,
    )
    assert (out / "env-manifest.json").is_file()
    args = capture.read_text(encoding="utf-8")
    assert "--append-system-prompt" in args
    assert "# candidate skill" in args
