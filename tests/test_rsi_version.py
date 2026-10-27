from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsi_version.cli import main
from rsi_version.schema import DATASET_SCHEMA, validate_dataset
from rsi_version.store import VersionStore


def _dataset(project: str = "demo") -> dict:
    return {
        "schema": DATASET_SCHEMA,
        "name": "demo",
        "holdout_key": "project",
        "splits": {
            "train": [{"id": f"{project}-train", "project": project}],
            "val": [{"id": f"{project}-val", "project": f"{project}-val"}],
            "test": [{"id": f"{project}-test", "project": f"{project}-test"}],
        },
        "counts": {"train": 1, "val": 1, "test": 1},
    }


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _create(store: VersionStore, tmp_path: Path, text: str, **kwargs):
    skill = tmp_path / "skill.md"
    skill.write_text(text, encoding="utf-8")
    dataset = _write(tmp_path / "dataset.json", _dataset())
    evaluation = _write(
        tmp_path / "eval.json",
        {"schema": "mygoldmine-rsi-eval/v1", "n_tasks": 1, "hard": 1.0, "soft": 0.9},
    )
    gate = _write(
        tmp_path / "gate.json",
        {
            "schema": "mygoldmine-rsi-gate/v1",
            "status": "accepted",
            "accepted": True,
            "metric": "hard",
            "baseline": 0.5,
            "candidate": 1.0,
            "no_regression": True,
        },
    )
    return store.create(
        stage="env",
        skill_path=skill,
        dataset_path=dataset,
        eval_path=evaluation,
        gate_path=gate,
        operator="test",
        base_git_commit="deadbeef",
        base_git_dirty=False,
        **kwargs,
    )


def test_create_and_promote(tmp_path: Path) -> None:
    store = VersionStore(tmp_path / "rsi")
    meta = _create(store, tmp_path, "# skill v0\n", tag="rsi/env/v000", promote=True)
    assert len(meta["version_id"]) == 64
    assert meta["parent_version"] is None
    assert meta["tag"] == "rsi/env/v000"
    assert store.current_version("env") == meta["version_id"]
    assert store.validate() == []
    version_dir = store.versions_dir("env") / meta["version_id"]
    assert (version_dir / "skill.md").read_text() == "# skill v0\n"
    assert (version_dir / "diff.patch").read_text() == ""
    assert (version_dir / "meta.json").is_file()


def test_parent_lineage_and_diff(tmp_path: Path) -> None:
    store = VersionStore(tmp_path / "rsi")
    first = _create(store, tmp_path, "# skill v0\n", tag="rsi/env/v000", promote=True)
    second = _create(store, tmp_path, "# skill v0\n- new rule\n", tag="rsi/env/v001")
    assert second["parent_version"] == first["version_id"]
    assert second["tag"] == "rsi/env/v001"
    diff = (store.versions_dir("env") / second["version_id"] / "diff.patch").read_text()
    assert "+- new rule" in diff
    assert store.validate() == []


def test_no_parent_flag(tmp_path: Path) -> None:
    store = VersionStore(tmp_path / "rsi")
    first = _create(store, tmp_path, "# v0\n", tag="rsi/env/v000", promote=True)
    second = _create(
        store, tmp_path, "# v1\n", tag="rsi/env/v001", parent="", promote=True
    )
    assert second["parent_version"] is None
    assert second["version_id"] != first["version_id"]


def test_validate_detects_skill_corruption(tmp_path: Path) -> None:
    store = VersionStore(tmp_path / "rsi")
    meta = _create(store, tmp_path, "# v0\n", tag="rsi/env/v000", promote=True)
    version_dir = store.versions_dir("env") / meta["version_id"]
    (version_dir / "skill.md").write_text("# corrupted\n", encoding="utf-8")
    errors = store.validate()
    assert any("skill_sha256 mismatch" in error for error in errors)


def test_dataset_leakage_detection() -> None:
    dataset = _dataset()
    dataset["splits"]["val"][0]["project"] = dataset["splits"]["train"][0]["project"]
    errors = validate_dataset(dataset)
    assert any("overlaps train/val" in error for error in errors)

    duplicate = _dataset()
    duplicate["splits"]["val"][0]["id"] = duplicate["splits"]["train"][0]["id"]
    errors = validate_dataset(duplicate)
    assert any("duplicate id" in error for error in errors)


def test_cli_create_and_validate(tmp_path: Path) -> None:
    root = tmp_path / "rsi"
    skill = tmp_path / "skill.md"
    skill.write_text("# cli skill\n", encoding="utf-8")
    dataset = _write(tmp_path / "cli-dataset.json", _dataset())
    assert main(["init", "--root", str(root), "--stage", "env"]) == 0
    assert (
        main(
            [
                "create",
                "--root",
                str(root),
                "--stage",
                "env",
                "--skill",
                str(skill),
                "--dataset",
                str(dataset),
                "--tag",
                "rsi/env/v000",
                "--promote",
                "--operator",
                "test",
                "--base-git-commit",
                "abc",
            ]
        )
        == 0
    )
    assert main(["validate", "--root", str(root)]) == 0
    assert main(["current", "--root", str(root), "--stage", "env"]) == 0
    assert main(["show", "--root", str(root), "--stage", "env", "--json"]) == 0


def test_unknown_parent_rejected(tmp_path: Path) -> None:
    store = VersionStore(tmp_path / "rsi")
    with pytest.raises(FileNotFoundError):
        _create(
            store,
            tmp_path,
            "# v0\n",
            parent="0" * 64,
            tag="rsi/env/v000",
        )


def test_validate_detects_provenance_corruption(tmp_path: Path) -> None:
    store = VersionStore(tmp_path / "rsi")
    meta = _create(store, tmp_path, "# v0\n", tag="rsi/env/v000", promote=True)
    version_dir = store.versions_dir("env") / meta["version_id"]
    provenance = json.loads((version_dir / "provenance.json").read_text())
    provenance["operator"] = "someone-else"
    (version_dir / "provenance.json").write_text(json.dumps(provenance))
    errors = store.validate()
    assert any("provenance_sha256 mismatch" in error for error in errors)
