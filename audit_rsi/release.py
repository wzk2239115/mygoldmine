from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from rsi_version.schema import sha256_file, sha256_text
from rsi_version.store import VersionStore


def _read_json(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return json.loads(json.dumps(value))
    data = json.loads(Path(value).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("release metadata must be a JSON object")
    return data


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def gate_from_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    accepted = bool(
        evaluation.get("status") == "accepted"
        and evaluation.get("accepted") is True
        and evaluation.get("no_regression", True) is True
        and not evaluation.get("reasons")
    )
    candidate = evaluation.get("candidate", {})
    incumbent = evaluation.get("incumbent", {})
    return {
        "schema": "mygoldmine-rsi-gate/v1",
        "status": "accepted" if accepted else "rejected",
        "accepted": accepted,
        "metric": evaluation.get("metric", "score"),
        "baseline": incumbent.get("mean"),
        "candidate": candidate.get("mean"),
        "difference": evaluation.get("difference"),
        "no_regression": evaluation.get("no_regression", False),
        "reasons": list(evaluation.get("reasons", [])),
    }


def create_candidate(
    root: str | Path = "rsi",
    *,
    stage: str = "audit",
    policy_path: str | Path,
    plan: str | Path | dict[str, Any],
    dataset: str | Path | dict[str, Any],
    evaluation: str | Path | dict[str, Any],
    provenance: str | Path | dict[str, Any] | None = None,
    gate: str | Path | dict[str, Any] | None = None,
    promote: bool = False,
    operator: str = "offline-evaluator",
    tag: str = "",
) -> dict[str, Any]:
    policy_path = Path(policy_path)
    policy_text = policy_path.read_text(encoding="utf-8")
    plan_data = _read_json(plan)
    dataset_data = _read_json(dataset)
    evaluation_data = _read_json(evaluation)
    evaluation_data.setdefault("schema", "mygoldmine-rsi-eval/v1")
    provenance_data = _read_json(provenance) if provenance is not None else {}
    gate_data = _read_json(gate) if gate is not None else gate_from_evaluation(evaluation_data)
    artifacts = {
        "policy.py": sha256_text(policy_text),
        "plan.json": sha256_text(
            json.dumps(plan_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ),
    }
    provenance_data["artifacts"] = {
        **provenance_data.get("artifacts", {}),
        **artifacts,
    }
    provenance_data["release"] = {
        "kind": "offline-candidate",
        "evaluation_status": evaluation_data.get("status", "insufficient"),
    }

    store = VersionStore(root)
    with tempfile.TemporaryDirectory(prefix="rsi-release-") as temporary:
        staging = Path(temporary)
        skill_path = staging / "skill.md"
        skill_path.write_text(
            "# Offline RSI candidate\n\n"
            f"- policy_sha256: `{artifacts['policy.py']}`\n"
            f"- plan_sha256: `{artifacts['plan.json']}`\n",
            encoding="utf-8",
        )
        paths = {
            "dataset": staging / "dataset.json",
            "evaluation": staging / "eval.json",
            "provenance": staging / "provenance.json",
            "gate": staging / "gate.json",
        }
        _write_json(paths["dataset"], dataset_data)
        _write_json(paths["evaluation"], evaluation_data)
        _write_json(paths["provenance"], provenance_data)
        _write_json(paths["gate"], gate_data)
        meta = store.create(
            stage=stage,
            skill_path=skill_path,
            dataset_path=paths["dataset"],
            eval_path=paths["evaluation"],
            gate_path=paths["gate"],
            provenance_path=paths["provenance"],
            operator=operator,
            tag=tag,
        )

    version_dir = store.versions_dir(stage) / meta["version_id"]
    (version_dir / "policy.py").write_text(policy_text, encoding="utf-8")
    _write_json(version_dir / "plan.json", plan_data)
    if promote:
        promote_candidate(root, stage, meta["version_id"])
    return meta


def validate_candidate(
    root: str | Path,
    stage: str,
    version_id: str,
) -> list[str]:
    store = VersionStore(root)
    meta = store.load(stage, version_id)
    version_dir = store.versions_dir(stage) / version_id
    provenance = json.loads((version_dir / "provenance.json").read_text(encoding="utf-8"))
    artifacts = provenance.get("artifacts", {})
    errors = []
    for filename in ("policy.py", "plan.json"):
        path = version_dir / filename
        if not path.is_file():
            errors.append(f"missing {filename}")
        elif sha256_file(path) != artifacts.get(filename):
            errors.append(f"{filename} hash mismatch")
    if meta.get("gate") != json.loads((version_dir / "gate.json").read_text(encoding="utf-8")):
        errors.append("gate metadata mismatch")
    return errors


def promote_candidate(
    root: str | Path,
    stage: str,
    version_id: str,
) -> dict[str, Any]:
    store = VersionStore(root)
    errors = validate_candidate(root, stage, version_id)
    if errors:
        raise ValueError("candidate integrity failed: " + "; ".join(errors))
    meta = store.load(stage, version_id)
    gate = meta.get("gate", {})
    evaluation = json.loads(
        (store.versions_dir(stage) / version_id / "eval.json").read_text(encoding="utf-8")
    )
    accepted = bool(
        gate.get("status") == "accepted"
        and gate.get("accepted") is True
        and evaluation.get("status") == "accepted"
        and evaluation.get("accepted") is True
        and evaluation.get("no_regression", True) is True
        and not evaluation.get("reasons")
    )
    if not accepted:
        raise ValueError("release requires an accepted statistical gate")
    return store.promote(stage, version_id)


def get_candidate(
    root: str | Path,
    stage: str,
    version_id: str,
) -> dict[str, Any]:
    store = VersionStore(root)
    meta = store.load(stage, version_id)
    version_dir = store.versions_dir(stage) / version_id
    return {
        **meta,
        "path": str(version_dir),
        "policy_path": str(version_dir / "policy.py"),
        "plan_path": str(version_dir / "plan.json"),
        "dataset_path": str(version_dir / "dataset.json"),
        "eval_path": str(version_dir / "eval.json"),
        "provenance_path": str(version_dir / "provenance.json"),
    }


publish_candidate = promote_candidate
create_release_candidate = create_candidate
