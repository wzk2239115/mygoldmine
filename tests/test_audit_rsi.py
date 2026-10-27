from __future__ import annotations

import json
from pathlib import Path

import pytest

from audit_rsi.adapters.runs import import_runs
from audit_rsi.cli import main
from audit_rsi.env import TraceEnv
from audit_rsi.learning.discover import discover
from audit_rsi.learning.proposer import TEMPLATES, TemplateProposer
from audit_rsi.objective import evaluate
from audit_rsi.orchestrate import plan_from_pool, write_plan
from audit_rsi.policy.baseline import BaselinePolicy
from audit_rsi.policy.heuristics import EvidenceFirstPolicy
from audit_rsi.policy.loader import PolicyRejected, load_policy_source

FINDINGS = [
    {
        "id": "F-01",
        "title": "Unauthenticated admin route",
        "severity": "high",
        "confidence": "high",
        "category": "authentication",
        "cwe": ["CWE-306"],
        "evidence": ["app.py:10"],
        "root_cause": "missing auth check on admin route",
        "preconditions": [],
        "reproduction_idea": "",
        "remediation": "",
        "related_artifacts": [],
    },
    {
        "id": "F-02",
        "title": "Documented behavior",
        "severity": "info",
        "confidence": "high",
        "category": "general",
        "cwe": [],
        "evidence": ["docs.md:3"],
        "root_cause": "documented design choice",
        "preconditions": [],
        "reproduction_idea": "",
        "remediation": "",
        "related_artifacts": [],
    },
]

STAGES = {
    "workspace_scan": "completed",
    "project_profile": "completed",
    "route_auth": "completed",
    "general_code_security": "completed",
    "final_crosscheck": "completed",
}


