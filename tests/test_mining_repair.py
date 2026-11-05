from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from audit_rsi.cli import main
from audit_rsi.mining_repair import (
    MiningRepairStore,
    evaluate_mining_repair,
    load_active_mining_repairs,
    propose_mining_repairs,
    render_mining_repair_context,
)
from audit_rsi.verification import write_jsonl

ROOT_CAUSE = "默认绑定回环地址且没有远程入口，因此不存在未授权远程访问。"


def _record(
    project: str,
    semantic: str,
    verdict: str,
    *,
    evidence: str = "runtime",
    run: str = "run-1",
    root_cause: str = ROOT_CAUSE,
) -> dict:
    occurrence = f"{project}/{run}/{semantic}"
    return {
        "occurrence_id": occurrence,
        "semantic_id": semantic,
        "project": project,
        "run_id": run,
        "ts": "2026-01-01T00:00:00Z",
        "action": "verify",
        "context": {"category": "authentication-bypass", "finding_id": semantic},
        "outcome": {"verdict": verdict, "evidence_class": evidence},
        "raw_for_ledger": {
            "occurrence_id": occurrence,
            "raw": {
                "title": f"{project} {semantic}",
                "category": "authentication-bypass",
                "root_cause": root_cause,
                "files": [f"src/{project}.py"],
            },
        },
    }


def _ledger(records: list[dict]) -> dict:
    return {
        "occurrences": {
            record["occurrence_id"]: record["raw_for_ledger"]
            for record in records
        }
    }


def _pool(records: list[dict]) -> list[dict]:
    return [
        {key: value for key, value in record.items() if key != "raw_for_ledger"}
        for record in records
    ]


def _training_pair(evidence: str = "runtime") -> list[dict]:
    return [
        _record("alpha", "sem-fp-a", "fp", evidence=evidence),
        _record("beta", "sem-fp-b", "fp", evidence=evidence, run="run-2"),
    ]


def _evaluation_pair() -> tuple[list[dict], list[dict]]:
    baseline = [
        _record("holdout", "sem-fp-h", "fp", run="before"),
        _record("holdout", "sem-tp-h", "runtime-confirmed", run="before"),
    ]
    candidate = [
        _record("holdout", "sem-tp-h", "runtime-confirmed", run="after"),
    ]
    return baseline, candidate


def test_shared_repair_publishes_loads_and_rolls_back(tmp_path: Path) -> None:
    training = _training_pair()
    candidate = propose_mining_repairs(
        _pool(training), ledger=_ledger(training)["occurrences"]
    )[0]
    assert candidate["proposal"]["scope"] == "shared"
    assert candidate["proposal"]["trusted_projects"] == ["alpha", "beta"]

    baseline, after = _evaluation_pair()
    evaluation = evaluate_mining_repair(
        candidate,
        _pool(baseline),
        _pool(after),
        holdout_projects=["holdout"],
    )
    assert evaluation["accepted"] is True
    assert evaluation["counts"]["false_positives_suppressed"] == 1
    assert evaluation["candidate"]["false_positive_rate"] == 0.0

    store = MiningRepairStore(tmp_path)
    version = store.apply(candidate, evaluation)
    target = tmp_path / version["target"]
    assert target.is_file()
    rules, errors = load_active_mining_repairs(tmp_path, "unseen-project")
    assert errors == []
    assert [rule["rule_id"] for rule in rules] == [candidate["rule_id"]]
    assert "已发布挖掘修复" in render_mining_repair_context(tmp_path, "unseen-project")

    rolled_back = store.rollback(version["version_id"])
    assert rolled_back["status"] == "rolled_back"
    assert not target.exists()
    assert load_active_mining_repairs(tmp_path, "unseen-project") == ([], [])


def test_project_repair_does_not_leak_to_other_projects(tmp_path: Path) -> None:
    training = [_record("alpha", "sem-fp-a", "fp")]
    candidate = propose_mining_repairs(
        _pool(training), ledger=_ledger(training)["occurrences"]
    )[0]
    assert candidate["proposal"]["scope"] == "project"
    baseline = [
        _record("alpha", "sem-fp-a", "fp", run="before"),
        _record("alpha", "sem-tp-a", "runtime-confirmed", run="before"),
    ]
    after = [_record("alpha", "sem-tp-a", "runtime-confirmed", run="after")]
    evaluation = evaluate_mining_repair(candidate, _pool(baseline), _pool(after))
    assert evaluation["accepted"] is True

    MiningRepairStore(tmp_path).apply(candidate, evaluation)
    own_rules, _ = load_active_mining_repairs(tmp_path, "alpha")
    other_rules, _ = load_active_mining_repairs(tmp_path, "beta")
    assert len(own_rules) == 1
    assert other_rules == []
    assert f"knowledge/project-rules/alpha/{candidate['rule_id']}.md" == candidate["target"]


def test_static_evidence_and_missing_shared_holdout_cannot_publish() -> None:
    training = _training_pair(evidence="static")
    candidate = propose_mining_repairs(
        _pool(training), ledger=_ledger(training)["occurrences"]
    )[0]
    baseline, after = _evaluation_pair()
    static_result = evaluate_mining_repair(
        candidate,
        _pool(baseline),
        _pool(after),
        holdout_projects=["holdout"],
    )
    assert static_result["status"] == "insufficient"
    assert "no_trusted_source_evidence" in static_result["reasons"]

    trusted = _training_pair()
    shared = propose_mining_repairs(
        _pool(trusted), ledger=_ledger(trusted)["occurrences"]
    )[0]
    missing_holdout = evaluate_mining_repair(shared, _pool(baseline), _pool(after))
    assert missing_holdout["status"] == "insufficient"
    assert "shared_holdout_required" in missing_holdout["reasons"]


