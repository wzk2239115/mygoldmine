"""Build leak-free, provenance-preserving experiences from audit artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .adapters.runs import load_labels

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
ACTION_MAP = {
    "reproduce": "verify",
    "triage": "deep_read",
    "review": "human_review",
    "duplicate": "duplicate_candidate",
    "archived": "defer",
    "inbox": "defer",
}
OUTCOME_VERDICTS = frozenset(
    {
        "unknown",
        "static-supported",
        "runtime-confirmed",
        "judge-approved",
        "human-confirmed",
        "fp",
        "duplicate",
        "design",
    }
)
POSITIVE_VERDICTS = frozenset(
    {"static-supported", "runtime-confirmed", "judge-approved", "human-confirmed"}
)


def _load_json(path: str | Path | None, default: Any) -> Any:
    if path is None:
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _load_jsonl(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _string(value: Any) -> str:
    return "" if value is None else str(value)


def _finding_id(item: Mapping[str, Any]) -> str:
    return _string(item.get("finding_id") or item.get("local_id") or item.get("id"))


def _occurrence_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _string(item.get("project")),
        _string(item.get("run_id") or item.get("runId") or item.get("run")),
        _finding_id(item),
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 and result < float("inf") else None


def _cost(trajectory: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    names = ("agent_calls", "seconds", "tokens", "review_seconds")
    raw = trajectory.get("cost") if trajectory else None
    raw = raw if isinstance(raw, Mapping) else {}
    cost: dict[str, Any] = {}
    observed = []
    for name in names:
        value = raw.get(name)
        if value is None and trajectory:
            value = trajectory.get(name)
        number = _number(value)
        if number is None:
            cost[name] = 0 if name != "seconds" and name != "review_seconds" else 0.0
        else:
            cost[name] = number if name == "seconds" or name == "review_seconds" else int(number)
            observed.append(name)
    return cost, observed


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _historical_cost(value: Any) -> dict[str, int | float]:
    raw = _mapping(value)
    result: dict[str, int | float] = {}
    for name in ("agent_calls", "seconds", "tokens", "review_seconds"):
        number = _number(raw.get(name))
        if number is not None:
            result[name] = number if name.endswith("seconds") else int(number)
    return result


def _context(
    occurrence: Mapping[str, Any], trajectory: Mapping[str, Any] | None
) -> dict[str, Any]:
    raw = _mapping(occurrence.get("raw"))
    features = _mapping(trajectory.get("features") if trajectory else None)
    pre_context = _mapping(trajectory.get("context") if trajectory else None)
    evidence = raw.get("evidence")
    evidence_count = len(evidence) if isinstance(evidence, list) else 0
    cve_tier = features.get("cve_tier", pre_context.get("cve_tier"))
    context = {
        "finding_id": _finding_id(occurrence),
        "severity": _string(
            features.get("severity") or occurrence.get("severity") or "unknown"
        ).lower(),
        "confidence": _string(
            features.get("confidence") or occurrence.get("confidence") or "unknown"
        ).lower(),
        "category": _string(raw.get("category") or "unknown"),
        "evidence_count": int(_number(features.get("evidence_count")) or evidence_count),
        "cve_tier": cve_tier,
    }
    score = _number(trajectory.get("score")) if trajectory else None
    if score is not None:
        context["score"] = score

    history: dict[str, Any] = {}
    for source in (
        _mapping(trajectory.get("history") if trajectory else None),
        _mapping(features.get("history")),
        _mapping(pre_context.get("history")),
    ):
        history.update(source)
    verification = _mapping(features.get("verification"))
    verification = {**verification, **_mapping(pre_context.get("verification"))}
    if "verified" not in history:
        if "verified" in features:
            history["verified"] = features["verified"]
        elif "verified" in verification:
            history["verified"] = verification["verified"]
    if "cost" not in history and "cost" in verification:
        history["cost"] = verification["cost"]
    if not verification and features.get("verify_verdict"):
        verification = {"verdict": features["verify_verdict"]}
    safe_verification = {
        key: verification[key]
        for key in ("verdict", "method", "evidence_class", "status", "confidence")
        if key in verification
    }
    safe_history: dict[str, Any] = {}
    if "verified" in history:
        safe_history["verified"] = history["verified"]
    historical_cost = _historical_cost(history.get("cost"))
    if historical_cost:
        safe_history["cost"] = historical_cost
    if safe_verification:
        safe_history["verification"] = safe_verification
    context["history"] = safe_history
    return context


def _load_verify(run_dir: Path) -> dict[str, dict[str, Any]]:
    summary = _load_json(run_dir / "verify" / "auto" / "summary.json", {})
    result: dict[str, dict[str, Any]] = {}
    if isinstance(summary, Mapping):
        for item in summary.get("findings", []):
            if isinstance(item, dict) and item.get("finding_id"):
                result[_string(item["finding_id"])] = item
    if run_dir.is_dir():
        for path in sorted(run_dir.glob("**/verify/**/verdict.json")):
            item = _load_json(path, {})
            if not isinstance(item, dict):
                continue
            finding_id = item.get("finding_id")
            if not finding_id:
                finding = _load_json(path.parent / "finding.json", {})
                if isinstance(finding, Mapping):
                    finding_id = finding.get("id")
            if finding_id:
                result[_string(finding_id)] = item
    return result


def _verify_outcome(item: Mapping[str, Any] | None) -> dict[str, str]:
    item = item or {}
    raw = _string(item.get("verdict")).lower()
    evidence_text = " ".join(
        (_string(item.get("evidence_class")).lower(), _string(item.get("method")).lower())
    )
    runtime = any(
        marker in evidence_text for marker in ("runtime", "dynamic", "exploit", "redteam")
    )
    evidence_class = "runtime" if runtime else "static"
    supported = "runtime-confirmed" if runtime else "static-supported"
    verdict = {
        "confirmed": supported,
        "tp": supported,
        "rejected": "fp",
        "fp": "fp",
    }.get(raw, "unknown")
    return {
        "verdict": verdict,
        "evidence_class": evidence_class if item else "none",
        "label_scope": "occurrence",
        "origin": "verify" if item else "",
    }


def _human_outcome(item: Mapping[str, Any] | None) -> dict[str, str]:
    raw = _string((item or {}).get("verdict")).lower()
    verdict = {
        "tp": "human-confirmed",
        "confirmed": "human-confirmed",
        "human-confirmed": "human-confirmed",
        "fp": "fp",
        "rejected": "fp",
        "duplicate": "duplicate",
        "design": "design",
    }.get(raw, "unknown")
    return {
        "verdict": verdict,
        "evidence_class": "human" if item else "none",
        "label_scope": "semantic",
        "origin": "curated" if item else "",
    }


def _validation_outcome(item: Mapping[str, Any] | None) -> dict[str, str]:
    if not item:
        return {
            "verdict": "unknown",
            "evidence_class": "none",
            "label_scope": "semantic",
            "origin": "",
        }
    judge = item.get("judge")
    judge = judge if isinstance(judge, Mapping) else {}
    judge_verdict = _string(judge.get("verdict")).lower()
    status = _string(item.get("status") or judge.get("recommended_status")).lower()
    if judge_verdict in {"approved", "tp", "confirmed"}:
        verdict = "judge-approved"
    elif judge_verdict in {"rejected", "fp"}:
        verdict = "fp"
    elif status in {"runtime-validated", "runtime-confirmed", "confirmed"}:
        verdict = "runtime-confirmed"
    else:
        verdict = "unknown"
    evidence_class = "judge" if judge_verdict else "runtime"
    return {
        "verdict": verdict,
        "evidence_class": evidence_class,
        "label_scope": "semantic",
        "origin": "validation",
    }


def _empty_outcome() -> dict[str, Any]:
    return {
        "verdict": "unknown",
        "evidence_class": "none",
        "label_scope": None,
        "origin": None,
        "reward_eligible": False,
    }


def _better_outcome(current: dict[str, Any], candidate: dict[str, str]) -> dict[str, Any]:
    if not candidate.get("origin"):
        return current
    rank = {"none": 0, "static": 1, "runtime": 2, "judge": 3, "human": 4}
    current_known = current["verdict"] != "unknown"
    candidate_known = candidate["verdict"] != "unknown"
    if current_known and not candidate_known:
        return current
    if candidate_known and not current_known:
        return {**candidate, "reward_eligible": False}
    if rank[candidate["evidence_class"]] < rank[current["evidence_class"]]:
        return current
    return {**candidate, "reward_eligible": False}


def _entry_in_scope(
    entry: Mapping[str, Any],
    occurrence: Mapping[str, Any],
    key_scoped: bool,
    allow_unscoped: bool = False,
) -> bool:
    run_id = _string(entry.get("run_id") or entry.get("runId") or entry.get("run"))
    commit = _string(entry.get("commit"))
    semantic_id = _string(entry.get("semantic_id"))
    occurrence_id = _string(entry.get("occurrence_id"))
    if run_id and run_id != _string(occurrence.get("run_id")):
        return False
    if commit and commit != _string(occurrence.get("commit")):
        return False
    if semantic_id and semantic_id != _string(occurrence.get("semantic_id")):
        return False
    if occurrence_id and occurrence_id != _string(occurrence.get("occurrence_id")):
        return False
    return bool(
        run_id or commit or semantic_id or occurrence_id or key_scoped or allow_unscoped
    )


def _curated_for(
    occurrence: Mapping[str, Any], curated: Mapping[str, Any], unscoped_ok: bool
) -> dict[str, Any] | None:
    project = _string(occurrence.get("project"))
    run_id = _string(occurrence.get("run_id"))
    commit = _string(occurrence.get("commit"))
    finding_id = _finding_id(occurrence)
    keys = [
        (f"{project}:{run_id}:{finding_id}", True, False),
        (f"{project}@{commit}:{finding_id}", True, False),
        (f"{project}:{finding_id}", unscoped_ok, True),
    ]
    for key, allowed, unscoped in keys:
        if not allowed:
            continue
        entry = curated.get(key)
        if isinstance(entry, dict) and _entry_in_scope(
            entry, occurrence, not unscoped, allow_unscoped=unscoped
        ):
            return entry
    semantic_id = _string(occurrence.get("semantic_id"))
    for entry in curated.values():
        if not isinstance(entry, dict) or not _entry_in_scope(entry, occurrence, False):
            continue
        if _string(entry.get("semantic_id")) == semantic_id and semantic_id:
            return entry
    return None


def _validation_indexes(
    rows: Iterable[Mapping[str, Any]], occurrences: list[Mapping[str, Any]]
) -> tuple[dict[str, list[Mapping[str, Any]]], dict[str, list[Mapping[str, Any]]]]:
    by_key = {_occurrence_key(item): item for item in occurrences}
    semantic_by_project_finding: dict[tuple[str, str], set[str]] = {}
    for item in occurrences:
        semantic_by_project_finding.setdefault(
            (_string(item.get("project")), _finding_id(item)), set()
        ).add(_string(item.get("semantic_id")))
    by_occurrence: dict[str, list[Mapping[str, Any]]] = {}
    by_semantic: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        occurrence_id = _string(row.get("occurrence_id"))
        semantic_id = _string(row.get("semantic_id"))
        project = _string(row.get("project"))
        run_id = _string(row.get("run_id") or row.get("runId") or row.get("run"))
        explicit_run_id = bool(run_id)
        finding = row.get("finding")
        finding = finding if isinstance(finding, Mapping) else {}
        finding_id = _finding_id(row) or _finding_id(finding)
        if not project and row.get("run_dir"):
            parts = Path(_string(row["run_dir"])).parts
            if "redteam" in parts:
                index = len(parts) - 1 - parts[::-1].index("redteam")
                if index + 2 < len(parts):
                    project = parts[index + 1]
                    run_id = run_id or parts[index + 2]
        if occurrence_id:
            by_occurrence.setdefault(occurrence_id, []).append(row)
            continue
        if semantic_id:
            by_semantic.setdefault(semantic_id, []).append(row)
            continue
        occurrence = by_key.get((project, run_id, finding_id))
        if occurrence is not None:
            occurrence_id = _string(occurrence.get("occurrence_id"))
            by_occurrence.setdefault(occurrence_id, []).append(row)
            continue
        semantic_ids = semantic_by_project_finding.get((project, finding_id), set())
        if not explicit_run_id and len(semantic_ids) == 1:
            by_semantic.setdefault(next(iter(semantic_ids)), []).append(row)
    return by_occurrence, by_semantic


def write_experience(records: Iterable[Mapping[str, Any]], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return output


def build_experience(
    ledger_path: str | Path = REPO_ROOT / "ui" / "data" / "finding-ledger.json",
    refine_path: str | Path | None = REPO_ROOT / "rsi" / "trajectories" / "refine.jsonl",
    validation_path: str | Path | None = REPO_ROOT / "rsi" / "trajectories" / "validation.jsonl",
    curated_path: str | Path | None = REPO_ROOT / "ui" / "data" / "curated.json",
    handoff_path: str | Path | None = REPO_ROOT / "docs" / "cve-handoff.json",
    adjudication_path: str | Path | None = REPO_ROOT / "docs" / "cve-adjudication.json",
    runs_root: str | Path | None = None,
    output_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return one record per ledger occurrence, using its latest matching refine event."""
    ledger = _load_json(ledger_path, {})
    raw_occurrences = ledger.get("occurrences", {}) if isinstance(ledger, Mapping) else {}
    if isinstance(raw_occurrences, Mapping):
        occurrences = [value for value in raw_occurrences.values() if isinstance(value, dict)]
    elif isinstance(raw_occurrences, list):
        occurrences = [value for value in raw_occurrences if isinstance(value, dict)]
    else:
        occurrences = []
    occurrences.sort(key=lambda item: _string(item.get("occurrence_id") or item.get("key")))

    root = Path(runs_root) if runs_root else Path(ledger_path).resolve().parents[2] / "runs"
    refine_rows = _load_jsonl(refine_path)
    latest_refine: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in refine_rows:
        latest_refine[_occurrence_key(row)] = row
    validation_occurrence, validation_semantic = _validation_indexes(
        _load_jsonl(validation_path), occurrences
    )
    curated, _handoff = load_labels(curated_path, handoff_path, adjudication_path)

    project_finding_semantics: dict[tuple[str, str], set[str]] = {}
    semantic_counts: dict[str, int] = {}
    for occurrence in occurrences:
        project_finding_semantics.setdefault(
            (_string(occurrence.get("project")), _finding_id(occurrence)), set()
        ).add(_string(occurrence.get("semantic_id")))
        semantic_id = _string(occurrence.get("semantic_id"))
        semantic_counts[semantic_id] = semantic_counts.get(semantic_id, 0) + 1

    run_cache: dict[Path, tuple[Mapping[str, Any], dict[str, dict[str, Any]]]] = {}
    records: list[dict[str, Any]] = []
    for occurrence in occurrences:
        occurrence_id = _string(occurrence.get("occurrence_id") or occurrence.get("key"))
        semantic_id = _string(occurrence.get("semantic_id"))
        project = _string(occurrence.get("project"))
        run_id = _string(occurrence.get("run_id"))
        finding_id = _finding_id(occurrence)
        trajectory = latest_refine.get((project, run_id, finding_id))
        decision = _string(trajectory.get("decision")).lower() if trajectory else ""
        explicit_action = bool(trajectory and "action" in trajectory)
        if explicit_action:
            requested_action = _string(trajectory.get("action"))
            action = requested_action if requested_action in set(ACTION_MAP.values()) else None
        else:
            action = ACTION_MAP.get(decision)
        if trajectory and "action_propensity" in trajectory:
            propensity = _number(trajectory.get("action_propensity"))
            action_propensity = propensity if propensity is not None and propensity <= 1 else None
        else:
            action_propensity = 1.0 if action and not explicit_action else None
        if trajectory and "policy" in trajectory:
            policy = trajectory["policy"]
        elif action and not explicit_action:
            policy = "deterministic-legacy-refine"
        else:
            policy = None

        report_path = Path(_string(occurrence.get("report")))
        if not report_path.is_absolute():
            report_path = root.parent / report_path
        run_dir = report_path.parent if occurrence.get("report") else root / project / run_id
        if run_dir not in run_cache:
            report = _load_json(run_dir / "audit-report.json", {})
            run_cache[run_dir] = (report, _load_verify(run_dir))
        report, verify = run_cache[run_dir]
        target = report.get("target", {}) if isinstance(report, Mapping) else {}
        target = target if isinstance(target, Mapping) else {}
        project_type = target.get("project_type") or occurrence.get("project_type")

        outcome = _empty_outcome()
        outcome = _better_outcome(outcome, _verify_outcome(verify.get(finding_id)))
        for validation in validation_occurrence.get(occurrence_id, []):
            outcome = _better_outcome(outcome, _validation_outcome(validation))
        for validation in validation_semantic.get(semantic_id, []):
            outcome = _better_outcome(outcome, _validation_outcome(validation))
        unscoped_ok = len(project_finding_semantics[(project, finding_id)]) == 1
        curated_entry = _curated_for(occurrence, curated, unscoped_ok)
        outcome = _better_outcome(outcome, _human_outcome(curated_entry))

        cost, observed_cost = _cost(trajectory)
        source = {
            "trajectory": "refine" if trajectory else "ledger",
            "decision": decision or None,
            "outcome_sources": [outcome["origin"]] if outcome.get("origin") else [],
            "label_scope": outcome.get("label_scope"),
            "cost_estimated": len(observed_cost) != 4,
            "cost_observed": observed_cost,
            "semantic_occurrence_count": semantic_counts[semantic_id],
        }
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "occurrence_id": occurrence_id,
                "semantic_id": semantic_id,
                "project": project,
                "project_type": _string(project_type) if project_type is not None else None,
                "run_id": run_id,
                "commit": _string(occurrence.get("commit")),
                "ts": _string(
                    (trajectory or {}).get("ts")
                    or occurrence.get("generated_at")
                    or ledger.get("generated_at")
                ),
                "action": action,
                "context": _context(occurrence, trajectory),
                "action_propensity": action_propensity,
                "label_propensity": None,
                "outcome": outcome,
                "cost": cost,
                "policy": policy,
                "source": source,
            }
        )

    rewarded_semantics: set[str] = set()
    for record in records:
        verdict = record["outcome"]["verdict"]
        semantic_id = record["semantic_id"]
        if verdict != "unknown" and semantic_id not in rewarded_semantics:
            record["outcome"]["reward_eligible"] = True
            rewarded_semantics.add(semantic_id)
    if output_path is not None:
        write_experience(records, output_path)
    return records


def outcome_credit(record: Mapping[str, Any]) -> float:
    """Return one unit of credit for at most one judged occurrence per semantic."""
    outcome = record.get("outcome")
    if not isinstance(outcome, Mapping) or outcome.get("verdict") == "unknown":
        return 0.0
    return 1.0 if outcome.get("reward_eligible") else 0.0
