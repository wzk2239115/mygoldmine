#!/usr/bin/env python3
"""Build a versioned environment-build task dataset from targets/ and env/."""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rsi_version.schema import DATASET_SCHEMA, validate_dataset


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _split(projects: list[str], seed: int) -> dict[str, list[str]]:
    ordered = sorted(projects)
    random.Random(seed).shuffle(ordered)
    total = len(ordered)
    if total == 0:
        return {"train": [], "val": [], "test": []}
    if total < 3:
        return {"train": ordered, "val": [], "test": []}
    test_count = max(1, round(total * 0.2))
    val_count = max(1, round(total * 0.2))
    train_count = total - test_count - val_count
    if train_count < 1:
        train_count = 1
        if val_count > test_count:
            val_count = max(0, total - train_count - test_count)
        else:
            test_count = max(0, total - train_count - val_count)
    return {
        "train": ordered[:train_count],
        "val": ordered[train_count : train_count + val_count],
        "test": ordered[train_count + val_count :],
    }


def build_dataset(
    repo_root: Path,
    targets_manifest: Path,
    env_dir: Path,
    seed: int = 42,
    include_missing: bool = False,
) -> dict[str, Any]:
    manifest = _load(targets_manifest, {})
    projects = manifest.get("projects", {}) if isinstance(manifest, dict) else {}
    tasks: dict[str, dict[str, Any]] = {}
    for project, entry in projects.items():
        if entry.get("status", "ok") != "ok":
            continue
        source = Path(entry.get("path") or repo_root / "targets" / project)
        if not source.exists():
            continue
        env_manifest_path = env_dir / project / "env-manifest.json"
        observed = _load(env_manifest_path, {})
        if not observed and not include_missing:
            continue
        task_id = f"{project}@{str(entry.get('commit') or 'unknown')[:8]}"
        tasks[project] = {
            "id": task_id,
            "project": project,
            "repo": _relative(repo_root, source),
            "commit": str(entry.get("commit") or ""),
            "mode": str(observed.get("mode") or "auto"),
            "task_type": "env_build",
            "expected": {
                "env_status": "ready",
                "require_image": True,
                "require_build_exit_code": 0,
            },
            "observed": {
                "env_status": observed.get("env_status", "unknown"),
                "build_exit_code": observed.get("build_exit_code"),
                "has_image_id": bool(observed.get("image_id")),
                "partial_reasons": observed.get("partial_reasons", []),
                "limitations": observed.get("limitations", []),
                "manifest": _relative(repo_root, env_manifest_path),
            },
            "provenance": {
                "source": "targets/manifest.json + env/<project>/env-manifest.json",
                "label": "goal: reproducible ready image",
            },
        }

    split_projects = _split(list(tasks), seed)
    splits: dict[str, list[dict[str, Any]]] = {}
    for split, names in split_projects.items():
        splits[split] = [tasks[name] for name in names]
    return {
        "schema": DATASET_SCHEMA,
        "name": "mygoldmine_env_build",
        "holdout_key": "project",
        "splits": splits,
        "counts": {name: len(items) for name, items in splits.items()},
        "source": "targets/manifest.json",
        "split_seed": seed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": (
            "Tasks are goal-labeled: expected env_status=ready. The observed "
            "block records the current env manifest for debugging, not the label."
        ),
    }


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--targets-manifest", default="")
    parser.add_argument("--env-dir", default="")
    parser.add_argument(
        "--out",
        default=str(
            REPO_ROOT / "integrations" / "skillopt_env_build" / "datasets"
            / "env_build_v0.json"
        ),
    )
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--include-missing", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    targets_manifest = Path(
        args.targets_manifest or repo_root / "targets" / "manifest.json"
    )
    env_dir = Path(args.env_dir or repo_root / "env")
    dataset = build_dataset(
        repo_root,
        targets_manifest,
        env_dir,
        seed=args.split_seed,
        include_missing=args.include_missing,
    )
    errors = validate_dataset(dataset)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(out), "counts": dataset["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
