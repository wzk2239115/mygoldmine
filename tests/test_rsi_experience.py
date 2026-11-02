from __future__ import annotations

import json
from pathlib import Path

import pytest

from audit_rsi.cli import main
from audit_rsi.experience import ACTION_MAP, build_experience, outcome_credit
from audit_rsi.labeling import (
    inverse_label_propensity,
    inverse_propensity_weights,
    stratified_sample,
    trusted_label_plan,
)


def _occurrence(project: str, run_id: str, finding_id: str, semantic_id: str) -> dict:
    return {
        "occurrence_id": f"{project}/{run_id}/{finding_id}",
        "semantic_id": semantic_id,
        "project": project,
        "run_id": run_id,
        "finding_id": finding_id,
        "severity": "high",
        "confidence": "medium",
        "verified": False,
        "commit": "abc123",
        "generated_at": "2026-01-01T00:00:00Z",
        "report": f"runs/{project}/{run_id}/audit-report.json",
        "raw": {
            "id": finding_id,
            "title": "sensitive finding body",
            "category": "auth",
            "evidence": [{"file": "secret.py", "lines": "1-2"}],
            "root_cause": "sensitive root cause",
            "final_review_note": "future human result",
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _artifacts(tmp_path: Path) -> dict[str, Path]:
    runs = tmp_path / "runs"
    occurrences = [
        _occurrence("demo", "r1", "F-01", "sem-shared"),
        _occurrence("demo", "r2", "F-01", "sem-shared"),
        _occurrence("demo", "r1", "F-02", "sem-other"),
        _occurrence("demo", "r1", "F-03", "sem-unknown"),
    ]
    for run_id in ("r1", "r2"):
        run = runs / "demo" / run_id
        run.mkdir(parents=True)
        (run / "audit-report.json").write_text(
            json.dumps({"target": {"project_type": "cli"}, "findings": []}),
            encoding="utf-8",
        )
    verify = runs / "demo" / "r1" / "verify" / "auto"
    verify.mkdir(parents=True)
    (verify / "summary.json").write_text(
        json.dumps(
            {
                "findings": [
                    {"finding_id": "F-01", "verdict": "confirmed"},
                    {"finding_id": "F-02", "verdict": "rejected"},
                    {"finding_id": "F-03", "verdict": "inconclusive"},
                ]
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-01-02T00:00:00Z",
                "occurrences": {item["occurrence_id"]: item for item in occurrences},
            }
        ),
        encoding="utf-8",
    )
    refine = tmp_path / "refine.jsonl"
    decisions = ["reproduce", "triage", "review", "duplicate"]
    _write_jsonl(
        refine,
        [
            {
                "ts": f"2026-01-03T00:00:0{index}Z",
                "project": item["project"],
                "run_id": item["run_id"],
                "finding_id": item["finding_id"],
                "features": {
                    "severity": "high",
                    "confidence": "medium",
                    "verified": True,
                    "verify_verdict": "confirmed",
                    "evidence_count": 1,
                },
                "decision": decisions[index],
                "reason": "policy explanation",
                "score": 30 - index,
            }
            for index, item in enumerate(occurrences)
        ],
    )
    validation = tmp_path / "validation.jsonl"
    validation.write_text("", encoding="utf-8")
    curated = tmp_path / "curated.json"
    curated.write_text("{}", encoding="utf-8")
    adjudication = tmp_path / "adjudication.json"
    adjudication.write_text('{"findings": {}}', encoding="utf-8")
    return {
        "ledger_path": ledger,
        "refine_path": refine,
        "validation_path": validation,
        "curated_path": curated,
        "adjudication_path": adjudication,
        "runs_root": runs,
    }


def test_action_mapping_and_pre_action_context(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    records = build_experience(**paths)
    by_id = {record["occurrence_id"]: record for record in records}

    assert [by_id[f"demo/{run}/{finding}"]["action"] for run, finding in (
        ("r1", "F-01"),
        ("r2", "F-01"),
        ("r1", "F-02"),
        ("r1", "F-03"),
    )] == ["verify", "deep_read", "human_review", "duplicate_candidate"]
    assert ACTION_MAP == {
        "reproduce": "verify",
        "triage": "deep_read",
        "review": "human_review",
        "duplicate": "duplicate_candidate",
        "archived": "defer",
        "inbox": "defer",
    }
    record = by_id["demo/r1/F-01"]
    assert record["source"]["decision"] == "reproduce"
    assert record["action_propensity"] == 1.0
    assert record["context"] == {
        "finding_id": "F-01",
        "severity": "high",
        "confidence": "medium",
        "category": "auth",
        "evidence_count": 1,
        "cve_tier": None,
        "score": 30.0,
        "history": {
            "verified": True,
            "verification": {"verdict": "confirmed"},
        },
    }
    assert not {"verdict", "outcome", "verified", "verify_verdict", "raw"} & set(
        record["context"]
    )


def test_explicit_policy_fields_and_pre_action_history_take_precedence(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    rows = [json.loads(line) for line in paths["refine_path"].read_text().splitlines()]
    rows[0].update(
        {
            "action": "human_review",
            "policy": {"name": "new-policy", "version": 3},
            "action_propensity": 0.25,
            "cost": {
                "agent_calls": 9,
                "seconds": 99,
                "tokens": 999,
                "review_seconds": 88,
            },
            "features": {
                **rows[0]["features"],
                "cve_tier": 2,
                "verified": False,
            },
            "context": {
                "verification": {
                    "verified": False,
                    "verdict": "rejected",
                    "method": "runtime",
                    "cost": {"seconds": 7, "agent_calls": 2},
                }
            },
        }
    )
    _write_jsonl(paths["refine_path"], rows)
    record = next(
        item
        for item in build_experience(**paths)
        if item["occurrence_id"] == "demo/r1/F-01"
    )
    assert record["action"] == "human_review"
    assert record["policy"] == {"name": "new-policy", "version": 3}
    assert record["action_propensity"] == 0.25
    assert record["source"]["decision"] == "reproduce"
    assert record["context"]["cve_tier"] == 2
    assert record["context"]["history"] == {
        "verified": False,
        "cost": {"seconds": 7.0, "agent_calls": 2},
        "verification": {"verdict": "rejected", "method": "runtime"},
    }
    assert record["cost"]["seconds"] == 99.0
    assert record["outcome"]["verdict"] == "static-supported"


def test_verify_runtime_evidence_is_not_downgraded_to_static(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    summary_path = (
        paths["runs_root"] / "demo" / "r1" / "verify" / "auto" / "summary.json"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["findings"][0]["evidence_class"] = "runtime"
    summary["findings"][1]["method"] = "dynamic-reproduction"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    records = build_experience(**paths)
    by_id = {record["occurrence_id"]: record for record in records}
    assert by_id["demo/r1/F-01"]["outcome"]["verdict"] == "runtime-confirmed"
    assert by_id["demo/r1/F-01"]["outcome"]["evidence_class"] == "runtime"
    assert by_id["demo/r1/F-01"]["label_propensity"] == 1.0
    assert by_id["demo/r1/F-01"]["source"]["label_assignment"] == "deterministic-runtime-verify"
    assert by_id["demo/r1/F-02"]["outcome"]["verdict"] == "fp"
    assert by_id["demo/r1/F-02"]["outcome"]["evidence_class"] == "runtime"
    assert by_id["demo/r1/F-02"]["label_propensity"] == 1.0
    assert by_id["demo/r2/F-01"]["label_propensity"] is None


def test_verify_report_artifacts_feed_actionable_experience(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    report_path = paths["runs_root"] / "demo" / "r1" / "verify" / "verify-report.json"
    report_path.write_text(json.dumps({
        "method": "static-evidence",
        "results": [
            {"id": "F-01", "verification": {"status": "confirmed", "method": "runtime-harness"}},
            {"id": "F-02", "verification": {"status": "confirmed", "method": "static-evidence"}},
        ],
    }))
    by_id = {record["occurrence_id"]: record for record in build_experience(**paths)}
    assert by_id["demo/r1/F-01"]["action"] == "verify"
    assert by_id["demo/r1/F-01"]["outcome"]["verdict"] == "runtime-confirmed"
    assert by_id["demo/r1/F-01"]["label_propensity"] == 1.0
    assert by_id["demo/r1/F-02"]["outcome"]["verdict"] == "static-supported"
    assert by_id["demo/r1/F-02"]["label_propensity"] == 1.0
    assert by_id["demo/r1/F-02"]["source"]["label_assignment"] == "deterministic-static-verify"


def test_auto_state_supplies_action_and_policy_without_refine_trace(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    paths["refine_path"].write_text("")
    paths["auto_path"] = tmp_path / "auto-state.json"
    paths["auto_path"].write_text(json.dumps({
        "findings": {"demo/r1/F-01": {"status": "reproduce", "source": "verify"}}
    }))
    record = next(
        item
        for item in build_experience(**paths)
        if item["occurrence_id"] == "demo/r1/F-01"
    )
    assert record["action"] == "verify"
    assert record["action_propensity"] == 1.0
    assert record["policy"] == "deterministic-auto-state"
    assert record["source"]["trajectory"] == "auto"
    assert record["label_propensity"] == 1.0


def test_unknown_and_inconclusive_never_become_fp(tmp_path: Path) -> None:
    records = build_experience(**_artifacts(tmp_path))
    unknown = next(item for item in records if item["semantic_id"] == "sem-unknown")
    assert unknown["outcome"]["verdict"] == "unknown"
    assert unknown["outcome"]["evidence_class"] == "static"
    assert outcome_credit(unknown) == 0.0


def test_verdict_and_evidence_class_are_distinct(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    paths["curated_path"].write_text(
        json.dumps({"demo:F-02": {"verdict": "fp"}}), encoding="utf-8"
    )
    records = build_experience(**paths)
    by_semantic = {record["semantic_id"]: record for record in records}
    assert by_semantic["sem-other"]["outcome"] == {
        "verdict": "fp",
        "evidence_class": "human",
        "label_scope": "semantic",
        "origin": "curated",
        "reward_eligible": True,
    }


def test_unscoped_label_does_not_cross_semantics(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    second = _occurrence("demo", "r3", "F-01", "sem-different")
    ledger = json.loads(paths["ledger_path"].read_text(encoding="utf-8"))
    ledger["occurrences"][second["occurrence_id"]] = second
    paths["ledger_path"].write_text(json.dumps(ledger), encoding="utf-8")
    paths["curated_path"].write_text(
        json.dumps({"demo:F-01": {"verdict": "fp"}}), encoding="utf-8"
    )
    records = build_experience(**paths)
    f01 = [record for record in records if record["context"]["finding_id"] == "F-01"]
    assert len(f01) == 3
    assert all(record["outcome"]["verdict"] != "fp" for record in f01)


def test_scoped_validation_matches_only_its_occurrence(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    _write_jsonl(
        paths["validation_path"],
        [
            {
                "occurrence_id": "demo/r2/F-01",
                "judge": {"verdict": "approved"},
                "status": "runtime-validated",
            },
            {
                "occurrence_id": "other/run/F-01",
                "judge": {"verdict": "rejected"},
            },
        ],
    )
    records = build_experience(**paths)
    by_id = {record["occurrence_id"]: record for record in records}
    assert by_id["demo/r2/F-01"]["outcome"]["verdict"] == "judge-approved"
    assert by_id["demo/r2/F-01"]["outcome"]["evidence_class"] == "judge"
    assert by_id["demo/r2/F-01"]["label_propensity"] is None
    assert by_id["demo/r2/F-01"]["source"]["label_assignment"] == "review-required"
    assert by_id["demo/r1/F-01"]["outcome"]["verdict"] == "static-supported"


def test_duplicate_semantic_receives_credit_once(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    _write_jsonl(
        paths["validation_path"],
        [{"semantic_id": "sem-shared", "judge": {"verdict": "approved"}}],
    )
    records = build_experience(**paths)
    shared = [record for record in records if record["semantic_id"] == "sem-shared"]
    assert len(shared) == 2
    assert all(record["outcome"]["verdict"] == "judge-approved" for record in shared)
    assert sum(outcome_credit(record) for record in shared) == 1.0


def test_cost_estimation_and_jsonl_output(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    output = tmp_path / "nested" / "experience.jsonl"
    records = build_experience(**paths, output_path=output)
    assert all(record["source"]["cost_estimated"] for record in records)
    assert all(
        record["cost"]
        == {"agent_calls": 0, "seconds": 0.0, "tokens": 0, "review_seconds": 0.0}
        for record in records
    )
    loaded = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert loaded == records

    rows = [json.loads(line) for line in paths["refine_path"].read_text().splitlines()]
    rows[0]["cost"] = {
        "agent_calls": 2,
        "seconds": 3.5,
        "tokens": 100,
        "review_seconds": 0,
    }
    _write_jsonl(paths["refine_path"], rows)
    complete = build_experience(**paths)
    first = next(item for item in complete if item["occurrence_id"] == "demo/r1/F-01")
    assert first["source"]["cost_estimated"] is False
    assert first["cost"]["agent_calls"] == 2


def test_unknown_action_has_no_fabricated_propensity(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    paths["refine_path"].write_text("", encoding="utf-8")
    records = build_experience(**paths)
    assert all(record["action"] is None for record in records)
    assert all(record["action_propensity"] is None for record in records)
    assert all(record["policy"] is None for record in records)


def _candidates(count: int = 40) -> list[dict]:
    return [
        {
            "occurrence_id": f"demo/r/F-{index:02d}",
            "semantic_id": f"sem-{index:02d}",
            "project": "demo" if index % 2 else "other",
            "run_id": "r",
            "commit": "abc",
            "action": "deep_read" if index % 3 else "verify",
            "context": {
                "severity": "high" if index % 2 else "low",
                "score": float(index),
                "title": "sensitive body",
                "verdict": "future label",
            },
        }
        for index in range(count)
    ]


def test_stratified_sampling_is_deterministic_and_includes_low_scores() -> None:
    candidates = _candidates()
    first = stratified_sample(candidates, sample_size=12, seed=17)
    second = stratified_sample(candidates, sample_size=12, seed=17)
    assert first == second
    assert len(first) == 12
    assert any(item["sampling_reason"] == "random-low-score-exploration" for item in first)
    assert any(item["sampling_reason"] == "high-score-coverage" for item in first)
    assert len({item["occurrence_id"] for item in first}) == 12
    for item in first:
        assert 0.0 < item["label_propensity"] <= 1.0
        assert item["label_propensity"] == pytest.approx(
            item["stratum"]["quota"] / item["stratum"]["size"]
        )
        assert "title" not in item["context"]
        assert "verdict" not in item["context"]


def test_inverse_propensity_weights_and_cap() -> None:
    assert inverse_label_propensity(0.5) == 2.0
    assert inverse_label_propensity(0.01, max_weight=20) == 20.0
    assert inverse_propensity_weights(
        [{"label_propensity": 1.0}, {"label_propensity": 0.25}]
    ) == [1.0, 4.0]
    with pytest.raises(ValueError):
        inverse_label_propensity(0.0)
    with pytest.raises(ValueError):
        inverse_label_propensity(0.5, max_weight=0.5)


def test_sample_size_bounds_and_seed_change() -> None:
    candidates = _candidates(8)
    assert stratified_sample(candidates, sample_size=0) == []
    assert len(stratified_sample(candidates, sample_size=100, seed=2)) == 8
    assert stratified_sample(candidates, sample_size=5, seed=1) != stratified_sample(
        candidates, sample_size=5, seed=999
    )


def test_trusted_label_plan_prioritizes_missing_projects_and_actions(tmp_path) -> None:
    def candidate(project, action, verdict="unknown", evidence="none", severity="high"):
        return {
            "occurrence_id": f"{project}/r1/F-{action}",
            "semantic_id": f"sem-{project}-{action}",
            "project": project,
            "run_id": "r1",
            "commit": "abc",
            "action": action,
            "context": {"severity": severity, "title": "sensitive"},
            "outcome": {"verdict": verdict, "evidence_class": evidence},
        }

    records = [
        candidate("project-a", "verify", "tp", "human"),
        candidate("project-b", "verify"),
        candidate("project-c", "deep_read"),
        candidate("project-d", "defer"),
        candidate("project-e", None),
    ]
    plan = trusted_label_plan(records, sample_size=3, seed=7)
    assert plan["status"] == "ok"
    assert plan["analysis"]["selected_projects"] == ["project-b", "project-c", "project-d"]
    assert {task["sampling_reason"] for task in plan["tasks"]} == {"trusted-project-gap"}
    assert all(task["label_propensity"] == 1.0 for task in plan["tasks"])
    assert all("title" not in task["context"] for task in plan["tasks"])
    assert trusted_label_plan(records[:1], sample_size=3)["status"] == "insufficient"

    pool = tmp_path / "pool.jsonl"
    output = tmp_path / "plan.jsonl"
    report = tmp_path / "report.json"
    pool.write_text("".join(json.dumps(row) + "\n" for row in records))
    assert main([
        "label-plan", "--pool", str(pool), "--output", str(output),
        "--report", str(report), "--limit", "3",
    ]) == 0
    assert len(output.read_text().splitlines()) == 3
    assert json.loads(report.read_text())["analysis"]["selected_projects"] == [
        "project-b", "project-c", "project-d"
    ]
