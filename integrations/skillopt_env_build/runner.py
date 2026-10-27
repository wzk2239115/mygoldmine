from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RunnerConfig:
    mode: str = "existing"
    command: str = ""
    timeout: int = 3600
    repo_root: str | Path = "."
    env_dir: str | Path = "env"
    max_log_chars: int = 4000


def resolve_repo(repo_root: Path, task: dict[str, Any]) -> Path:
    repo = Path(str(task.get("repo", "")))
    if not repo.is_absolute():
        repo = repo_root / repo
    return repo.resolve()


def resolve_env_dir(repo_root: Path, env_dir: str | Path, task: dict[str, Any]) -> Path:
    base = Path(env_dir)
    if not base.is_absolute():
        base = repo_root / base
    return base / str(task.get("project", ""))


def format_command(
    command: str | list[str],
    task: dict[str, Any],
    repo_root: Path,
    env_dir: Path,
    skill_file: Path,
) -> list[str]:
    parts = shlex.split(command) if isinstance(command, str) else list(command)
    values = {
        "repo": str(resolve_repo(repo_root, task)),
        "project": str(task.get("project", "")),
        "commit": str(task.get("commit", "")),
        "mode": str(task.get("mode", "auto")),
        "env_dir": str(env_dir),
        "skill_file": str(skill_file),
    }
    return [part.format(**values) for part in parts]


def _read_manifest(env_project_dir: Path) -> tuple[dict[str, Any], str]:
    path = env_project_dir / "env-manifest.json"
    if not path.is_file():
        return {}, str(path)
    try:
        return json.loads(path.read_text(encoding="utf-8")), str(path)
    except (OSError, json.JSONDecodeError):
        return {}, str(path)


def _tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_task(
    task: dict[str, Any],
    skill_content: str,
    out_dir: str | Path,
    config: RunnerConfig,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    skill_file = out / "skill.md"
    skill_file.write_text(skill_content, encoding="utf-8")
    repo_root = Path(config.repo_root).resolve()
    env_project_dir = resolve_env_dir(repo_root, config.env_dir, task)
    started = time.time()
    returncode = 0
    stdout = ""
    stderr = ""
    timed_out = False
    error = ""

    if config.mode == "command":
        if not config.command:
            error = "runner_command is empty"
        else:
            command = format_command(
                config.command,
                task,
                repo_root,
                env_project_dir,
                skill_file,
            )
            env = os.environ.copy()
            env.update(
                {
                    "ENV_BUILDER_SKILL_FILE": str(skill_file),
                    "ENV_BUILD_PROJECT": str(task.get("project", "")),
                    "ENV_BUILD_REPO": str(resolve_repo(repo_root, task)),
                    "ENV_BUILD_COMMIT": str(task.get("commit", "")),
                    "ENV_BUILD_MODE": str(task.get("mode", "auto")),
                    "ENV_BUILD_OUT_DIR": str(env_project_dir),
                }
            )
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(repo_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=config.timeout,
                    check=False,
                )
                returncode = completed.returncode
                stdout = completed.stdout
                stderr = completed.stderr
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                returncode = 124
                error = f"timeout after {config.timeout}s"
                stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
                stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            except (OSError, ValueError) as exc:
                returncode = 127
                error = repr(exc)
    elif config.mode != "existing":
        error = f"unknown runner mode: {config.mode}"

    manifest, manifest_path = _read_manifest(env_project_dir)
    if not manifest and not error:
        error = f"manifest not found: {manifest_path}"
    if returncode != 0 and not error:
        error = f"command exited {returncode}"

    return {
        "task": task,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "returncode": returncode,
        "stdout": _tail(stdout, config.max_log_chars),
        "stderr": _tail(stderr, config.max_log_chars),
        "timed_out": timed_out,
        "error": error,
        "duration_ms": int((time.time() - started) * 1000),
    }
