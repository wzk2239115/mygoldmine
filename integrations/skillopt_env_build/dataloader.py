from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from skillopt.datasets.base import SplitDataLoader as _SplitDataLoader
except ImportError:
    _SplitDataLoader = object

from rsi_version.schema import validate_dataset


def load_dataset(path: str | Path) -> dict[str, Any]:
    dataset = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_dataset(dataset)
    if errors:
        raise ValueError("invalid env-build dataset: " + "; ".join(errors))
    return dataset


def get_tasks(dataset: dict[str, Any], split: str) -> list[dict[str, Any]]:
    return list(dataset.get("splits", {}).get(split, []))


def format_task_prompt(task: dict[str, Any]) -> str:
    return (
        "Build a reproducible Docker environment for this source repository.\n\n"
        f"project: {task.get('project', '')}\n"
        f"repo: {task.get('repo', '')}\n"
        f"commit: {task.get('commit', '')}\n"
        f"mode: {task.get('mode', 'auto')}\n\n"
        "Goal: produce env/<project>/env-manifest.json with env_status=ready, "
        "build_exit_code=0, and a non-empty image_id from a real Docker build.\n"
        "Use scripts/env/build_env.sh for detection, generation, build, and "
        "verification. Keep partial/blocked honest if the environment cannot "
        "be made ready. Do not run target code on the host.\n"
    )


class EnvBuildDataLoader(_SplitDataLoader):
    def __init__(
        self,
        dataset_path: str = "",
        limit: int = 0,
        **kwargs: Any,
    ) -> None:
        if _SplitDataLoader is not object:
            super().__init__(limit=limit, **kwargs)
        self.dataset_path = dataset_path
        self.limit = int(limit or 0)
        self._splits: dict[str, list[dict[str, Any]]] = {}

    def setup(self, cfg: dict) -> None:
        if not self.dataset_path:
            self.dataset_path = str(cfg.get("dataset_path", "") or "")
        if not self.dataset_path:
            raise ValueError("EnvBuildDataLoader requires dataset_path")
        dataset = load_dataset(self.dataset_path)
        self._splits = {
            split: list(items) for split, items in dataset.get("splits", {}).items()
        }
        for split in ("train", "val", "test"):
            self._splits.setdefault(split, [])
            if self.limit:
                self._splits[split] = self._splits[split][: self.limit]
        if not self._splits["train"]:
            raise ValueError("env-build dataset has an empty train split")

    def get_split_items(self, split: str) -> list[dict[str, Any]]:
        canonical = {
            "valid_seen": "val",
            "selection": "val",
            "valid_unseen": "test",
        }.get(split, split)
        return list(self._splits.get(canonical, []))

    @property
    def train_items(self) -> list[dict[str, Any]]:
        return self._splits.get("train", [])

    @property
    def val_items(self) -> list[dict[str, Any]]:
        return self._splits.get("val", [])

    @property
    def test_items(self) -> list[dict[str, Any]]:
        return self._splits.get("test", [])

    def get_train_size(self) -> int:
        return len(self.train_items)
