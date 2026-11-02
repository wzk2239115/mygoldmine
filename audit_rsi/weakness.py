"""Deterministic weakness mining for red-team harness improvement evidence."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

EDITABLE_SURFACES = {
    "model_timeout": "runtime_control.model_timeout_and_retry",
    "agent_timeout": "runtime_control.agent_deadline",
    "lab_unhealthy": "scenario.launch_and_healthcheck",
    "not_captured": "scenario.reachability_and_attacker_harness",
    "agent_error": "agent_loop.and_tool_adapter",
    "lab_error": "lab.lifecycle_and_recovery",
    "tool_failure": "tool.middleware_and_error_recovery",
    "invalid_response": "agent.structured_output_middleware",
    "blocked_no_lab": "scenario.coverage",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _surface(failure_class: str) -> str:
    return EDITABLE_SURFACES.get(failure_class, "agent.loop_and_recovery")


def mine_redteam_weaknesses(
    records: Iterable[Mapping[str, Any]],
    steps: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    groups: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    by_occurrence = {
        str(record.get("occurrence_id", "")): record for record in records
    }

    def add(record, failure_class, event_id=""):
        source = _mapping(record.get("source"))
        context = _mapping(record.get("context"))
        roles = _mapping(source.get("roles"))
        signature = (
            str(record.get("project_type") or "unknown"),
            str(roles.get("attacker") or "unknown"),
            failure_class,
            str(context.get("severity") or "unknown"),
            _surface(failure_class),
        )
        group = groups.setdefault(
            signature,
            {
                "project_type": signature[0],
                "attacker_model": signature[1],
                "failure_class": signature[2],
                "severity": signature[3],
                "editable_surface": signature[4],
                "occurrences": set(),
                "event_support": 0,
                "agent_calls": 0,
                "seconds": 0.0,
                "evidence_classes": set(),
            },
        )
        group["occurrences"].add(str(record.get("occurrence_id", "")))
        group["event_support"] += 1
        cost = _mapping(record.get("cost"))
        group["agent_calls"] += int(cost.get("agent_calls", 0) or 0)
        group["seconds"] += float(cost.get("seconds", 0) or 0)
        outcome = _mapping(record.get("outcome"))
        group["evidence_classes"].add(str(outcome.get("evidence_class") or "unknown"))

    for record in by_occurrence.values():
        source = _mapping(record.get("source"))
        failure_class = str(source.get("failure_class") or "")
        if failure_class:
            add(record, failure_class)
        behavior = _mapping(_mapping(record.get("context")).get("redteam"))
        if int(behavior.get("invalid_responses", 0) or 0) > 0:
            add(record, "invalid_response")
    for step in steps:
        returncode = int(step.get("returncode", 0) or 0)
        if not returncode:
            continue
        occurrence = str(step.get("occurrence_id", ""))
        record = by_occurrence.get(occurrence)
        if record is not None:
            add(record, "tool_failure", str(step.get("event_id", "")))

    rows = []
    for group in groups.values():
        support = len(group["occurrences"])
        rows.append(
            {
                "project_type": group["project_type"],
                "attacker_model": group["attacker_model"],
                "failure_class": group["failure_class"],
                "severity": group["severity"],
                "editable_surface": group["editable_surface"],
                "support": support,
                "event_support": group["event_support"],
                "occurrence_ids": sorted(group["occurrences"]),
                "mean_agent_calls": group["agent_calls"] / support if support else 0.0,
                "mean_seconds": group["seconds"] / support if support else 0.0,
                "evidence_classes": sorted(group["evidence_classes"]),
                "status": "candidate_only",
            }
        )
    rows.sort(
        key=lambda row: (
            -row["support"],
            -row["event_support"],
            row["failure_class"],
            row["attacker_model"],
            row["project_type"],
        )
    )
    return {
        "schema_version": 1,
        "evaluation": (
            "deterministic verifier-grounded failure signatures; "
            "no automatic harness edit or causal attribution"
        ),
        "status": "ok" if rows else "insufficient",
        "group_count": len(rows),
        "groups": rows,
        "mutation": "none",
        "requires_candidate_validation": True,
    }