def _write_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    runs = tmp_path / "runs"
    run = runs / "demo" / "20260101T000000Z"
    run.mkdir(parents=True)
    report = {
        "target": {
            "name": "demo",
            "commit": "abcdef1234567890",
            "project_type": "test",
        },
        "summary": {"severity_counts": {"high": 1, "info": 1}},
        "coverage": {"stages": STAGES},
        "findings": FINDINGS,
    }
    (run / "audit-report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    (run / "run-meta.json").write_text(
        json.dumps(
            {
                "project": "demo",
                "commit": "abcdef1234567890",
                "duration_seconds": 80,
                "model": "test-model",
                "agent": "test-agent",
            }
        ),
        encoding="utf-8",
    )
    verify = run / "verify" / "auto"
    verify.mkdir(parents=True)
    (verify / "summary.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "finding_id": "F-01",
                        "severity": "high",
                        "verdict": "confirmed",
                        "reason": "source hit",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    curated = tmp_path / "curated.json"
    curated.write_text(
        json.dumps(
            {
                "demo:F-01": {"verdict": "tp", "cveTier": 1},
                "demo:F-02": {"verdict": "fp", "cveTier": None},
            }
        ),
        encoding="utf-8",
    )
    handoff = tmp_path / "handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "tier": 1,
                        "project": "demo",
                        "finding_id": "F-01",
                        "known_overlap": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return runs, curated, handoff


def _pool(tmp_path: Path):
    runs, curated, handoff = _write_run(tmp_path)
    return import_runs(
        runs,
        latest=True,
        curated_path=curated,
        handoff_path=handoff,
    )


def test_import_builds_tree_and_labels(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    assert len(pool.worlds) == 1
    world = pool.worlds[0]
    assert world.project == "demo"
    assert world.best_score > 0
    assert "stage:route_auth" in world.tree.nodes
    finding = world.tree.nodes["finding:F-01"]
    assert finding.outcome.verdict == "tp"
    assert finding.outcome.cve_tier == 1
    assert world.tree.nodes["finding:F-02"].outcome.verdict == "fp"
    assert world.tree.nodes["verify:F-01"].outcome.verdict == "tp"


def test_adjudication_clears_stale_tier(tmp_path: Path) -> None:
    runs, curated, handoff = _write_run(tmp_path)
    adjudication = tmp_path / "adjudication.json"
    adjudication.write_text(
        json.dumps(
            {
                "findings": {
                    "demo:F-01": {"verdict": "design", "cveTier": None}
                }
            }
        ),
        encoding="utf-8",
    )
    pool = import_runs(
        runs,
        curated_path=curated,
        handoff_path=handoff,
        adjudication_path=adjudication,
    )
    finding = pool.worlds[0].tree.nodes["finding:F-01"]
    assert finding.outcome.verdict == "design"
    assert finding.outcome.cve_tier is None


def test_env_hides_unrevealed_outcomes(tmp_path: Path) -> None:
    world = _pool(tmp_path).worlds[0]
    env = TraceEnv(world, rho=0.5, max_workers=1, max_rounds=10)
    obs = env.reset()
    assert obs.nodes["root"].revealed is True
    assert obs.eligible
    candidate = obs.eligible[0]
    assert obs.nodes[candidate].revealed is False
    assert obs.nodes[candidate].outcome is None
    obs = env.step([candidate])
    assert obs.nodes[candidate].revealed is True
    assert obs.nodes[candidate].outcome is not None


def test_replay_rewards_targeted_policy(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    baseline = evaluate(
        BaselinePolicy,
        pool,
        betas=(0.5,),
        max_workers=1,
        max_rounds=4,
    )
    evidence = evaluate(
        EvidenceFirstPolicy,
        pool,
        betas=(0.5,),
        max_workers=1,
        max_rounds=4,
    )
    assert baseline.per_world[0].points[0].quality == 0.0
    assert evidence.per_world[0].points[0].quality > 0.0
    assert evidence.score > baseline.score


def test_policy_loader_rejects_dangerous_code() -> None:
    with pytest.raises(PolicyRejected):
        load_policy_source(
            "import os\nclass Policy(BasePolicy):\n"
            "    def select(self, obs):\n        return []\n"
        )
    with pytest.raises(PolicyRejected):
        load_policy_source(
            "class Policy(BasePolicy):\n"
            "    def select(self, obs):\n        return open('/etc/passwd')\n"
        )
    with pytest.raises(PolicyRejected):
        load_policy_source(
            "class Policy(BasePolicy):\n"
            "    def select(self, obs):\n        while True:\n            pass\n"
        )
    cls = load_policy_source(TEMPLATES["evidence"])
    assert cls.name == "dreamed-evidence"


def test_discover_promotes_better_policy(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    out = tmp_path / "rsi"
    result = discover(
        pool,
        proposer=TemplateProposer(),
        rounds=2,
        betas=(0.5,),
        max_workers=1,
        max_rounds=4,
        out_dir=out,
    )
    assert result.best_score > result.baseline_score
    assert (out / "policy" / "method.py").exists()
    assert (out / "learning" / "discover_summary.json").exists()
    promoted = load_policy_source(
        (out / "policy" / "method.py").read_text(encoding="utf-8")
    )
    assert promoted.name.startswith("dreamed-")


def test_plan_and_cli_import(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    plan = plan_from_pool(
        pool,
        policy_name="baseline",
        betas=(0.5,),
        max_workers=1,
        max_rounds=10,
    )
    assert plan["priorities"]
    assert any(item["tag"] == "auth" for item in plan["priorities"])
    json_path, md_path = write_plan(plan, tmp_path / "rsi")
    assert json_path.exists() and md_path.exists()

    runs, curated, handoff = _write_run(tmp_path / "cli")
    out = tmp_path / "cli-rsi"
    rc = main(
        [
            "import",
            "--runs",
            str(runs),
            "--out",
            str(out),
            "--curated",
            str(curated),
            "--handoff",
            str(handoff),
            "--json",
        ]
    )
    assert rc == 0
    assert (out / "trace_pool.json").exists()
