"""Turn red-team artifacts into provenance-checked, role-aware experiences."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]


def _contracts():
    path = REPO_ROOT / "scripts" / "redteam" / "contracts.py"
    spec = importlib.util.spec_from_file_location("goldmine_redteam_contracts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _seconds(rows: Iterable[Mapping[str, Any]]) -> float:
    timestamps = []
    for row in rows:
        try:
            timestamps.append(datetime.fromisoformat(str(row.get("ts", ""))))
        except ValueError:
            continue
    if len(timestamps) < 2:
        return 0.0
    return max(0.0, (max(timestamps) - min(timestamps)).total_seconds())


def _action(content: str) -> str:
    try:
        payload = json.loads(content)
    except ValueError:
        return "invalid"
    action = payload.get("action") if isinstance(payload, dict) else None
    return action if action in {"shell", "done"} else "invalid"


def _steps(
    occurrence_id: str,
    agent_rows: list[Mapping[str, Any]],
    trace_rows: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    steps = []
    tool_calls = 0
    tool_failures = 0
    invalid_responses = 0
    for row in agent_rows:
        role = row.get("role")
        if role == "assistant" and _action(str(row.get("content", ""))) == "invalid":
            invalid_responses += 1
    for row in trace_rows:
        if row.get("kind") != "tool_result":
            continue
        tool_calls += 1
        returncode = int(row.get("returncode", 0) or 0)
        tool_failures += int(returncode != 0)
        steps.append(
            {
                "occurrence_id": occurrence_id,
                "event_id": str(row.get("event_id", "")),
                "ts": str(row.get("ts", "")),
                "role": "attacker",
                "action": "shell",
                "status": "failed" if returncode else "completed",
                "returncode": returncode,
                "output_sha256": str(row.get("output_sha256", "")),
            }
        )
    for row in agent_rows:
        if row.get("role") != "done":
            continue
        steps.append(
            {
                "occurrence_id": occurrence_id,
                "event_id": str(row.get("tool_event_id", "")),
                "ts": "",
                "role": "attacker",
                "action": "done",
                "status": "captured" if row.get("captured") else "completed",
                "returncode": 0,
                "output_sha256": str(row.get("output_sha256", "")),
            }
        )
    return steps, {
        "tool_calls": tool_calls,
        "tool_failures": tool_failures,
        "invalid_responses": invalid_responses,
    }


def build_redteam_experience(run_dir: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_dir = Path(run_dir)
    payload = _json(run_dir / "result.json", {})
    result = _mapping(payload.get("result"))
    finding = _mapping(_json(run_dir / "finding.json", {}))
    agent_rows = _jsonl(run_dir / "agent.jsonl")
    trace_rows = _jsonl(run_dir / "trace.jsonl")
    project = str(payload.get("project") or finding.get("project") or run_dir.parent.name)
    run_id = str(payload.get("run_id") or run_dir.name)
    finding_id = str(finding.get("id") or finding.get("finding_id") or "unknown")
    occurrence_id = str(
        finding.get("occurrence_id")
        or f"{project}/{finding.get('run_id') or run_id}/{finding_id}"
    )
    semantic_id = str(finding.get("semantic_id") or occurrence_id)
    steps, behavior = _steps(occurrence_id, agent_rows, trace_rows)

    provenance = None
    try:
        provenance = _contracts().recompute_flag_provenance(run_dir, payload)
    except Exception:
        provenance = None
    status = str(result.get("status", "unknown"))
    judge = _mapping(result.get("judge"))
    judge_approved = (
        status in {"judge_approved", "runtime-validated"}
        and judge.get("verdict") == "approved"
    )
    if judge_approved and provenance and result.get("flag_provenance_verified") == provenance:
        outcome = {
            "verdict": "judge-approved",
            "evidence_class": "judge",
            "label_scope": "occurrence",
            "origin": "redteam",
            "reward_eligible": True,
        }
        label_propensity = 1.0
        label_assignment = "deterministic-judge-provenance"
    elif status == "flag_captured" and provenance:
        outcome = {
            "verdict": "runtime-confirmed",
            "evidence_class": "runtime",
            "label_scope": "occurrence",
            "origin": "redteam",
            "reward_eligible": True,
        }
        label_propensity = 1.0
        label_assignment = "deterministic-runtime-provenance"
    else:
        outcome = {
            "verdict": "unknown",
            "evidence_class": "none",
            "label_scope": "occurrence",
            "origin": "redteam",
            "reward_eligible": False,
        }
        label_propensity = None
        label_assignment = "unverified-or-negative-outcome"

    evidence = finding.get("evidence")
    record = {
        "schema_version": 1,
        "occurrence_id": occurrence_id,
        "semantic_id": semantic_id,
        "project": project,
        "project_type": str(finding.get("project_type") or "unknown"),
        "run_id": run_id,
        "commit": str(finding.get("commit") or ""),
        "ts": str(payload.get("finished_at") or ""),
        "action": "verify",
        "context": {
            "finding_id": finding_id,
            "severity": str(finding.get("severity") or "unknown").lower(),
            "confidence": str(finding.get("confidence") or "unknown").lower(),
            "category": str(finding.get("category") or "unknown"),
            "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            "redteam": behavior,
        },
        "action_propensity": 1.0,
        "label_propensity": label_propensity,
        "outcome": outcome,
        "cost": {
            "agent_calls": sum(row.get("role") == "assistant" for row in agent_rows),
            "seconds": _seconds(trace_rows),
            "tokens": 0,
            "review_seconds": 0,
        },
        "policy": {
            "name": "redteam-agent",
            "version": 1,
            "model": str(result.get("model") or "unknown"),
        },
        "source": {
            "trajectory": "redteam",
            "decision": status,
            "outcome_sources": ["redteam"],
            "label_scope": "occurrence",
            "label_assignment": label_assignment,
            "cost_estimated": True,
            "cost_observed": ["agent_calls", "seconds"],
            "audit_run_id": str(finding.get("run_id") or ""),
            "failure_class": None if outcome["verdict"] != "unknown" else status,
            "roles": {
                "attacker": str(result.get("model") or "unknown"),
                "victim": "isolated-service",
                "judge": "independent" if judge else "not-run",
            },
            "provenance_verified": bool(provenance),
        },
    }
    return record, steps


def scan_redteam_runs(runs_root: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = Path(runs_root)
    records = []
    steps = []
    for result_path in sorted(root.glob("*/*/result.json")):
        record, run_steps = build_redteam_experience(result_path.parent)
        records.append(record)
        steps.extend(run_steps)
    records.sort(key=lambda row: (row["project"], row["occurrence_id"], row["run_id"]))
    steps.sort(key=lambda row: (row["occurrence_id"], row["event_id"], row["action"]))
    return records, steps
