from __future__ import annotations

import json
from pathlib import Path

from audit_rsi.adapters.runs import import_runs
from audit_rsi.cli import _emit
from audit_rsi.learning.discover import discover
from audit_rsi.objective import evaluate
from audit_rsi.policy.base import BasePolicy
from audit_rsi.schema import Cost, DiscoveryTree, Node, Outcome
from audit_rsi.world import ReplayWorld, TracePool


def _finding(finding_id: str = "F-01") -> dict:
    return {
        "id": finding_id,
        "title": finding_id,
        "severity": "high",
        "confidence": "high",
        "category": "authentication",
        "evidence": ["app.py:10"],
    }


def _write_run(
    runs: Path,
    run_id: str,
    *,
    findings: list[dict] | None = None,
    raw_report: str | None = None,
    commit: str = "abcdef123456",
) -> Path:
    run = runs / "demo" / run_id
    run.mkdir(parents=True)
    if raw_report is None:
        raw_report = json.dumps(
            {
                "target": {"name": "demo", "commit": commit},
                "coverage": {"stages": {"route_auth": run_id}},
                "findings": findings if findings is not None else [],
            }
        )
    (run / "audit-report.json").write_text(raw_report, encoding="utf-8")
    (run / "run-meta.json").write_text(
        json.dumps({"commit": commit, "duration_seconds": 1}),
        encoding="utf-8",
    )
    return run


def test_latest_empty_and_invalid_reports_preserve_valid_history(
    tmp_path: Path,
) -> None:
    runs = tmp_path / "runs"
    _write_run(runs, "20260101", findings=[_finding()], commit="old")
    _write_run(runs, "20260102", findings=[], commit="empty")
    _write_run(runs, "20260103", raw_report="{", commit="invalid")
    curated = tmp_path / "curated.json"
    curated.write_text(
        json.dumps({"demo:20260101:F-01": {"verdict": "tp"}}),
        encoding="utf-8",
    )

    pool = import_runs(runs, latest=True, curated_path=curated)

    assert len(pool.worlds) == 1
    world = pool.worlds[0]
    assert world.meta["run_id"] == "20260101"
    assert world.commit == "old"
    assert world.tree.nodes["finding:F-01"].outcome.verdict == "tp"
    assert [item["status"] for item in world.meta["report_overlays"]] == [
        "empty",
        "invalid",
    ]
    assert world.meta["latest_report"]["run_id"] == "20260103"
    assert world.meta["report_overlays"][0]["coverage"]["stages"] == {
        "route_auth": "20260102"
    }


def test_scoped_labels_do_not_propagate_across_runs(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_run(runs, "run-a", findings=[_finding()], commit="commit-a")
    _write_run(runs, "run-b", findings=[_finding()], commit="commit-b")
    curated = tmp_path / "curated.json"
    curated.write_text(
        json.dumps(
            {
                "demo:F-01": {"verdict": "fp"},
                "demo:run-a:F-01": {
                    "verdict": "tp",
                    "semantic_id": "stable-finding",
                },
            }
        ),
        encoding="utf-8",
    )

    pool = import_runs(runs, latest=False, curated_path=curated)
    outcomes = {
        world.meta["run_id"]: world.tree.nodes["finding:F-01"].outcome
        for world in pool.worlds
    }

    assert outcomes["run-a"].verdict == "tp"
    assert outcomes["run-a"].run_id == "run-a"
    assert outcomes["run-a"].commit == "commit-a"
    assert outcomes["run-a"].semantic_id == "stable-finding"
    assert outcomes["run-b"].verdict == "unverified"


def _world(
    world_id: str,
    verdicts: dict[str, str],
    severities: dict[str, str],
) -> ReplayWorld:
    tree = DiscoveryTree(root_id="root")
    tree.add(
        Node(
            id="root",
            parent_id=None,
            kind="root",
            label=world_id,
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
                    severity=severities[finding_id],
                    confidence="high",
                ),
            )
        )
    return ReplayWorld(world_id=world_id, project=world_id, commit="", tree=tree)


class FirstOnlyPolicy(BasePolicy):
    name = "first-only"
    used = False

    def select(self, obs):
        if self.used or not obs.eligible:
            return []
        self.used = True
        return [min(obs.eligible, key=lambda node_id: obs.nodes[node_id].index)]


