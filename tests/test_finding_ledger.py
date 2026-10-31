import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "scripts" / "workflow"
sys.path.insert(0, str(WORKFLOW))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger_module = load_module("finding_ledger", WORKFLOW / "finding_ledger.py")
build_state = load_module("build_state", WORKFLOW / "build_state.py")
refine = load_module("refine_worker", WORKFLOW / "refine_worker.py")


def write_run(
    runs_root,
    project,
    run_id,
    findings,
    started_at,
    *,
    complete=True,
    exit_code=0,
    state="completed",
    draft=False,
):
    run_dir = runs_root / project / run_id
    run_dir.mkdir(parents=True)
    report = {"generated_at": started_at, "findings": findings}
    if draft:
        report["draft"] = True
    (run_dir / "audit-report.json").write_text(json.dumps(report), encoding="utf-8")
    (run_dir / "run-meta.json").write_text(
        json.dumps(
            {
                "started_at": started_at,
                "ended_at": started_at,
                "reports_complete": complete,
                "exit_code": exit_code,
            }
        ),
        encoding="utf-8",
    )
    status_dir = runs_root / project / f"{run_id}.meta"
    status_dir.mkdir()
    (status_dir / "status.json").write_text(json.dumps({"state": state}), encoding="utf-8")
    return run_dir


def finding(finding_id, title, path="src/example.py", **extra):
    return {
        "id": finding_id,
        "title": title,
        "severity": "high",
        "evidence": [{"path": path, "line": 10}],
        **extra,
    }


def test_history_only_findings_survive_and_occurrence_identity_is_explicit(tmp_path):
    runs = tmp_path / "runs"
    write_run(runs, "p", "r1", [finding("F-1", "历史独有问题")], "2026-01-01T00:00:00Z")
    write_run(runs, "p", "r2", [finding("F-2", "最新报告问题", "src/other.py")], "2026-01-02T00:00:00Z")

    ledger = ledger_module.build_ledger(runs, tmp_path)
    latest = ledger_module.latest_occurrences(ledger)

    assert ledger["schema_version"] == 2
    assert set(latest) == {"p/r1/F-1", "p/r2/F-2"}
    assert latest["p/r1/F-1"]["semantic_id"] != latest["p/r2/F-2"]["semantic_id"]
    assert ledger["latest_by_project"]["p"]["run_id"] == "r2"


def test_same_legacy_id_with_different_meanings_requires_specific_identity(tmp_path):
    runs = tmp_path / "runs"
    write_run(
        runs,
        "p",
        "r1",
        [
            finding("F-1", "第一种根因", "src/a.py"),
            finding("F-1", "第二种根因", "src/b.py"),
        ],
        "2026-01-01T00:00:00Z",
    )

    ledger = ledger_module.build_ledger(runs, tmp_path)
    first = ledger["occurrences"]["p/r1/F-1"]
    second = ledger["occurrences"]["p/r1/F-1~2"]

    assert first["semantic_id"] != second["semantic_id"]
    assert len(ledger["indexes"]["legacy_to_semantics"]["p:F-1"]) == 2
    assert ledger_module.resolve_reference(ledger, project="p", finding_id="F-1") == []
    assert ledger_module.resolve_reference(ledger, occurrence_id="p/r1/F-1~2") == ["p/r1/F-1~2"]
    assert ledger_module.merge_manual_state(ledger, [{"p:F-1": {"status": "closed"}}]) == {}


@pytest.mark.parametrize(
    "raw",
    [
        {"verified": "true"},
        {"verified": False, "verdict": "unverified"},
        {"verified": True, "verdict": "unverified"},
        {"verification": "verified in the audit narrative"},
        {"verdict": "perhaps"},
        {"verdict": "unknown"},
    ],
)
def test_verified_is_strict_and_never_inferred_from_prose(raw):
    assert ledger_module.is_verified(raw) is False


def test_explicit_confirmed_verdict_is_verified():
    assert ledger_module.is_verified({"verified": False, "verdict": "confirmed"}) is True
    assert ledger_module.is_verified({"verification": {"status": "reproduced"}}) is True


