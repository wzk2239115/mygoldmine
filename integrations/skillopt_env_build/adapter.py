from __future__ import annotations

import concurrent.futures
import json
import re
from pathlib import Path
from typing import Any

try:
    from skillopt.datasets.base import BatchSpec
    from skillopt.envs.base import EnvAdapter
except ImportError as exc:
    raise ImportError(
        "SkillOpt is required for this adapter. Set SKILLOPT_ROOT or install "
        "the skillopt package."
    ) from exc

from .dataloader import EnvBuildDataLoader, format_task_prompt
from .runner import RunnerConfig, run_task
from .scoring import score_manifest

_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


class EnvBuildAdapter(EnvAdapter):
    def __init__(
        self,
        dataset_path: str = "",
        runner_mode: str = "existing",
        runner_command: str = "",
        repo_root: str = ".",
        env_dir: str = "env",
        timeout: int = 3600,
        workers: int = 4,
        limit: int = 0,
        analyst_workers: int = 4,
        failure_only: bool = False,
        minibatch_size: int = 4,
        edit_budget: int = 3,
        **kwargs: Any,
    ) -> None:
        self.dataset_path = dataset_path
        self.runner_mode = runner_mode
        self.runner_command = runner_command
        self.repo_root = repo_root
        self.env_dir = env_dir
        self.timeout = int(timeout)
        self.workers = max(1, int(workers))
        self.limit = int(limit)
        self.analyst_workers = max(1, int(analyst_workers))
        self.failure_only = bool(failure_only)
        self.minibatch_size = max(1, int(minibatch_size))
        self.edit_budget = max(1, int(edit_budget))
        self.dataloader = EnvBuildDataLoader(
            dataset_path=dataset_path,
            limit=limit,
        )
        self.runner_config = RunnerConfig(
            mode=runner_mode,
            command=runner_command,
            timeout=self.timeout,
            repo_root=repo_root,
            env_dir=env_dir,
        )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        if cfg.get("dataset_path"):
            self.dataset_path = str(cfg["dataset_path"])
            self.dataloader.dataset_path = self.dataset_path
        self.dataloader.setup(cfg)
        self.analyst_workers = max(
            1, int(cfg.get("analyst_workers", self.analyst_workers))
        )
        self.failure_only = bool(cfg.get("failure_only", self.failure_only))
        self.minibatch_size = max(
            1, int(cfg.get("minibatch_size", self.minibatch_size))
        )
        self.edit_budget = max(1, int(cfg.get("edit_budget", self.edit_budget)))
        self.runner_config.mode = str(cfg.get("runner_mode", self.runner_mode))
        self.runner_config.command = str(
            cfg.get("runner_command", self.runner_command)
        )
        self.runner_config.timeout = int(cfg.get("timeout", self.timeout))
        self.runner_config.repo_root = str(cfg.get("repo_root", self.repo_root))
        self.runner_config.env_dir = str(cfg.get("env_dir", self.env_dir))

    def get_dataloader(self) -> EnvBuildDataLoader:
        return self.dataloader

    def build_train_env(self, batch_size: int, seed: int, **kwargs: Any):
        batch: BatchSpec = self.dataloader.build_train_batch(
            batch_size=batch_size, seed=seed, **kwargs
        )
        return list(batch.payload or [])

    def build_eval_env(
        self, env_num: int, split: str, seed: int, **kwargs: Any
    ):
        batch: BatchSpec = self.dataloader.build_eval_batch(
            env_num=env_num, split=split, seed=seed, **kwargs
        )
        return list(batch.payload or [])

    def rollout(
        self,
        env_manager,
        skill_content: str,
        out_dir: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        items = list(env_manager or [])
        if not items:
            return []
        output = Path(out_dir)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.workers
        ) as executor:
            futures = [
                executor.submit(
                    self._run_one,
                    task,
                    skill_content,
                    output,
                )
                for task in items
            ]
            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(
                        {
                            "id": "unknown",
                            "hard": 0,
                            "soft": 0.0,
                            "predicted_answer": "",
                            "task_description": "",
                            "task_type": "env_build",
                            "fail_reason": repr(exc),
                        }
                    )
        results.sort(key=lambda row: str(row.get("id", "")))
        return results

    def _run_one(
        self,
        task: dict[str, Any],
        skill_content: str,
        out_dir: Path,
    ) -> dict[str, Any]:
        task_id = str(task.get("id", "task"))
        safe_id = _SAFE_ID.sub("_", task_id)
        task_dir = out_dir / "predictions" / safe_id
        run = run_task(task, skill_content, task_dir, self.runner_config)
        score = score_manifest(
            run.get("manifest"),
            task.get("expected"),
            error=str(run.get("error", "")),
            timed_out=bool(run.get("timed_out", False)),
        )
        prompt = format_task_prompt(task)
        manifest = run.get("manifest") or {}
        summary = {
            "env_status": manifest.get("env_status", "unknown"),
            "build_exit_code": manifest.get("build_exit_code"),
            "manifest_path": run.get("manifest_path", ""),
            "error": run.get("error", ""),
            "timed_out": run.get("timed_out", False),
            "score": score.detail,
        }
        assistant = json.dumps(summary, ensure_ascii=False, indent=2)
        if run.get("stdout"):
            assistant += "\n\nSTDOUT (tail):\n" + run["stdout"]
        if run.get("stderr"):
            assistant += "\n\nSTDERR (tail):\n" + run["stderr"]
        conversation = [
            {"role": "system", "content": skill_content},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": assistant},
        ]
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "conversation.json").write_text(
            json.dumps(conversation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        status = str(manifest.get("env_status", "unknown"))
        fail_reason = ""
        if score.hard == 0:
            fail_reason = (
                f"env_status={status}, exit={manifest.get('build_exit_code')}, "
                f"image_id={bool(manifest.get('image_id'))}, "
                f"error={run.get('error', '')}"
            )
        return {
            "id": task_id,
            "hard": score.hard,
            "soft": score.soft,
            "predicted_answer": assistant,
            "task_description": prompt,
            "question": prompt,
            "task_type": "env_build",
            "target_system_prompt": skill_content,
            "target_user_prompt": prompt,
            "n_turns": 1,
            "fail_reason": fail_reason,
            "env_status": status,
            "manifest_path": run.get("manifest_path", ""),
            "returncode": run.get("returncode"),
            "timed_out": run.get("timed_out", False),
            "duration_ms": run.get("duration_ms", 0),
        }

    def get_task_types(self) -> list[str]:
        return ["env_build"]
