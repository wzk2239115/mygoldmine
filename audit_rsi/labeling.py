"""Deterministic stratified review sampling and inverse-propensity weights."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

DEFAULT_MAX_WEIGHT = 20.0
DEFAULT_HIGH_SCORE_FRACTION = 0.6
SENSITIVE_CONTEXT_KEYS = frozenset(
    {
        "adjudication",
        "curated",
        "evidence",
        "judge",
        "outcome",
        "raw",
        "reason",
        "root_cause",
        "title",
        "validation",
        "verdict",
        "verify_verdict",
    }
)


def _score(candidate: Mapping[str, Any]) -> float | None:
    context = candidate.get("context")
    context = context if isinstance(context, Mapping) else {}
    value = candidate.get("score", context.get("score"))
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _severity(candidate: Mapping[str, Any]) -> str:
    context = candidate.get("context")
    context = context if isinstance(context, Mapping) else {}
    return str(candidate.get("severity") or context.get("severity") or "unknown").lower()


def _safe_context(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return {}
    result = {}
    for key, item in value.items():
        name = str(key)
        if name.lower() in SENSITIVE_CONTEXT_KEYS:
            continue
        if isinstance(item, Mapping):
            result[name] = _safe_context(item)
        elif isinstance(item, list):
            result[name] = [
                _safe_context(entry) if isinstance(entry, Mapping) else entry
                for entry in item
                if isinstance(entry, (str, int, float, bool, Mapping)) or entry is None
            ]
        elif isinstance(item, (str, int, float, bool)) or item is None:
            result[name] = item
    return result


def _high_score_threshold(candidates: list[Mapping[str, Any]]) -> float | None:
    scores = sorted(score for item in candidates if (score := _score(item)) is not None)
    if not scores:
        return None
    return scores[(3 * len(scores)) // 4] if len(scores) > 1 else scores[0]


def _candidate_identity(candidate: Mapping[str, Any], index: int) -> str:
    occurrence_id = str(candidate.get("occurrence_id") or "")
    semantic_id = str(candidate.get("semantic_id") or "")
    return f"{occurrence_id}|{semantic_id}|{index}"


def _random_key(identity: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}|{identity}".encode()).hexdigest()


def _allocate(
    capacities: Mapping[tuple[str, str, str, str], int], total: int
) -> dict[tuple[str, str, str, str], int]:
    quotas = {key: 0 for key in capacities}
    remaining = min(total, sum(capacities.values()))
    while remaining:
        active = [key for key in capacities if quotas[key] < capacities[key]]
        if not active:
            break
        capacity_sum = sum(capacities[key] for key in active)
        assigned = sum(quotas[key] for key in active)
        target_total = assigned + remaining
        chosen = max(
            active,
            key=lambda key: (
                target_total * capacities[key] / capacity_sum - quotas[key],
                capacities[key] - quotas[key],
                tuple(reversed(key)),
            ),
        )
        quotas[chosen] += 1
        remaining -= 1
    return quotas


def _task(
    candidate: Mapping[str, Any],
    propensity: float,
    reason: str,
    stratum: tuple[str, str, str, str],
    stratum_size: int,
    stratum_quota: int,
) -> dict[str, Any]:
    score = _score(candidate)
    return {
        "occurrence_id": candidate.get("occurrence_id"),
        "semantic_id": candidate.get("semantic_id"),
        "project": candidate.get("project"),
        "run_id": candidate.get("run_id"),
        "commit": candidate.get("commit"),
        "action": candidate.get("action"),
        "context": _safe_context(candidate.get("context")),
        "score": score,
        "label_propensity": propensity,
        "sampling_reason": reason,
        "stratum": {
            "project": stratum[0],
            "severity": stratum[1],
            "score": stratum[2],
            "action": stratum[3],
            "size": stratum_size,
            "quota": stratum_quota,
        },
    }


def stratified_sample(
    candidates: Iterable[Mapping[str, Any]],
    sample_size: int,
    seed: int = 0,
    high_score_fraction: float = DEFAULT_HIGH_SCORE_FRACTION,
    high_score_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """Sample equal-probability subsets within project/severity/score/action strata."""
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    if not 0.0 <= high_score_fraction <= 1.0:
        raise ValueError("high_score_fraction must be between 0 and 1")
    items = list(candidates)
    if sample_size == 0 or not items:
        return []
    sample_size = min(sample_size, len(items))
    threshold = (
        _high_score_threshold(items) if high_score_threshold is None else high_score_threshold
    )

    indexed_strata: dict[
        tuple[str, str, str, str], list[tuple[int, Mapping[str, Any]]]
    ] = defaultdict(list)
    for index, candidate in enumerate(items):
        score = _score(candidate)
        score_bucket = "missing"
        if score is not None and threshold is not None:
            score_bucket = "high" if score >= threshold else "low"
        action = str(candidate.get("action") or "unknown")
        stratum = (
            str(candidate.get("project") or "unknown"),
            _severity(candidate),
            score_bucket,
            action,
        )
        indexed_strata[stratum].append((index, candidate))

    high_keys = sorted(key for key in indexed_strata if key[2] == "high")
    exploration_keys = sorted(key for key in indexed_strata if key[2] != "high")
    high_capacity = sum(len(indexed_strata[key]) for key in high_keys)
    exploration_capacity = sum(len(indexed_strata[key]) for key in exploration_keys)
    high_total = min(high_capacity, int(sample_size * high_score_fraction + 0.5))
    if exploration_capacity and sample_size > 1:
        high_total = min(high_total, sample_size - 1)
    exploration_total = min(exploration_capacity, sample_size - high_total)
    high_total = min(high_capacity, sample_size - exploration_total)
    exploration_total = sample_size - high_total

    quotas = _allocate({key: len(indexed_strata[key]) for key in high_keys}, high_total)
    quotas.update(
        _allocate(
            {key: len(indexed_strata[key]) for key in exploration_keys}, exploration_total
        )
    )

    selected = []
    for stratum in sorted(indexed_strata):
        quota = quotas.get(stratum, 0)
        if not quota:
            continue
        members = sorted(
            indexed_strata[stratum],
            key=lambda pair: _random_key(_candidate_identity(pair[1], pair[0]), seed),
        )
        size = len(members)
        propensity = quota / size
        reason = "high-score-coverage" if stratum[2] == "high" else "random-low-score-exploration"
        for _index, candidate in members[:quota]:
            selected.append(_task(candidate, propensity, reason, stratum, size, quota))
    return selected


def trusted_label_plan(
    candidates: Iterable[Mapping[str, Any]],
    sample_size: int,
    seed: int = 0,
) -> dict[str, Any]:
    """Prioritize missing trusted projects and actions before top-up sampling."""
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    items = list(candidates)
    trusted_evidence = {"runtime", "judge", "human", "manual"}
    trusted = [
        item
        for item in items
        if str(item.get("outcome", {}).get("verdict", "unknown")) != "unknown"
        and str(item.get("outcome", {}).get("evidence_class", "unknown")) in trusted_evidence
    ]
    trusted_projects = {str(item.get("project", "unknown")) for item in trusted}
    trusted_actions = {str(item.get("action", "unknown")) for item in trusted}
    projects = sorted({str(item.get("project", "unknown")) for item in items})
    actions = sorted({str(item.get("action", "unknown")) for item in items if item.get("action")})
    project_gaps = [project for project in projects if project not in trusted_projects]
    action_gaps = [action for action in actions if action not in trusted_actions]

    indexed: dict[tuple[str, str], list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for index, candidate in enumerate(items):
        action = str(candidate.get("action") or "")
        outcome = candidate.get("outcome")
        outcome = outcome if isinstance(outcome, Mapping) else {}
        if not action or str(outcome.get("verdict", "unknown")) != "unknown":
            continue
        indexed[(str(candidate.get("project") or "unknown"), action)].append((index, candidate))
    if sample_size == 0 or not indexed:
        return {
            "status": "insufficient",
            "analysis": {
                "trusted_support": len(trusted),
                "project_gaps": project_gaps,
                "action_gaps": action_gaps,
                "selected_projects": [],
                "selected_actions": [],
            },
            "tasks": [],
        }

    capacities = {key: len(members) for key, members in indexed.items()}
    quotas = _allocate(capacities, min(sample_size, sum(capacities.values())))
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    tasks = []
    for stratum in sorted(indexed):
        quota = quotas.get(stratum, 0)
        if not quota:
            continue
        members = sorted(
            indexed[stratum],
            key=lambda pair: (
                severity_rank.get(_severity(pair[1]), 5),
                _random_key(_candidate_identity(pair[1], pair[0]), seed),
            ),
        )
        size = len(members)
        for _index, candidate in members[:quota]:
            project, action = stratum
            if project in project_gaps:
                reason = "trusted-project-gap"
            elif action in action_gaps:
                reason = "trusted-action-gap"
            else:
                reason = "trusted-coverage-top-up"
            tasks.append(_task(candidate, quota / size, reason, (*stratum, "", ""), size, quota))
    return {
        "status": "ok" if tasks else "insufficient",
        "analysis": {
            "trusted_support": len(trusted),
            "project_gaps": project_gaps,
            "action_gaps": action_gaps,
            "selected_projects": sorted({str(task["project"]) for task in tasks}),
            "selected_actions": sorted({str(task["action"]) for task in tasks}),
        },
        "tasks": tasks,
    }


def inverse_label_propensity(
    value: float | Mapping[str, Any], max_weight: float = DEFAULT_MAX_WEIGHT
) -> float:
    """Return a capped Horvitz-Thompson weight for a selected candidate."""
    propensity = value.get("label_propensity") if isinstance(value, Mapping) else value
    if isinstance(propensity, bool) or not isinstance(propensity, (int, float)):
        raise ValueError("label_propensity must be numeric")
    if not 0.0 < propensity <= 1.0:
        raise ValueError("label_propensity must be in (0, 1]")
    if not isinstance(max_weight, (int, float)) or max_weight < 1.0:
        raise ValueError("max_weight must be at least 1")
    return min(1.0 / propensity, float(max_weight))


def inverse_propensity_weights(
    records: Iterable[Mapping[str, Any]], max_weight: float = DEFAULT_MAX_WEIGHT
) -> list[float]:
    return [inverse_label_propensity(record, max_weight=max_weight) for record in records]
