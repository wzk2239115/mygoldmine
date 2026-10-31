from __future__ import annotations

from pathlib import Path

import pytest

from audit_rsi.evaluation import (
    compare,
    project_bootstrap,
    rolling_forward,
    split_by_project_time,
)
from audit_rsi.learning.discover import discover
from audit_rsi.orchestrate import evolve
from audit_rsi.release import create_candidate, get_candidate, promote_candidate
from audit_rsi.schema import Cost, DiscoveryTree, Node, Outcome
from audit_rsi.world import ReplayWorld, TracePool
from rsi_version.store import VersionStore


def test_semantic_leakage_is_rejected() -> None:
    rows = [
        {"id": "a", "project": "a", "time": 1, "semantic_id": "shared"},
        {"id": "b", "project": "b", "time": 2, "semantic_id": "b-only"},
        {"id": "c", "project": "c", "time": 3, "semantic_id": "shared"},
    ]
    with pytest.raises(ValueError, match="semantic leakage"):
        split_by_project_time(rows)


def test_project_time_split_is_ordered_and_isolated() -> None:
    rows = [
        {
            "id": f"{project}-{time}",
            "project": project,
            "time": time,
            "semantic_id": f"{project}-semantic",
        }
        for project, offset in (("a", 0), ("b", 10), ("c", 20), ("d", 30))
        for time in (offset + 2, offset + 1)
    ]
    splits = split_by_project_time(rows, val_fraction=0.25, test_fraction=0.25)
    assert splits["projects"] == {"train": ["a", "b"], "val": ["c"], "test": ["d"]}
    assert [row["time"] for row in splits["train"]] == [1, 2, 11, 12]
    assert {row["project"] for row in splits["train"]}.isdisjoint(
        {row["project"] for row in splits["test"]}
    )


def test_project_bootstrap_is_reproducible() -> None:
    rows = [
        {"project": "a", "value": 0.2},
        {"project": "b", "value": 0.8},
        {"project": "c", "value": 0.4},
    ]
    first = project_bootstrap(rows, seed=17, n_bootstrap=200)
    second = project_bootstrap(rows, seed=17, n_bootstrap=200)
    assert first == second
    assert first["ci_low"] <= first["mean"] <= first["ci_high"]


def test_low_label_coverage_is_insufficient() -> None:
    incumbent = [
        {"project": project, "score": 0.5, "label_coverage": 0.2} for project in ("a", "b")
    ]
    candidate = [dict(row, score=0.8) for row in incumbent]
    result = compare(candidate, incumbent, min_label_coverage=0.8)
    assert result["status"] == "insufficient"
    assert not result["accepted"]
    assert "insufficient_label_coverage" in result["reasons"]
    assert result["difference"]["ci"] is not None


def test_worst_project_type_regression_is_rejected() -> None:
    incumbent = [
        {"project": "a1", "project_type": "a", "score": 0.2, "label_coverage": 1},
        {"project": "a2", "project_type": "a", "score": 0.2, "label_coverage": 1},
        {"project": "b1", "project_type": "b", "score": 0.8, "label_coverage": 1},
    ]
    candidate = [
        dict(row, score=score) for row, score in zip(incumbent, (0.8, 0.8, 0.1), strict=True)
    ]
    result = compare(candidate, incumbent)
    assert result["delta"] > 0
    assert result["status"] == "rejected"
    assert result["worst_project_type"]["project_type"] == "b"
    assert "worst_project_type_regression" in result["reasons"]


def test_rolling_forward_and_numeric_verification_metric() -> None:
    rows = [
        {"project": project, "time": time, "accuracy": time / 10}
        for project in ("a", "b")
        for time in (1, 2, 3)
    ]
    result = rolling_forward(rows, metric="accuracy", min_train=2, seed=3)
    assert result["status"] == "ok"
    assert result["n_folds"] == 2
    assert all(fold["train_size"] == 2 for fold in result["folds"])


def _world(project: str, verdicts: dict[str, str]) -> ReplayWorld:
    tree = DiscoveryTree(root_id="root")
    tree.add(
        Node(
            id="root",
            parent_id=None,
            kind="root",
            label=project,
            cost=Cost(agent_calls=0),
        )
    )
    for finding_id, verdict in verdicts.items():
        tree.add(
            Node(
                id=f"finding:{finding_id}",
                parent_id="root",
                kind="finding",
                label=finding_id,
                skill="test",
                outcome=Outcome(
                    verdict=verdict,
                    severity="high" if finding_id == "B" else "low",
                    confidence="high",
                    semantic_id=f"{project}:{finding_id}",
                ),
            )
        )
    return ReplayWorld(
        world_id=project,
        project=project,
        commit="",
        tree=tree,
        meta={"project_type": "demo", "time": "2026-01-01"},
    )


