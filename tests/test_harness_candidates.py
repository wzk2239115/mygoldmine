import json

import pytest

from audit_rsi.cli import main
from audit_rsi.harness import propose_harness_candidates, validate_harness_candidate


def weakness_report():
    return {
        "mutation": "none",
        "groups": [{
            "project_type": "cli",
            "attacker_model": "model-a",
            "failure_class": "model_timeout",
            "severity": "high",
            "editable_surface": "runtime_control.model_timeout_and_retry",
            "occurrence_ids": ["demo/r1/F-01"],
            "support": 1,
            "event_support": 2,
            "mean_agent_calls": 3,
            "mean_seconds": 12,
            "evidence_classes": ["none"],
        }],
    }


def accepted_flips():
    return {
        "gate": {
            "accepted": True,
            "status": "accepted",
            "reasons": [],
            "metrics": {"paired_coverage": 1.0, "pass_to_fail": 0, "fail_to_pass": 1},
        }
    }


def test_proposal_is_deterministic_bounded_and_non_mutating(tmp_path):
    first = propose_harness_candidates(weakness_report())
    second = propose_harness_candidates(weakness_report())
    assert first == second
    assert len(first) == 1
    candidate = first[0]
    assert candidate["candidate_id"].startswith("hcand_")
    assert candidate["change"]["operation"] == "bounded_adjustment"
    assert candidate["change"]["preserve"] == "all unrelated behavior"
    assert candidate["mutation"] == "none"
    assert candidate["validation"]["status"] == "pending"

    validated = validate_harness_candidate(candidate, accepted_flips())
    assert validated["status"] == "validated"
    assert validated["validation"]["status"] == "accepted"
    assert validated["mutation"] == "none"

    rejected = validate_harness_candidate(candidate, {
        "gate": {"accepted": False, "status": "rejected", "reasons": ["pass_to_fail_regression"]}
    })
    assert rejected["status"] == "rejected"

    tampered = dict(candidate)
    tampered["candidate_id"] = "hcand_tampered"
    with pytest.raises(ValueError, match="identity"):
        validate_harness_candidate(tampered, accepted_flips())

    weakness = tmp_path / "weakness.json"
    candidates_path = tmp_path / "candidates.json"
    validated_path = tmp_path / "validated.json"
    flips_path = tmp_path / "flips.json"
    weakness.write_text(json.dumps(weakness_report()))
    flips_path.write_text(json.dumps(accepted_flips()))
    assert main([
        "harness-propose", "--weakness", str(weakness), "--output", str(candidates_path)
    ]) == 0
    candidate_file = json.loads(candidates_path.read_text())[0]
    candidate_input = tmp_path / "candidate.json"
    candidate_input.write_text(json.dumps(candidate_file))
    assert main([
        "harness-validate",
        "--candidate", str(candidate_input),
        "--flips", str(flips_path),
        "--output", str(validated_path),
    ]) == 0
    assert json.loads(validated_path.read_text())["status"] == "validated"
