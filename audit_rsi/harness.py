"""Auditable, non-mutating harness candidate proposals and validation."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .verification import outcome_flip_gate

SCHEMA_VERSION = 1
ALLOWED_SURFACES = frozenset({
    "runtime_control.model_timeout_and_retry",
    "runtime_control.agent_deadline",
    "scenario.launch_and_healthcheck",
    "scenario.reachability_and_attacker_harness",
    "scenario.coverage",
    "agent_loop.and_tool_adapter",
    "agent.loop_and_recovery",
    "agent.structured_output_middleware",
    "lab.lifecycle_and_recovery",
    "tool.middleware_and_error_recovery",
})


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _candidate_id(proposal: Mapping[str, Any]) -> str:
    return f"hcand_{_digest(proposal)[:16]}"


def propose_harness_candidates(
    weakness_report: Mapping[str, Any],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be positive")
    if weakness_report.get("mutation") != "none":
        raise ValueError("weakness evidence must be non-mutating")
    candidates = []
    for group in weakness_report.get("groups", [])[:limit]:
        surface = str(group.get("editable_surface") or "")
        occurrences = sorted(set(group.get("occurrence_ids", [])))
        if surface not in ALLOWED_SURFACES:
            raise ValueError(f"unsupported editable surface: {surface}")
        if int(group.get("support", 0) or 0) < 1 or not occurrences:
            continue
        proposal = {
            "project_type": str(group.get("project_type") or "unknown"),
            "attacker_model": str(group.get("attacker_model") or "unknown"),
            "failure_class": str(group.get("failure_class") or "unknown"),
            "severity": str(group.get("severity") or "unknown"),
            "editable_surface": surface,
            "occurrence_ids": occurrences,
            "support": int(group["support"]),
            "event_support": int(group.get("event_support", 0) or 0),
            "mean_agent_calls": float(group.get("mean_agent_calls", 0) or 0),
            "mean_seconds": float(group.get("mean_seconds", 0) or 0),
            "evidence_classes": sorted(group.get("evidence_classes", [])),
        }
        candidates.append(
            {
                "schema_version": SCHEMA_VERSION,
                "candidate_id": _candidate_id(proposal),
                "status": "proposal_only",
                "proposal": proposal,
                "change": {
                    "surface": surface,
                    "operation": "bounded_adjustment",
                    "parameters": {},
                    "preserve": "all unrelated behavior",
                },
                "intent": {
                    "target_failure": proposal["failure_class"],
                    "expected": "reduce targeted failure without pass-to-fail regression",
                },
                "evidence": {
                    "source_data_hash": _digest(proposal),
                    "requires_candidate_validation": True,
                },
                "validation": {
                    "status": "pending",
                    "required": ["paired_outcome_flip_gate"],
                },
                "mutation": "none",
            }
        )
    return candidates


def validate_harness_candidate(
    candidate: Mapping[str, Any],
    flip_report: Mapping[str, Any],
) -> dict[str, Any]:
    proposal = candidate.get("proposal")
    if not isinstance(proposal, Mapping):
        raise ValueError("candidate proposal is required")
    if candidate.get("candidate_id") != _candidate_id(proposal):
        raise ValueError("candidate identity does not match its proposal")
    if candidate.get("mutation") != "none":
        raise ValueError("candidate must be non-mutating")
    gate = flip_report.get("gate") or outcome_flip_gate(flip_report)
    status = "accepted" if gate.get("accepted") else str(gate.get("status") or "rejected")
    validated = dict(candidate)
    validated["status"] = "validated" if status == "accepted" else status
    validated["validation"] = {
        "status": status,
        "required": ["paired_outcome_flip_gate"],
        "reasons": list(gate.get("reasons", [])),
        "metrics": dict(gate.get("metrics", {})),
        "evidence_hash": _digest(flip_report),
    }
    validated["mutation"] = "none"
    return validated
