from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION_SCHEMA = "mygoldmine-rsi-version/v1"
CURRENT_SCHEMA = "mygoldmine-rsi-current/v1"
STAGE_SCHEMA = "mygoldmine-rsi-stage/v1"
DATASET_SCHEMA = "mygoldmine-rsi-dataset/v1"
EVAL_SCHEMA = "mygoldmine-rsi-eval/v1"
GATE_SCHEMA = "mygoldmine-rsi-gate/v1"
PROVENANCE_SCHEMA = "mygoldmine-rsi-provenance/v1"

STAGES = ("env", "audit", "review")
SPLITS = ("train", "val", "test")
STAGE_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
VERSION_RE = re.compile(r"^[0-9a-f]{64}$")
TAG_RE = re.compile(r"^rsi/[a-z][a-z0-9_-]*/v[0-9]{3,}$")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dataset_hash(dataset: dict[str, Any]) -> str:
    return sha256_text(canonical_json(dataset))


def git_info(repo_root: str | Path) -> tuple[str, bool | None]:
    root = str(repo_root)
    try:
        commit = subprocess.check_output(
            ["git", "-C", root, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = ""
    try:
        dirty = subprocess.check_output(
            ["git", "-C", root, "status", "--porcelain", "--untracked-files=normal"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty_value: bool | None = bool(dirty)
    except (OSError, subprocess.CalledProcessError):
        dirty_value = None
    return commit, dirty_value


def _item_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return text or None


def validate_dataset(
    dataset: dict[str, Any],
    *,
    strict_holdout: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(dataset, dict):
        return ["dataset must be a JSON object"]
    if dataset.get("schema") != DATASET_SCHEMA:
        errors.append(f"dataset.schema must be {DATASET_SCHEMA!r}")
    splits = dataset.get("splits")
    if not isinstance(splits, dict):
        return errors + ["dataset.splits must be an object"]
    unknown = sorted(set(splits) - set(SPLITS))
    if unknown:
        errors.append(f"unknown splits: {unknown}")
    seen_ids: dict[str, str] = {}
    holdout_key = dataset.get("holdout_key")
    holdout_values: dict[str, set[str]] = {name: set() for name in SPLITS}
    for split in SPLITS:
        items = splits.get(split, [])
        if not isinstance(items, list):
            errors.append(f"split {split!r} must be a list")
            continue
        for index, item in enumerate(items):
            item_id = _item_id(item)
            if item_id is None:
                errors.append(f"{split}[{index}] missing string/integer id")
                continue
            if item_id in seen_ids:
                errors.append(
                    f"duplicate id {item_id!r} in {split} and {seen_ids[item_id]}"
                )
            else:
                seen_ids[item_id] = split
            if strict_holdout and holdout_key:
                if not isinstance(item, dict) or holdout_key not in item:
                    errors.append(
                        f"{split}[{index}] missing holdout key {holdout_key!r}"
                    )
                else:
                    holdout_values[split].add(str(item[holdout_key]))
    if strict_holdout and holdout_key:
        for left in SPLITS:
            for right in SPLITS:
                if left >= right:
                    continue
                overlap = holdout_values[left] & holdout_values[right]
                if overlap:
                    errors.append(
                        f"holdout {holdout_key!r} overlaps {left}/{right}: "
                        f"{sorted(overlap)}"
                    )
    counts = dataset.get("counts")
    if counts is not None:
        if not isinstance(counts, dict):
            errors.append("dataset.counts must be an object")
        else:
            for split in SPLITS:
                items = splits.get(split, [])
                if split in counts and counts[split] != len(items):
                    errors.append(
                        f"counts[{split}]={counts[split]} but split has {len(items)}"
                    )
    return errors


def default_dataset(name: str = "empty") -> dict[str, Any]:
    return {
        "schema": DATASET_SCHEMA,
        "name": name,
        "holdout_key": "project",
        "splits": {"train": [], "val": [], "test": []},
        "counts": {"train": 0, "val": 0, "test": 0},
        "notes": "seed dataset; populate from real runs before training",
    }


def default_eval() -> dict[str, Any]:
    return {
        "schema": EVAL_SCHEMA,
        "n_tasks": 0,
        "hard": None,
        "soft": None,
        "cost": {},
        "per_task": [],
        "notes": "seed version; no evaluation yet",
    }


def default_gate() -> dict[str, Any]:
    return {
        "schema": GATE_SCHEMA,
        "status": "seed",
        "accepted": True,
        "metric": "seed",
        "baseline": None,
        "candidate": None,
        "no_regression": True,
        "notes": "initial seed skill",
    }


def default_provenance(
    operator: str,
    git_commit: str,
    git_dirty: bool | None,
    optimizer_model: str = "",
    target_model: str = "",
) -> dict[str, Any]:
    return {
        "schema": PROVENANCE_SCHEMA,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "operator": operator,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "models": {
            "optimizer": optimizer_model,
            "target": target_model,
        },
        "run_ids": [],
        "notes": "",
    }


def version_core(
    *,
    stage: str,
    parent_version: str | None,
    tag: str,
    base_git_commit: str,
    base_git_dirty: bool | None,
    skill_sha256: str,
    dataset_manifest_sha256: str,
    eval_sha256: str,
    provenance_sha256: str,
    gate: dict[str, Any],
    optimizer_model: str,
    target_model: str,
    prompt_sha256: str,
    cost: dict[str, Any],
    operator: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "schema": VERSION_SCHEMA,
        "stage": stage,
        "parent_version": parent_version,
        "tag": tag,
        "base_git_commit": base_git_commit,
        "base_git_dirty": base_git_dirty,
        "skill_sha256": skill_sha256,
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "eval_sha256": eval_sha256,
        "provenance_sha256": provenance_sha256,
        "gate": gate,
        "optimizer_model": optimizer_model,
        "target_model": target_model,
        "prompt_sha256": prompt_sha256,
        "cost": cost,
        "operator": operator,
        "created_at": created_at,
    }


def validate_meta(meta: dict[str, Any], version_dir: str | Path) -> list[str]:
    errors: list[str] = []
    directory = Path(version_dir)
    if not isinstance(meta, dict):
        return ["meta.json must be a JSON object"]
    if meta.get("schema") != VERSION_SCHEMA:
        errors.append(f"meta.schema must be {VERSION_SCHEMA!r}")
    stage = meta.get("stage")
    if not isinstance(stage, str) or not STAGE_RE.match(stage):
        errors.append(f"invalid stage: {stage!r}")
    version_id = meta.get("version_id")
    if not isinstance(version_id, str) or not VERSION_RE.match(version_id):
        errors.append(f"invalid version_id: {version_id!r}")
    else:
        core = {key: value for key, value in meta.items() if key != "version_id"}
        actual = sha256_text(canonical_json(core))
        if actual != version_id:
            errors.append(
                f"version_id mismatch: meta={version_id} recomputed={actual}"
            )
    tag = meta.get("tag")
    if not isinstance(tag, str) or not TAG_RE.match(tag):
        errors.append(f"invalid tag: {tag!r}")
    elif isinstance(stage, str) and not tag.startswith(f"rsi/{stage}/"):
        errors.append(f"tag {tag!r} does not match stage {stage!r}")
    created_at = meta.get("created_at")
    if not isinstance(created_at, str):
        errors.append("created_at must be a string")
    else:
        try:
            datetime.fromisoformat(created_at)
        except ValueError:
            errors.append(f"created_at is not ISO-8601: {created_at!r}")
    skill_path = directory / "skill.md"
    if not skill_path.is_file():
        errors.append(f"missing skill.md in {directory}")
    else:
        projected = sha256_file(skill_path)
        if projected != meta.get("skill_sha256"):
            errors.append(
                f"skill_sha256 mismatch: meta={meta.get('skill_sha256')} "
                f"actual={projected}"
            )
    for filename, field in (
        ("dataset.json", "dataset_manifest_sha256"),
        ("eval.json", "eval_sha256"),
    ):
        path = directory / filename
        if not path.is_file():
            errors.append(f"missing {filename} in {directory}")
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{filename} is not valid JSON: {exc}")
            continue
        actual = sha256_text(canonical_json(value))
        if actual != meta.get(field):
            errors.append(
                f"{field} mismatch: meta={meta.get(field)} actual={actual}"
            )
    provenance_path = directory / "provenance.json"
    if not provenance_path.is_file():
        errors.append(f"missing provenance.json in {directory}")
    else:
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"provenance.json is not valid JSON: {exc}")
        else:
            actual = sha256_text(canonical_json(provenance))
            if actual != meta.get("provenance_sha256"):
                errors.append(
                    f"provenance_sha256 mismatch: meta={meta.get('provenance_sha256')} "
                    f"actual={actual}"
                )
    gate = meta.get("gate")
    if not isinstance(gate, dict):
        errors.append("gate must be an object")
    else:
        if gate.get("status") not in {"seed", "accepted", "rejected"}:
            errors.append(f"gate.status invalid: {gate.get('status')!r}")
        if not isinstance(gate.get("accepted"), bool):
            errors.append("gate.accepted must be a boolean")
        gate_path = directory / "gate.json"
        if gate_path.is_file():
            try:
                stored_gate = json.loads(gate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"gate.json is not valid JSON: {exc}")
            else:
                if canonical_json(stored_gate) != canonical_json(gate):
                    errors.append("gate.json does not match meta.gate")
    parent = meta.get("parent_version")
    if parent is not None:
        if not isinstance(parent, str) or not VERSION_RE.match(parent):
            errors.append(f"invalid parent_version: {parent!r}")
    return errors