def test_unknown_verify_verdict_does_not_enter_reproduce(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    run_dir = write_run(runs, "p", "r1", [finding("F-1", "待验证问题")], "2026-01-01T00:00:00Z")
    ledger = ledger_module.build_ledger(runs, tmp_path)
    latest = ledger_module.latest_occurrences(ledger)
    verify_dir = run_dir / "verify" / "case"
    verify_dir.mkdir(parents=True)
    report_path = verify_dir / "verify-report.json"
    monkeypatch.setattr(build_state, "RUNS", runs)
    monkeypatch.setattr(build_state, "ROOT", tmp_path)

    report_path.write_text(
        json.dumps({"ended_at": "2026-01-03T00:00:00Z", "results": [{"id": "F-1", "verdict": "needs-review"}]}),
        encoding="utf-8",
    )
    assert build_state.build_verify_state(latest, set(), ledger) == {}

    report_path.write_text(
        json.dumps({"ended_at": "2026-01-04T00:00:00Z", "results": [{"id": "F-1", "verdict": "confirmed"}]}),
        encoding="utf-8",
    )
    state = build_state.build_verify_state(latest, set(), ledger)
    assert state["p/r1/F-1"]["status"] == "reproduce"
    assert state["p/r1/F-1"]["verifyVerdict"] == "confirmed"


def test_draft_or_incomplete_run_does_not_replace_complete_history(tmp_path):
    runs = tmp_path / "runs"
    write_run(runs, "p", "r1", [finding("F-1", "完整报告")], "2026-01-01T00:00:00Z")
    write_run(
        runs,
        "p",
        "r2",
        [finding("F-1", "草稿覆盖", "src/draft.py"), finding("F-3", "草稿独有")],
        "2026-01-02T00:00:00Z",
        complete=False,
        state="running",
        draft=True,
    )

    ledger = ledger_module.build_ledger(runs, tmp_path)

    assert set(ledger["occurrences"]) == {"p/r1/F-1"}
    assert ledger["latest_by_project"]["p"]["run_id"] == "r1"


def test_legacy_project_id_state_is_read_for_unambiguous_semantic(tmp_path):
    runs = tmp_path / "runs"
    write_run(runs, "p", "r1", [finding("f-1", "兼容旧状态")], "2026-01-01T00:00:00Z")
    ledger = ledger_module.build_ledger(runs, tmp_path)
    semantic_id = ledger["occurrences"]["p/r1/f-1"]["semantic_id"]

    states = ledger_module.merge_manual_state(
        ledger,
        [
            {"p:F-1": {"status": "triage", "notes": "legacy"}},
            {
                "schema_version": 2,
                "findings": {semantic_id: {"notes": "semantic"}},
                "occurrences": {"p/r1/f-1": {"status": "closed"}},
            },
        ],
    )

    assert states["p/r1/f-1"]["status"] == "closed"
    assert states["p/r1/f-1"]["notes"] == "semantic"
    legacy = ledger_module.legacy_state_view(states, ledger)
    assert legacy["p:F-1"]["occurrence_id"] == "p/r1/f-1"
    assert legacy["p:F-1"]["semantic_id"] == semantic_id


def test_archived_finding_recomputes_and_wakes_on_confirmed_evidence():
    item = {
        "project": "p",
        "severity": "low",
        "raw": {"title": "低危问题"},
        "raw_hash": "raw-v1",
        "report_hash": "report-v1",
    }
    key = "p/r1/F-1"
    latest = {key: item}
    old_hash = refine.source_hash(item, {})
    archived = {key: {"status": "archived", "source_hash": old_hash}}
    confirmed = {key: {"verifyVerdict": "confirmed"}}

    assert refine.needs_processing(key, latest, confirmed, archived, {}) is True
    status, _, _ = refine.classify(item, confirmed[key], refine.score(item, confirmed[key]), "p/r0/F-0")
    assert status == "reproduce"
    new_hash = refine.source_hash(item, confirmed[key])
    assert new_hash != old_hash
    assert refine.needs_processing(
        key, latest, confirmed, {key: {"status": "reproduce", "source_hash": new_hash}}, {}
    ) is False


@pytest.mark.parametrize("severity", ["high", "critical"])
def test_weak_duplicate_fingerprint_does_not_archive_high_severity(severity):
    item = {"project": "p", "severity": severity, "raw": {}}
    status, reason, duplicate_of = refine.classify(item, {}, 40, "p/r0/F-0")
    assert status == "triage"
    assert "弱指纹" in reason
    assert duplicate_of == ""


def test_low_severity_duplicate_can_still_archive():
    item = {"project": "p", "severity": "low", "raw": {}}
    status, _, duplicate_of = refine.classify(item, {}, 3, "p/r0/F-0")
    assert status == "archived"
    assert duplicate_of == "p/r0/F-0"


def redteam_result(run_dir):
    import hashlib

    flag = "FLAG{deterministic-test}"
    output = f"victim response: {flag}"
    flag_hash = hashlib.sha256(flag.encode()).hexdigest()
    output_hash = hashlib.sha256(output.encode()).hexdigest()
    provenance = {
        "source": "tool_output",
        "event_id": "tool-1",
        "capture_event_id": "capture-1",
        "output_sha256": output_hash,
        "flag_sha256": flag_hash,
    }
    (run_dir / "flag.txt").write_text(flag + "\n", encoding="utf-8")
    records = [
        {
            "kind": "tool_result",
            "event_id": "tool-1",
            "output": output,
            "output_sha256": output_hash,
        },
        {
            "kind": "flag_capture",
            "event_id": "capture-1",
            "tool_event_id": "tool-1",
            "output_sha256": output_hash,
            "flag_sha256": flag_hash,
        },
    ]
    (run_dir / "trace.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    judge = {
        "verdict": "approved",
        "intended_vulnerability": True,
        "flag_provenance": True,
        "no_cheat": True,
        "environment_plausible": True,
        "reproducible": True,
        "minimal": True,
        "confidence": "high",
        "reason": "verified tool output",
        "concerns": [],
        "recommended_status": "runtime-validated",
    }
    document = {
        "status": "judge_approved",
        "flag_sha256": flag_hash,
        "judge": judge,
        "flag_provenance_verified": {**provenance, "verified": True},
        "result": {
            "status": "flag_captured",
            "captured": True,
            "answer": flag,
            "flag_provenance": provenance,
        },
    }
    return document


def test_review_requires_complete_judge_and_deterministic_provenance(tmp_path):
    run_dir = tmp_path / "redteam"
    run_dir.mkdir()
    result_path = run_dir / "result.json"
    document = redteam_result(run_dir)

    assert build_state.verified_redteam_provenance(result_path, document)["verified"] is True

    del document["flag_provenance_verified"]
    assert build_state.verified_redteam_provenance(result_path, document) is None


def test_legacy_judge_approved_alone_does_not_enter_review(tmp_path):
    run_dir = tmp_path / "redteam"
    run_dir.mkdir()
    document = redteam_result(run_dir)
    document["judge"] = {"verdict": "approved"}

    assert build_state.verified_redteam_provenance(run_dir / "result.json", document) is None
