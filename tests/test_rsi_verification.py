from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from audit_rsi.cli import main
from audit_rsi.verification import (
    ACTIONS,
    VerificationPolicy,
    data_hash,
    deduplicate_semantics,
    extract_features,
    merge_labels,
    outcome_flip_report,
    read_experience,
    record_utility,
    replay_policies,
    shadow_payload,
    train_policy,
    utility_details,
    write_jsonl,
)


def _record(
    occurrence_id: str = "occ-1",
    *,
    semantic_id: str = "semantic-1",
    project: str = "project-a",
    action: str = "verify",
    verdict: str = "tp",
    evidence_class: str = "runtime",
    severity: str = "high",
    label_propensity: float = 0.5,
    ts: str = "2026-01-01T00:00:00Z",
) -> dict:
    return {
        "occurrence_id": occurrence_id,
        "semantic_id": semantic_id,
        "project": project,
        "project_type": "cli",
        "run_id": "run-1",
        "commit": "abc123",
        "ts": ts,
        "action": action,
        "context": {
            "severity": severity,
            "confidence": "high",
            "evidence_count": 2,
            "cve_tier": 1,
            "history": {
                "verified": 1,
                "actions": {"verify": 2, "defer": 1},
                "cost": {"agent_calls": 3, "tokens": 100},
            },
        },
        "action_propensity": 0.5,
        "label_propensity": label_propensity,
        "outcome": {"verdict": verdict, "evidence_class": evidence_class},
        "cost": {
            "agent_calls": 1,
            "seconds": 2,
            "tokens": 100,
            "review_seconds": 1,
        },
        "policy": "legacy",
        "source": "test",
    }


def test_features_do_not_use_current_action_cost_or_outcome() -> None:
    original = _record()
    changed = copy.deepcopy(original)
    changed["action"] = "defer"
    changed["cost"] = {"agent_calls": 999, "tokens": 999999, "review_seconds": 999}
    changed["outcome"] = {"verdict": "fp", "evidence_class": "static"}

    assert extract_features(original) == extract_features(changed)
    policy = VerificationPolicy()
    assert policy.scores(original) == policy.scores(changed)
    assert policy.probabilities(original) == policy.probabilities(changed)


def test_propensities_sum_to_one_and_epsilon_is_explicit() -> None:
    record = _record()
    policy = VerificationPolicy(epsilon=0.2)
    decision = policy.decide(record)

    assert set(decision["scores"]) == set(ACTIONS)
    assert set(decision["propensities"]) == set(ACTIONS)
    assert sum(decision["probabilities"].values()) == pytest.approx(1.0)
    assert decision["epsilon"] == 0.2
    assert all(value >= 0.04 for value in decision["probabilities"].values())
    assert policy.probabilities(record, epsilon=1.0) == {
        action: pytest.approx(0.2) for action in ACTIONS
    }