CURRENT_SOURCE = """class Policy(BasePolicy):
    name = "current-first"
    used = False

    def select(self, obs):
        if self.used or not obs.eligible:
            return []
        self.used = True
        return [min(obs.eligible, key=lambda node_id: obs.nodes[node_id].index)]
"""

CANDIDATE_SOURCE = """class Policy(BasePolicy):
    name = "candidate-last"
    used = False

    def select(self, obs):
        if self.used or not obs.eligible:
            return []
        self.used = True
        return [max(obs.eligible, key=lambda node_id: obs.nodes[node_id].index)]
"""


class StaticProposer:
    def propose(self, context, round_dir):
        return CANDIDATE_SOURCE


def test_discover_without_holdout_never_writes_production_method(
    tmp_path: Path,
) -> None:
    out = tmp_path / "rsi"
    method = out / "policy" / "method.py"
    method.parent.mkdir(parents=True)
    method.write_text(CURRENT_SOURCE, encoding="utf-8")
    pool = TracePool([_world("train", {"A": "tp", "B": "tp"})])

    result = discover(
        pool,
        proposer=StaticProposer(),
        rounds=1,
        betas=(0.5,),
        max_workers=1,
        out_dir=out,
    )

    assert result.method_status == "shadow"
    assert result.gate_status == "insufficient"
    assert "holdout_missing" in result.gate_reasons
    assert method.read_text(encoding="utf-8") == CURRENT_SOURCE
    assert (out / "policy" / "shadow.py").read_text(encoding="utf-8") == CANDIDATE_SOURCE


def test_evolve_defaults_to_shadow_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = TracePool([_world("train", {"A": "tp", "B": "tp"})])
    monkeypatch.setattr("audit_rsi.orchestrate.import_runs", lambda *args, **kwargs: pool)
    out = tmp_path / "rsi"

    result = evolve(
        runs_root=tmp_path / "runs",
        out_dir=out,
        rounds=1,
        betas=(0.5,),
        max_workers=1,
        proposer=StaticProposer(),
    )

    assert result["discover"]["method_status"] == "shadow"
    assert result["plan"]["artifact_status"] == "shadow"
    assert not result["plan"]["is_current"]
    assert (out / "shadow-plan.json").is_file()
    assert not (out / "plan.json").exists()
    assert not (out / "policy" / "method.py").exists()


def _release_inputs(tmp_path: Path, status: str) -> dict:
    policy = tmp_path / f"policy-{status}.py"
    policy.write_text(CANDIDATE_SOURCE, encoding="utf-8")
    accepted = status == "accepted"
    return {
        "policy_path": policy,
        "plan": {"artifact_status": "shadow", "score": 1},
        "dataset": {
            "schema": "mygoldmine-rsi-dataset/v1",
            "name": "test",
            "holdout_key": "project",
            "splits": {
                "train": [{"id": "a", "project": "a"}],
                "val": [{"id": "b", "project": "b"}],
                "test": [{"id": "c", "project": "c"}],
            },
            "counts": {"train": 1, "val": 1, "test": 1},
        },
        "evaluation": {
            "status": status,
            "accepted": accepted,
            "no_regression": accepted,
            "reasons": [] if accepted else ["holdout_missing"],
            "candidate": {"mean": 0.8},
            "incumbent": {"mean": 0.5},
            "difference": {"mean": 0.3, "ci": [0.1, 0.5]},
        },
    }


def test_only_accepted_candidate_is_published(tmp_path: Path) -> None:
    root = tmp_path / "release-rsi"
    meta = create_candidate(root, stage="audit", **_release_inputs(tmp_path, "accepted"))
    assert VersionStore(root).current_version("audit") is None
    assert get_candidate(root, "audit", meta["version_id"])["policy_path"].endswith("policy.py")

    current = promote_candidate(root, "audit", meta["version_id"])
    assert current["version_id"] == meta["version_id"]
    assert VersionStore(root).validate() == []


def test_failed_candidate_remains_queryable(tmp_path: Path) -> None:
    root = tmp_path / "release-rsi"
    inputs = _release_inputs(tmp_path, "insufficient")
    with pytest.raises(ValueError, match="accepted statistical gate"):
        create_candidate(root, stage="audit", promote=True, **inputs)

    versions = VersionStore(root).list("audit")
    assert len(versions) == 1
    candidate = get_candidate(root, "audit", versions[0]["version_id"])
    assert candidate["gate"]["status"] == "rejected"
    assert Path(candidate["eval_path"]).is_file()
    assert VersionStore(root).current_version("audit") is None