def test_true_positive_loss_and_new_false_positive_are_rejected() -> None:
    training = _training_pair()
    candidate = propose_mining_repairs(
        _pool(training), ledger=_ledger(training)["occurrences"]
    )[0]
    baseline = [
        _record("holdout", "sem-fp-h", "fp", run="before"),
        _record("holdout", "sem-tp-1", "runtime-confirmed", run="before"),
        _record("holdout", "sem-tp-2", "runtime-confirmed", run="before"),
    ]
    lost = [_record("holdout", "sem-tp-1", "runtime-confirmed", run="after")]
    loss_result = evaluate_mining_repair(
        candidate,
        _pool(baseline),
        _pool(lost),
        holdout_projects=["holdout"],
    )
    assert loss_result["status"] == "rejected"
    assert "true_positive_regression" in loss_result["reasons"]

    new_fp = lost + [_record("holdout", "sem-new-fp", "fp", run="after")]
    fp_result = evaluate_mining_repair(
        candidate,
        _pool(baseline),
        _pool(new_fp),
        holdout_projects=["holdout"],
    )
    assert fp_result["status"] == "rejected"
    assert "new_false_positive_regression" in fp_result["reasons"]


def test_confirmed_pattern_requires_new_true_positive_without_regression() -> None:
    root_cause = "未认证管理端点允许远程修改配置。"
    training = [
        _record("alpha", "sem-tp-a", "runtime-confirmed", root_cause=root_cause),
        _record("beta", "sem-tp-b", "judge-approved", root_cause=root_cause),
    ]
    candidate = propose_mining_repairs(
        _pool(training), ledger=_ledger(training)["occurrences"]
    )[0]
    assert candidate["proposal"]["kind"] == "confirmed_pattern"
    baseline = [_record("holdout", "sem-control", "runtime-confirmed", run="before")]
    after = baseline + [
        _record("holdout", "sem-new-tp", "runtime-confirmed", run="after", root_cause=root_cause)
    ]
    evaluation = evaluate_mining_repair(
        candidate,
        _pool(baseline),
        _pool(after),
        holdout_projects=["holdout"],
    )
    assert evaluation["accepted"] is True
    assert evaluation["counts"]["new_true_positives"] == 1


def test_cli_cycle_runs_train_evaluate_publish_and_context(tmp_path: Path, monkeypatch) -> None:
    training = _training_pair()
    baseline, after = _evaluation_pair()
    train_path = tmp_path / "train.jsonl"
    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    ledger_path = tmp_path / "ledger.json"
    output_path = tmp_path / "cycle.json"
    write_jsonl(train_path, _pool(training))
    write_jsonl(baseline_path, _pool(baseline))
    write_jsonl(candidate_path, _pool(after))
    ledger_path.write_text(json.dumps(_ledger(training)), encoding="utf-8")
    monkeypatch.setattr("audit_rsi.cli.REPO_ROOT", tmp_path)

    assert main([
        "mining-repair-cycle",
        "--train-pool", str(train_path),
        "--baseline", str(baseline_path),
        "--candidate-pool", str(candidate_path),
        "--ledger", str(ledger_path),
        "--holdout-project", "holdout",
        "--output", str(output_path),
    ]) == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["accepted"] == 1
    assert report["published"] == 1
    version_id = report["results"][0]["publication"]["version_id"]
    assert (tmp_path / report["results"][0]["publication"]["target"]).is_file()

    assert main([
        "mining-repair-rollback",
        "--version", version_id,
    ]) == 0
    assert load_active_mining_repairs(tmp_path, "holdout") == ([], [])


def test_candidate_tampering_is_rejected(tmp_path: Path) -> None:
    training = _training_pair()
    candidate = propose_mining_repairs(
        _pool(training), ledger=_ledger(training)["occurrences"]
    )[0]
    baseline, after = _evaluation_pair()
    evaluation = evaluate_mining_repair(
        candidate,
        _pool(baseline),
        _pool(after),
        holdout_projects=["holdout"],
    )
    tampered = dict(candidate)
    tampered["content"] = "tampered\n"
    with pytest.raises(ValueError, match="identity"):
        MiningRepairStore(tmp_path).apply(tampered, evaluation)


def test_mining_entrypoint_script_loads_published_rules(tmp_path: Path) -> None:
    training = _training_pair()
    candidate = propose_mining_repairs(
        _pool(training), ledger=_ledger(training)["occurrences"]
    )[0]
    baseline, after = _evaluation_pair()
    evaluation = evaluate_mining_repair(
        candidate,
        _pool(baseline),
        _pool(after),
        holdout_projects=["holdout"],
    )
    MiningRepairStore(tmp_path).apply(candidate, evaluation)
    script = Path(__file__).resolve().parents[1] / "scripts/mine/repair_context.py"
    completed = subprocess.run(
        [
            "python3",
            str(script),
            "--root",
            str(tmp_path),
            "--project",
            "holdout",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "已发布挖掘修复" in completed.stdout
    assert candidate["rule_id"] in completed.stdout
    assert ROOT_CAUSE in completed.stdout