@pytest.mark.parametrize("epsilon", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_epsilon_is_rejected(epsilon: float) -> None:
    with pytest.raises(ValueError, match="epsilon"):
        VerificationPolicy(epsilon=epsilon)


def test_semantic_dedup_prefers_trusted_evidence() -> None:
    static = _record("static", evidence_class="static", ts="2026-01-02")
    runtime = _record("runtime", evidence_class="runtime", ts="2026-01-01")
    unknown = _record(
        "unknown", semantic_id="other", verdict="unknown", evidence_class="manual"
    )

    unique = deduplicate_semantics([static, unknown, runtime])

    assert len(unique) == 2
    selected = next(record for record in unique if record["semantic_id"] == "semantic-1")
    assert selected["occurrence_id"] == "runtime"


def test_unknown_has_no_reward_or_realized_utility() -> None:
    unknown = _record(verdict="unknown", evidence_class="manual")

    assert record_utility(unknown) is None
    assert utility_details(unknown) is None


def test_trusted_tp_utility_subtracts_all_real_costs() -> None:
    details = utility_details(_record())

    assert details is not None
    assert details["reward"] > 0
    assert details["agent_cost"] == pytest.approx(0.05)
    assert details["token_cost"] == pytest.approx(0.001)
    assert details["review_cost"] == pytest.approx(0.01)
    assert details["utility"] == pytest.approx(details["reward"] - 0.061)


def test_static_tp_does_not_receive_trusted_tp_reward() -> None:
    static = utility_details(_record(evidence_class="static"))

    assert static is not None
    assert static["reward"] == 0


def test_experience_verdict_aliases_and_missing_label_propensity() -> None:
    runtime = _record(verdict="runtime-confirmed", evidence_class="runtime")
    static = _record(verdict="static-supported", evidence_class="static")
    unselected = _record()
    unselected["label_propensity"] = None

    assert utility_details(runtime)["reward"] > 0
    assert utility_details(static)["reward"] == 0
    assert train_policy([unselected])["training"]["labeled_actions"] == 0


def test_zero_and_one_label_training_are_deterministic_and_finite() -> None:
    empty = train_policy([])
    single = train_policy([_record()], seed=7)
    repeated = train_policy([_record()], seed=7)

    assert empty["training"]["status"] == "insufficient"
    assert single["training"]["labeled_actions"] == 1
    assert single == repeated
    decision = VerificationPolicy(single).decide(_record())
    assert sum(decision["probabilities"].values()) == pytest.approx(1.0)


def test_negative_utility_is_a_signed_regression_target() -> None:
    record = _record(verdict="fp")
    target = record_utility(record, record["action"])
    assert target is not None and target < 0

    model = train_policy([record])
    stats = model["training"]["target"]

    assert model["algorithm"] == "per-action-ridge-utility-regression"
    assert model["training"]["status"] == "ok"
    assert model["training"]["support"] == 1
    assert stats["negative"] == 1
    assert stats["positive"] == 0
    assert stats["max"] == pytest.approx(target)
    assert model["training"]["target_by_action"]["verify"]["mean"] == pytest.approx(
        target
    )
    assert VerificationPolicy(model).scores(record)["verify"] < 0


def test_unknown_and_invalid_propensity_are_not_training_targets() -> None:
    unknown = _record(verdict="unknown")
    unselected = _record("occ-2", semantic_id="semantic-2")
    unselected["label_propensity"] = None

    model = train_policy([unknown, unselected])

    assert model["training"]["status"] == "insufficient"
    assert model["training"]["support"] == 0
    assert model["training"]["target"]["support"] == 0
    assert model["training"]["skipped_unknown_outcome"] == 1
    assert model["training"]["skipped_invalid_propensity"] == 1


def test_insufficient_training_shadow_falls_back_to_legacy_baseline() -> None:
    record = _record(verdict="unknown", severity="medium")
    policy = VerificationPolicy(train_policy([record]))

    shadow = shadow_payload([record], policy, epsilon=1.0, seed=4)
    advice = shadow["recommendations"][0]

    assert shadow["status"] == "insufficient"
    assert shadow["reason"] == "no_known_utility_targets"
    assert advice["baseline_action"] == "deep_read"
    assert advice["candidate_action"] == "deep_read"
    assert advice["status"] == "insufficient"
    assert "shadow fallback" in advice["reasons"][-1]


def test_static_only_training_is_explicitly_unvalidated_in_shadow() -> None:
    record = _record(verdict="static-supported", evidence_class="static")
    model = train_policy([record])

    assert model["training"]["status"] == "ok"
    assert model["training"]["trusted_support"] == 0
    assert model["training"]["evidence_support"] == {"static": 1}

    shadow = shadow_payload([record], VerificationPolicy(model))
    assert shadow["status"] == "static-only"
    assert shadow["evidence_status"] == "static-only"
    assert shadow["reason"] == "no_trusted_utility_targets"
    assert shadow["recommendation_only"] is True
    assert shadow["state_change"] == "none"


def test_label_merge_preserves_identity_and_propensities() -> None:
    original = _record()
    original["label_propensity"] = None
    label = {
        "occurrence_id": original["occurrence_id"],
        "semantic_id": original["semantic_id"],
        "project": original["project"],
        "run_id": original["run_id"],
        "commit": original["commit"],
        "label_propensity": 0.25,
        "verdict": "human-confirmed",
        "evidence_class": "human",
    }

    merged = merge_labels([original], [label])

    assert original["outcome"]["verdict"] == "tp"
    assert merged[0]["outcome"] == {
        "verdict": "human-confirmed",
        "evidence_class": "human",
    }
    assert merged[0]["action_propensity"] == original["action_propensity"]
    assert merged[0]["label_propensity"] == 0.25
    assert merged[0]["semantic_id"] == original["semantic_id"]


def test_label_merge_rejects_identity_mismatch() -> None:
    label = {
        "occurrence_id": "occ-1",
        "semantic_id": "different-semantic",
        "label_propensity": 0.5,
        "verdict": "fp",
        "evidence_class": "manual",
    }

    with pytest.raises(ValueError, match="semantic_id mismatch"):
        merge_labels([_record()], [label])


def test_holdout_project_never_enters_training() -> None:
    train = _record(project="project-a")
    holdout = _record("occ-holdout", semantic_id="holdout", project="project-b")

    model = train_policy([train, holdout], holdout_project="project-b")

    assert model["training"]["projects"] == ["project-a"]
    assert model["training"]["raw_records"] == 1
    assert model["validation"]["raw_records"] == 1
    assert model["training_data_hash"] == data_hash([train])
    assert model["validation_data_hash"] == data_hash([holdout])


def test_training_deduplicates_semantics_before_fitting() -> None:
    first = _record("first")
    second = _record("second", action="defer")

    model = train_policy([first, second])

    assert model["training"]["raw_records"] == 2
    assert model["training"]["unique_semantics"] == 1
    assert model["training"]["labeled_actions"] == 1


def test_replay_reports_support_coverage_projects_and_insufficient() -> None:
    matching = _record()
    unknown = _record(
        "unknown",
        semantic_id="unknown",
        project="project-b",
        action="defer",
        verdict="unknown",
        severity="low",
    )
    policy = VerificationPolicy()
    policy.weights["deep_read"][0] = 10.0
    replay = replay_policies([matching, unknown], policy)

    assert replay["baseline"]["support"] == 1
    assert replay["baseline"]["per_project"]["project-a"]["support"] == 1
    assert replay["baseline"]["label_coverage"] == 0.5
    assert replay["baseline"]["per_project"]["project-b"]["utility"] is None
    assert replay["baseline"]["per_project"]["project-b"]["status"] == "insufficient"
    assert replay["candidate"]["status"] == "insufficient"
    assert replay["candidate"]["utility"] is None
    assert replay["status"] == "insufficient"
    assert "uplift" not in replay
    assert "no causal uplift" in replay["evaluation"]


def test_shadow_is_recommendation_only_and_replayable(tmp_path: Path) -> None:
    records = [_record()]
    original = copy.deepcopy(records)
    model = train_policy(records, holdout_project="project-b")
    policy = VerificationPolicy(model, epsilon=0.1)

    first = shadow_payload(records, policy, epsilon=0.1, seed=11)
    second = shadow_payload(records, policy, epsilon=0.1, seed=11)

    assert records == original
    assert first == second
    assert first["recommendation_only"] is True
    assert first["state_change"] == "none"
    assert first["training_data_hash"] == model["training_data_hash"]
    assert first["validation_data_hash"] == model["validation_data_hash"]
    advice = first["recommendations"][0]
    assert advice["baseline_action"] == "verify"
    assert advice["candidate_action"] in ACTIONS
    assert advice["state_change"] == "none"
    assert set(advice["propensities"]) == set(ACTIONS)


def test_cli_train_shadow_replay_workflow_is_byte_replayable(tmp_path: Path) -> None:
    pool = tmp_path / "experience.jsonl"
    records = [
        _record(),
        _record("occ-2", semantic_id="semantic-2", project="project-b"),
    ]
    write_jsonl(pool, records)
    original_pool = pool.read_bytes()
    model_path = tmp_path / "policy.json"
    shadow_path = tmp_path / "shadow.json"
    replay_path = tmp_path / "replay.json"
    sample_path = tmp_path / "label-sample.jsonl"

    assert main(
        [
            "label-sample",
            "--pool",
            str(pool),
            "--output",
            str(sample_path),
            "--limit",
            "1",
            "--seed",
            "3",
        ]
    ) == 0
    sample = read_experience(sample_path)
    assert len(sample) == 1
    sample[0]["verdict"] = "human-confirmed"
    sample[0]["evidence_class"] = "human"
    write_jsonl(sample_path, sample)
    merged_path = tmp_path / "experience-labeled.jsonl"
    assert main(
        [
            "label-merge",
            "--pool",
            str(pool),
            "--labels",
            str(sample_path),
            "--output",
            str(merged_path),
        ]
    ) == 0
    merged = read_experience(merged_path)
    labeled = next(
        record
        for record in merged
        if record["occurrence_id"] == sample[0]["occurrence_id"]
    )
    assert labeled["outcome"]["verdict"] == "human-confirmed"
    assert labeled["label_propensity"] == sample[0]["label_propensity"]

    assert main(
        [
            "verify-train",
            "--pool",
            str(pool),
            "--output",
            str(model_path),
            "--holdout-project",
            "project-b",
            "--seed",
            "5",
        ]
    ) == 0
    model = json.loads(model_path.read_text(encoding="utf-8"))
    assert model["training"]["projects"] == ["project-a"]

    shadow_command = [
        "verify-shadow",
        "--pool",
        str(pool),
        "--train",
        str(model_path),
        "--output",
        str(shadow_path),
        "--epsilon",
        "0.1",
        "--seed",
        "9",
    ]
    assert main(shadow_command) == 0
    first_shadow = shadow_path.read_bytes()
    assert main(shadow_command) == 0
    assert shadow_path.read_bytes() == first_shadow
    assert pool.read_bytes() == original_pool
    assert read_experience(pool) == records

    assert main(
        [
            "verify-replay",
            "--pool",
            str(pool),
            "--train",
            str(model_path),
            "--holdout-project",
            "project-b",
            "--output",
            str(replay_path),
        ]
    ) == 0
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    assert replay["holdout_project"] == "project-b"
    assert replay["baseline"]["unique_semantics"] == 1


def test_outcome_flip_report_tracks_regressions_without_inventing_labels(tmp_path):
    baseline = [
        _record("a-1", semantic_id="s-1", verdict="tp"),
        _record("a-2", semantic_id="s-2", verdict="fp", evidence_class="static"),
        _record("a-3", semantic_id="s-3", verdict="tp", evidence_class="static"),
        _record("a-4", semantic_id="s-4", verdict="unknown"),
        _record("a-5", semantic_id="s-5", verdict="tp"),
    ]
    candidate = [
        _record("b-1", semantic_id="s-1", verdict="fp"),
        _record("b-2", semantic_id="s-2", verdict="tp"),
        _record("b-3", semantic_id="s-3", verdict="tp", evidence_class="static"),
        _record("b-4", semantic_id="s-4", verdict="fp"),
        _record("b-6", semantic_id="s-6", verdict="tp"),
    ]
    report = outcome_flip_report(baseline, candidate)
    assert report["status"] == "ok"
    assert report["common_semantics"] == 4
    assert report["paired_known_outcomes"] == 3
    assert report["counts"] == {
        "fail_to_pass": 1,
        "pass_to_fail": 1,
        "stable_tp": 1,
        "stable_non_tp": 0,
        "unknown_transition": 1,
    }
    assert report["fail_to_pass_rate"] == 1.0
    assert report["pass_to_fail_rate"] == 0.5
    assert [row["transition"] for row in report["transitions"]] == [
        "pass_to_fail",
        "fail_to_pass",
    ]
    assert outcome_flip_report(baseline, [])["status"] == "insufficient"

    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    output_path = tmp_path / "flips.json"
    write_jsonl(baseline_path, baseline)
    write_jsonl(candidate_path, candidate)
    assert main([
        "verify-flips",
        "--baseline", str(baseline_path),
        "--candidate", str(candidate_path),
        "--output", str(output_path),
    ]) == 0
    written = json.loads(output_path.read_text())
    assert written["paired_known_outcomes"] == 3
    assert written["evaluation"].startswith("observed per-semantic")