CURRENT_SOURCE = '''class Policy(BasePolicy):
    name = "current-first"
    used = False

    def select(self, obs):
        if self.used or not obs.eligible:
            return []
        self.used = True
        return [min(obs.eligible, key=lambda node_id: obs.nodes[node_id].index)]
'''

CANDIDATE_SOURCE = '''class Policy(BasePolicy):
    name = "candidate-last"
    used = False

    def select(self, obs):
        if self.used or not obs.eligible:
            return []
        self.used = True
        return [max(obs.eligible, key=lambda node_id: obs.nodes[node_id].index)]
'''


class StaticProposer:
    def propose(self, context, round_dir):
        return CANDIDATE_SOURCE


def _train_and_holdout() -> tuple[TracePool, TracePool]:
    train = TracePool(
        [
            _world(
                "train",
                {"A": "tp", "B": "tp"},
                {"A": "low", "B": "high"},
            )
        ]
    )
    holdout = TracePool(
        [
            _world(
                "holdout",
                {"A": "tp", "B": "unverified"},
                {"A": "high", "B": "high"},
            )
        ]
    )
    return train, holdout


def test_holdout_regression_is_rejected_without_overwriting_method(
    tmp_path: Path,
) -> None:
    train, holdout = _train_and_holdout()
    out = tmp_path / "rsi"
    method = out / "policy" / "method.py"
    method.parent.mkdir(parents=True)
    method.write_text(CURRENT_SOURCE, encoding="utf-8")

    result = discover(
        train,
        proposer=StaticProposer(),
        rounds=1,
        betas=(0.5,),
        max_workers=1,
        out_dir=out,
        holdout=holdout,
    )

    candidate = result.versions[1]
    assert candidate.status == "rejected"
    assert "holdout regression" in candidate.error
    assert candidate.holdout_score < result.baseline_holdout_score
    assert result.best_policy == "current-first"
    assert result.validation_status == "validated"
    assert result.method_status == "unchanged"
    assert method.read_text(encoding="utf-8") == CURRENT_SOURCE
    summary = json.loads(
        (out / "learning" / "discover_summary.json").read_text(encoding="utf-8")
    )
    assert summary["versions"][1]["status"] == "rejected"


def test_discover_without_holdout_is_explicitly_unvalidated(tmp_path: Path) -> None:
    train, _ = _train_and_holdout()
    out = tmp_path / "rsi"

    result = discover(
        train,
        proposer=StaticProposer(),
        rounds=1,
        betas=(0.5,),
        max_workers=1,
        out_dir=out,
    )

    assert result.validation_status == "unvalidated"
    assert result.holdout_score is None
    assert result.method_status == "shadow"
    assert result.versions[1].status == "shadow"
    assert not (out / "policy" / "method.py").exists()
    assert (out / "policy" / "shadow.py").read_text(encoding="utf-8") == CANDIDATE_SOURCE


def test_unjudged_fp_is_na_and_unverified_has_no_positive_reward(
    capsys,
) -> None:
    assert Outcome(verdict="unverified", severity="critical").score() == 0.0
    assert Outcome(verdict="unknown", severity="critical").score() == 0.0
    pool = TracePool(
        [_world("unjudged", {"A": "unverified"}, {"A": "critical"})]
    )

    result = evaluate(FirstOnlyPolicy, pool, betas=(0.5,), max_workers=1)
    point = result.per_world[0].points[0]

    assert point.quality == 0.0
    assert point.fp_rate is None
    assert point.label_coverage == 0.0
    assert result.to_dict()["mean_fp_rate"] is None
    _emit(result, False)
    output = capsys.readouterr().out
    assert "fp=N/A" in output
    assert "labels=0.000" in output


def test_multiple_tp_rewards_accumulate_without_renaming_best_score() -> None:
    pool = TracePool(
        [_world("two-tp", {"A": "tp", "B": "tp"}, {"A": "high", "B": "high"})]
    )

    result = evaluate(FirstOnlyPolicy, pool, betas=(0.5,), max_workers=1)
    point = result.per_world[0].points[0]
    payload = point.to_dict()

    assert point.quality == 0.5
    assert point.tp_recall == 0.5
    assert point.best_score == point.total_score
    assert pool.worlds[0].total_score == 2 * point.best_score
    assert payload["best_score"] == point.best_score
    assert payload["total_score"] == point.total_score
