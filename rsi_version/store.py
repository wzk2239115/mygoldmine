from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import (
    CURRENT_SCHEMA,
    STAGE_RE,
    STAGE_SCHEMA,
    VERSION_RE,
    canonical_json,
    dataset_hash,
    default_dataset,
    default_eval,
    default_gate,
    default_provenance,
    git_info,
    sha256_file,
    sha256_text,
    validate_dataset,
    validate_meta,
    version_core,
)


class VersionStore:
    def __init__(self, root: str | Path = "rsi") -> None:
        self.root = Path(root)
        self.repo_root = self.root.resolve().parent

    def stage_dir(self, stage: str) -> Path:
        self._check_stage(stage)
        return self.root / "stages" / stage

    def versions_dir(self, stage: str) -> Path:
        return self.stage_dir(stage) / "versions"

    def current_path(self, stage: str) -> Path:
        return self.stage_dir(stage) / "current.json"

    def init_stage(self, stage: str) -> Path:
        self._check_stage(stage)
        directory = self.stage_dir(stage)
        (directory / "versions").mkdir(parents=True, exist_ok=True)
        stage_meta = directory / "stage.json"
        if not stage_meta.exists():
            self._write_json(
                stage_meta,
                {
                    "schema": STAGE_SCHEMA,
                    "stage": stage,
                    "created_at": self._now(),
                },
            )
        gitkeep = directory / "versions" / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")
        return directory

    def create(
        self,
        *,
        stage: str,
        skill_path: str | Path,
        dataset_path: str | Path | None = None,
        eval_path: str | Path | None = None,
        gate_path: str | Path | None = None,
        provenance_path: str | Path | None = None,
        parent: str | None = None,
        tag: str = "",
        promote: bool = False,
        operator: str = "",
        optimizer_model: str = "",
        target_model: str = "",
        prompt_path: str | Path | None = None,
        cost: dict[str, Any] | None = None,
        base_git_commit: str | None = None,
        base_git_dirty: bool | None = None,
    ) -> dict[str, Any]:
        self.init_stage(stage)
        skill_path = Path(skill_path)
        skill_text = skill_path.read_text(encoding="utf-8")
        skill_sha = sha256_text(skill_text)

        dataset = self._load_optional(dataset_path, default_dataset())
        if dataset_path is not None:
            errors = validate_dataset(dataset)
            if errors:
                raise ValueError("dataset invalid: " + "; ".join(errors))
        dataset_sha = dataset_hash(dataset)

        eval_data = self._load_optional(eval_path, default_eval())
        eval_sha = sha256_text(canonical_json(eval_data))

        gate = self._load_optional(gate_path, default_gate())
        if not isinstance(gate, dict):
            raise ValueError("gate must be a JSON object")
        gate.setdefault("schema", "mygoldmine-rsi-gate/v1")
        gate.setdefault("accepted", gate.get("status") != "rejected")
        gate.setdefault("status", "seed")

        commit, dirty = git_info(self.repo_root)
        if base_git_commit is not None:
            commit = base_git_commit
        if base_git_dirty is not None:
            dirty = base_git_dirty

        provenance = self._load_optional(
            provenance_path,
            default_provenance(
                operator or "unknown",
                commit,
                dirty,
                optimizer_model,
                target_model,
            ),
        )
        if provenance_path is not None and isinstance(provenance, dict):
            provenance.setdefault("schema", "mygoldmine-rsi-provenance/v1")
            provenance.setdefault("git_commit", commit)
            provenance.setdefault("git_dirty", dirty)
            provenance.setdefault("operator", operator or "unknown")
        provenance_sha = sha256_text(canonical_json(provenance))
        if parent == "":
            parent_version = None
        elif parent is None:
            parent_version = self.current_version(stage)
        else:
            parent_version = parent
        if parent_version is not None:
            self.load(stage, parent_version)

        resolved_tag = tag or self._next_tag(stage)
        created_at = self._now()
        prompt_sha = (
            sha256_file(prompt_path) if prompt_path is not None else skill_sha
        )
        core = version_core(
            stage=stage,
            parent_version=parent_version,
            tag=resolved_tag,
            base_git_commit=commit,
            base_git_dirty=dirty,
            skill_sha256=skill_sha,
            dataset_manifest_sha256=dataset_sha,
            eval_sha256=eval_sha,
            provenance_sha256=provenance_sha,
            gate=gate,
            optimizer_model=optimizer_model,
            target_model=target_model,
            prompt_sha256=prompt_sha,
            cost=cost or {},
            operator=operator or "unknown",
            created_at=created_at,
        )
        version_id = sha256_text(canonical_json(core))
        version_dir = self.versions_dir(stage) / version_id
        if version_dir.exists():
            raise FileExistsError(f"version already exists: {version_dir}")
        version_dir.mkdir(parents=True, exist_ok=False)

        (version_dir / "skill.md").write_text(skill_text, encoding="utf-8")
        self._write_json(version_dir / "dataset.json", dataset)
        self._write_json(version_dir / "eval.json", eval_data)
        self._write_json(version_dir / "gate.json", gate)
        self._write_json(version_dir / "provenance.json", provenance)
        meta = {**core, "version_id": version_id}
        self._write_json(version_dir / "meta.json", meta)
        self._write_diff(stage, version_dir, parent_version, skill_text)

        if promote:
            self.promote(stage, version_id)
        return meta

    def load(self, stage: str, version_id: str) -> dict[str, Any]:
        self._check_version(version_id)
        version_dir = self.versions_dir(stage) / version_id
        if not version_dir.is_dir():
            raise FileNotFoundError(version_dir)
        return self._read_json(version_dir / "meta.json")

    def list(self, stage: str | None = None) -> list[dict[str, Any]]:
        stages = [stage] if stage else self._stage_names()
        rows: list[dict[str, Any]] = []
        for name in stages:
            directory = self.versions_dir(name)
            if not directory.is_dir():
                continue
            for version_dir in sorted(directory.iterdir()):
                if not version_dir.is_dir():
                    continue
                meta_path = version_dir / "meta.json"
                if not meta_path.is_file():
                    continue
                meta = self._read_json(meta_path)
                rows.append({**meta, "path": str(version_dir)})
        rows.sort(key=lambda row: row.get("created_at", ""))
        return rows

    def current(self, stage: str) -> dict[str, Any] | None:
        path = self.current_path(stage)
        if not path.is_file():
            return None
        return self._read_json(path)

    def current_version(self, stage: str) -> str | None:
        current = self.current(stage)
        if not current:
            return None
        value = current.get("version_id")
        return str(value) if value else None

    def promote(self, stage: str, version_id: str) -> dict[str, Any]:
        meta = self.load(stage, version_id)
        current = {
            "schema": CURRENT_SCHEMA,
            "stage": stage,
            "version_id": version_id,
            "tag": meta.get("tag", ""),
            "updated_at": self._now(),
        }
        self._write_json(self.current_path(stage), current)
        return current

    def validate(self) -> list[str]:
        errors: list[str] = []
        for stage in self._stage_names():
            if not STAGE_RE.match(stage):
                errors.append(f"invalid stage directory: {stage!r}")
                continue
            versions = self.versions_dir(stage)
            if not versions.is_dir():
                errors.append(f"missing versions dir for stage {stage}")
                continue
            ids: set[str] = set()
            for version_dir in sorted(versions.iterdir()):
                if not version_dir.is_dir():
                    continue
                meta_path = version_dir / "meta.json"
                if not meta_path.is_file():
                    errors.append(f"missing meta.json in {version_dir}")
                    continue
                try:
                    meta = self._read_json(meta_path)
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"{version_dir}: {exc}")
                    continue
                errors.extend(
                    f"{version_dir}: {item}"
                    for item in validate_meta(meta, version_dir)
                )
                version_id = meta.get("version_id")
                if isinstance(version_id, str):
                    ids.add(version_id)
                parent = meta.get("parent_version")
                if parent is not None and parent not in {
                    path.name for path in versions.iterdir() if path.is_dir()
                }:
                    errors.append(
                        f"{version_dir}: parent {parent} does not exist"
                    )
                dataset_path = version_dir / "dataset.json"
                if dataset_path.is_file():
                    try:
                        dataset = self._read_json(dataset_path)
                        errors.extend(
                            f"{version_dir}: {item}"
                            for item in validate_dataset(dataset)
                        )
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"{version_dir}: dataset.json: {exc}")
            current = self.current(stage)
            if ids and not current:
                errors.append(f"stage {stage}: versions exist but current.json missing")
            if current:
                current_id = current.get("version_id")
                if current_id not in ids:
                    errors.append(
                        f"stage {stage}: current points to missing {current_id}"
                    )
                elif current.get("tag") and current.get("tag") != self.load(
                    stage, str(current_id)
                ).get("tag"):
                    errors.append(
                        f"stage {stage}: current tag mismatch for {current_id}"
                    )
        return errors

    def _write_diff(
        self,
        stage: str,
        version_dir: Path,
        parent_version: str | None,
        skill_text: str,
    ) -> None:
        if parent_version is None:
            (version_dir / "diff.patch").write_text("", encoding="utf-8")
            return
        parent_path = self.versions_dir(stage) / parent_version / "skill.md"
        old = parent_path.read_text(encoding="utf-8").splitlines(keepends=True)
        new = skill_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old,
            new,
            fromfile=f"{parent_version}/skill.md",
            tofile=f"{version_dir.name}/skill.md",
        )
        (version_dir / "diff.patch").write_text("".join(diff), encoding="utf-8")

    def _next_tag(self, stage: str) -> str:
        tags = {row.get("tag") for row in self.list(stage)}
        index = 0
        while True:
            candidate = f"rsi/{stage}/v{index:03d}"
            if candidate not in tags:
                return candidate
            index += 1

    def _stage_names(self) -> list[str]:
        stages = self.root / "stages"
        if not stages.is_dir():
            return []
        return sorted(path.name for path in stages.iterdir() if path.is_dir())

    def _load_optional(self, path: str | Path | None, default: Any) -> Any:
        if path is None:
            return default
        target = Path(path)
        if not target.is_file():
            raise FileNotFoundError(target)
        return self._read_json(target)

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _check_stage(self, stage: str) -> None:
        if not STAGE_RE.match(stage or ""):
            raise ValueError(f"invalid stage: {stage!r}")

    def _check_version(self, version_id: str) -> None:
        if not VERSION_RE.match(version_id or ""):
            raise ValueError(f"invalid version_id: {version_id!r}")
