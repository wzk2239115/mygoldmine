import json
import sys

from scripts.workflow import refine_worker as refine


def item(tmp_path, finding_id):
    key = f"demo/r1/{finding_id}"
    report = tmp_path / "demo/r1/audit-report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('{"findings":[]}')
    return {
        "occurrence_id": key,
        "semantic_id": f"sem-{finding_id}",
        "project": "demo",
        "id": finding_id,
        "severity": "high",
        "confidence": "medium",
        "report": str(report),
        "raw": {"root_cause": finding_id, "evidence": []},
    }


def test_loop_waits_for_late_findings_instead_of_exiting_when_empty(tmp_path, monkeypatch):
    latest = {"demo/r1/F-01": item(tmp_path, "F-01")}
    monkeypatch.setattr(refine, "DATA", tmp_path / "data")
    monkeypatch.setattr(refine, "QUEUE", refine.DATA / "refine-queue.json")
    monkeypatch.setattr(refine, "REFINE", refine.DATA / "refine-state.json")
    monkeypatch.setattr(refine, "PAUSE", refine.DATA / "refine.pause")
    monkeypatch.setattr(refine, "STOP", refine.DATA / "refine.stop")
    monkeypatch.setattr(refine, "LOCK", refine.DATA / ".refine-worker.lock")
    monkeypatch.setattr(refine, "TRAJECTORY", tmp_path / "refine.jsonl")
    refine.DATA.mkdir(parents=True)
    (refine.DATA / "auto-state.json").write_text('{"findings":{}}')
    (refine.DATA / "refine-state.json").write_text('{"findings":{}}')
    (refine.DATA / "curated.json").write_text('{}')
    (refine.DATA / "state.json").write_text('{}')
    monkeypatch.setattr(refine.base.finding_ledger, "build_ledger", lambda: {})
    monkeypatch.setattr(refine.base, "latest_findings", lambda ledger: latest)
    monkeypatch.setattr(
        refine.base.finding_ledger,
        "merge_manual_state",
        lambda ledger, payloads: payloads[0].get("findings", {}),
    )
    monkeypatch.setattr(
        refine.base.finding_ledger,
        "identified_states",
        lambda states, ledger: states,
    )
    sleeps = []

    def late_arrival(_):
        sleeps.append(1)
        if len(sleeps) == 1:
            latest["demo/r1/F-02"] = item(tmp_path, "F-02")
        else:
            refine.STOP.touch()

    monkeypatch.setattr(refine.time, "sleep", late_arrival)
    monkeypatch.setattr(
        sys,
        "argv",
        ["refine_worker.py", "--loop", "--batch", "10", "--interval", "1"],
    )

    assert refine.main() == 0
    assert len(sleeps) == 2
    state = json.loads(refine.REFINE.read_text())
    assert set(state["findings"]) == {"demo/r1/F-01", "demo/r1/F-02"}
    queue = json.loads(refine.QUEUE.read_text())
    assert queue["stats"]["total"] == 2
    assert queue["stats"]["pending"] == 0
