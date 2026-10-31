"""Short-horizon verification policy, training, replay, and shadow advice."""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ACTIONS = (
    "verify",
    "deep_read",
    "human_review",
    "duplicate_candidate",
    "defer",
)
POLICY_VERSION = "verification-utility-ridge-v2"
TRUSTED_EVIDENCE = frozenset({"runtime", "judge", "manual"})
KNOWN_VERDICTS = frozenset({"tp", "fp", "duplicate", "design"})
PROMOTION_ACTIONS = frozenset({"verify", "deep_read", "human_review"})

_SEVERITIES = ("critical", "high", "medium", "low", "info", "unknown")
_CONFIDENCES = ("high", "medium", "low", "unknown")
_SEVERITY_REWARD = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.45,
    "low": 0.2,
    "info": 0.05,
    "unknown": 0.1,
}
_CONFIDENCE_REWARD = {"high": 1.0, "medium": 0.7, "low": 0.4, "unknown": 0.4}
_EVIDENCE_WEIGHT = {
    "manual": 3.0,
    "judge": 2.5,
    "runtime": 2.0,
    "static": 0.5,
    "unknown": 0.25,
}
_FEATURE_NAMES = (
    "bias",
    *(f"severity_{value}" for value in _SEVERITIES),
    *(f"confidence_{value}" for value in _CONFIDENCES),
    "history_verified",
    "evidence_count",
    "cve_tier_1",
    "cve_tier_2",
    "cve_tier_other",
    *(f"project_type_{index}" for index in range(8)),
    *(f"history_action_{action}" for action in ACTIONS),
    "history_agent_calls",
    "history_seconds",
    "history_tokens",
    "history_review_seconds",
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _log_number(value: Any) -> float:
    return math.log1p(max(0.0, _number(value)))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _record_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record.get("project", "")),
        str(record.get("occurrence_id", "")),
        str(record.get("semantic_id", "")),
        _canonical(record),
    )


def data_hash(records: Iterable[Mapping[str, Any]]) -> str:
    """Hash a data version independently of JSONL row order."""
    rows = sorted(_canonical(dict(record)) for record in records)
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def read_experience(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if not text.strip():
        return []
    if source.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = payload.get("records", payload.get("experiences", []))
        else:
            raise ValueError("experience JSON must be a list or contain records")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("every experience must be an object")
    return [dict(row) for row in records]


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [_canonical(dict(record)) for record in records]
    target.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return target


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _context_value(record: Mapping[str, Any], key: str, default: Any = None) -> Any:
    context = _mapping(record.get("context"))
    if key in context:
        return context[key]
    return record.get(key, default)


def _history(record: Mapping[str, Any]) -> Mapping[str, Any]:
    context = _mapping(record.get("context"))
    combined: dict[str, Any] = {}
    for parent in (record, context):
        history = _mapping(parent.get("history"))
        combined.update(history)
    return combined


def _history_value(
    record: Mapping[str, Any], history: Mapping[str, Any], key: str, default: Any = 0.0
) -> Any:
    if key in history:
        return history[key]
    context = _mapping(record.get("context"))
    historical_key = f"historical_{key}"
    if historical_key in context:
        return context[historical_key]
    if historical_key in record:
        return record[historical_key]
    return default


def _history_actions(record: Mapping[str, Any], history: Mapping[str, Any]) -> Any:
    for parent in (history, _mapping(record.get("context")), record):
        for key in ("actions", "action_counts", "historical_actions"):
            if key in parent:
                return parent[key]
    return {}


def _history_cost(record: Mapping[str, Any], history: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("cost", "costs"):
        value = history.get(key)
        if isinstance(value, Mapping):
            return value
    for parent in (_mapping(record.get("context")), record):
        for key in ("historical_cost", "historical_costs"):
            value = parent.get(key)
            if isinstance(value, Mapping):
                return value
    return {}


def extract_features(record: Mapping[str, Any]) -> dict[str, float]:
    """Build features only from information available before the logged action."""
    features = {name: 0.0 for name in _FEATURE_NAMES}
    features["bias"] = 1.0

    severity = str(_context_value(record, "severity", "unknown")).lower()
    if severity not in _SEVERITIES:
        severity = "unknown"
    features[f"severity_{severity}"] = 1.0
    confidence = str(_context_value(record, "confidence", "unknown")).lower()
    if confidence not in _CONFIDENCES:
        confidence = "unknown"
    features[f"confidence_{confidence}"] = 1.0

    history = _history(record)
    features["history_verified"] = _log_number(
        _history_value(record, history, "verified")
    )
    evidence = _context_value(record, "evidence", [])
    evidence_count = _context_value(record, "evidence_count", None)
    if evidence_count is None:
        evidence_count = len(evidence) if isinstance(evidence, Sequence) else 0
    features["evidence_count"] = _log_number(evidence_count)

    tier = _number(_context_value(record, "cve_tier", 0))
    if tier == 1:
        features["cve_tier_1"] = 1.0
    elif tier == 2:
        features["cve_tier_2"] = 1.0
    elif tier > 0:
        features["cve_tier_other"] = 1.0

    project_type = str(_context_value(record, "project_type", "unknown"))
    digest = hashlib.sha256(project_type.encode("utf-8")).digest()
    features[f"project_type_{digest[0] % 8}"] = 1.0

    raw_actions = _history_actions(record, history)
    if isinstance(raw_actions, Mapping):
        action_counts = {action: _number(raw_actions.get(action)) for action in ACTIONS}
    elif isinstance(raw_actions, Sequence) and not isinstance(raw_actions, (str, bytes)):
        action_counts = {action: float(raw_actions.count(action)) for action in ACTIONS}
    else:
        action_counts = {action: 0.0 for action in ACTIONS}
    total_actions = sum(max(0.0, count) for count in action_counts.values())
    for action, count in action_counts.items():
        features[f"history_action_{action}"] = (
            max(0.0, count) / total_actions if total_actions else 0.0
        )

    historical_cost = _history_cost(record, history)
    for cost_name in ("agent_calls", "seconds", "tokens", "review_seconds"):
        features[f"history_{cost_name}"] = _log_number(historical_cost.get(cost_name))
    return features


def _softmax(scores: Sequence[float]) -> list[float]:
    maximum = max(scores)
    exponentials = [math.exp(score - maximum) for score in scores]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def _validate_epsilon(epsilon: float) -> float:
    value = _number(epsilon, float("nan"))
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("epsilon must be between 0 and 1")
    return value


class VerificationPolicy:
    """A fixed-action linear policy with explicit epsilon propensities."""

    actions = ACTIONS

    def __init__(self, model: Mapping[str, Any] | None = None, epsilon: float = 0.0):
        self.model = dict(model or {})
        self.epsilon = _validate_epsilon(epsilon)
        raw_weights = self.model.get("weights", {})
        self.weights: dict[str, list[float]] = {}
        for action in ACTIONS:
            values = list(_mapping(raw_weights).get(action, []))
            if not values:
                values = [0.0] * len(_FEATURE_NAMES)
            if len(values) != len(_FEATURE_NAMES):
                raise ValueError(f"invalid weight count for {action}")
            self.weights[action] = [_number(value) for value in values]

    @property
    def policy_version(self) -> str:
        return str(self.model.get("policy_version", POLICY_VERSION))

    def scores(self, record: Mapping[str, Any]) -> dict[str, float]:
        features = extract_features(record)
        return {
            action: sum(weight * features[name] for name, weight in zip(_FEATURE_NAMES, weights))
            for action, weights in self.weights.items()
        }

    def probabilities(
        self, record: Mapping[str, Any], epsilon: float | None = None
    ) -> dict[str, float]:
        exploration = self.epsilon if epsilon is None else _validate_epsilon(epsilon)
        raw = _softmax([self.scores(record)[action] for action in ACTIONS])
        uniform = 1.0 / len(ACTIONS)
        return {
            action: (1.0 - exploration) * probability + exploration * uniform
            for action, probability in zip(ACTIONS, raw)
        }

    def decide(self, record: Mapping[str, Any]) -> dict[str, Any]:
        scores = self.scores(record)
        probabilities = self.probabilities(record)
        action = max(ACTIONS, key=lambda name: scores[name])
        return {
            "action": action,
            "scores": scores,
            "probabilities": probabilities,
            "propensities": dict(probabilities),
            "epsilon": self.epsilon,
            "policy_version": self.policy_version,
        }

    def sample_action(
        self, record: Mapping[str, Any], seed: int = 0, epsilon: float | None = None
    ) -> str:
        probabilities = self.probabilities(record, epsilon)
        occurrence = str(record.get("occurrence_id", record.get("semantic_id", "")))
        entropy = int.from_bytes(
            hashlib.sha256(f"{seed}:{occurrence}".encode("utf-8")).digest()[:8], "big"
        )
        return random.Random(entropy).choices(ACTIONS, weights=list(probabilities.values()), k=1)[0]

    def reasons(self, record: Mapping[str, Any], action: str, limit: int = 3) -> list[str]:
        features = extract_features(record)
        contributions = [
            (name, self.weights[action][index] * features[name])
            for index, name in enumerate(_FEATURE_NAMES)
            if features[name]
        ]
        contributions.sort(key=lambda item: (-abs(item[1]), item[0]))
        return [f"{name}:{value:+.6f}" for name, value in contributions[:limit]]


def legacy_baseline_action(record: Mapping[str, Any]) -> tuple[str, str]:
    """Explainable legacy duplicate/severity/refine ordering."""
    context = _mapping(record.get("context"))
    duplicate_hint = bool(
        context.get("duplicate_hint", record.get("duplicate_hint", False))
    )
    if duplicate_hint:
        return "duplicate_candidate", "legacy refine duplicate hint"
    severity = str(_context_value(record, "severity", "unknown")).lower()
    if severity in {"critical", "high"}:
        return "verify", f"legacy severity order: {severity} verifies first"
    if severity == "medium":
        return "deep_read", "legacy severity order: medium requires a deep read"
    return "defer", f"legacy severity/refine order defers {severity}"


def _verdict(record: Mapping[str, Any]) -> str:
    raw = str(_mapping(record.get("outcome")).get("verdict", "unknown")).lower()
    aliases = {
        "confirmed": "tp",
        "true_positive": "tp",
        "runtime-confirmed": "tp",
        "judge-approved": "tp",
        "human-confirmed": "tp",
        "static-supported": "tp",
        "rejected": "fp",
        "false_positive": "fp",
        "dup": "duplicate",
    }
    verdict = aliases.get(raw, raw)
    return verdict if verdict in KNOWN_VERDICTS else "unknown"


def _evidence_class(record: Mapping[str, Any]) -> str:
    raw = str(_mapping(record.get("outcome")).get("evidence_class", "unknown")).lower()
    aliases = {"human": "manual", "human_review": "manual", "dynamic": "runtime"}
    evidence = aliases.get(raw, raw)
    return evidence if evidence in _EVIDENCE_WEIGHT else "unknown"


def deduplicate_semantics(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one deterministic, strongest-label row per semantic finding."""
    selected: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = dict(raw)
        semantic = str(record.get("semantic_id") or record.get("occurrence_id") or "")
        if not semantic:
            semantic = f"anonymous:{data_hash([record])}"
        record["semantic_id"] = semantic
        rank = (
            _verdict(record) != "unknown",
            _EVIDENCE_WEIGHT[_evidence_class(record)],
            str(record.get("ts", "")),
            str(record.get("occurrence_id", "")),
            _canonical(record),
        )
        if semantic not in selected:
            selected[semantic] = record
            selected[semantic]["_dedup_rank"] = rank
        elif rank > selected[semantic]["_dedup_rank"]:
            selected[semantic] = record
            selected[semantic]["_dedup_rank"] = rank
    result = []
    for record in selected.values():
        record.pop("_dedup_rank", None)
        result.append(record)
    return sorted(result, key=_record_key)


def _solve_ridge(
    rows: Sequence[Mapping[str, float]],
    actions: Sequence[str],
    targets: Sequence[float],
    weights: Sequence[float],
    ridge: float,
) -> dict[str, list[float]]:
    size = len(_FEATURE_NAMES)
    learned: dict[str, list[float]] = {}
    for selected_action in ACTIONS:
        normal = [[0.0] * size for _ in range(size)]
        target_vector = [0.0] * size
        for row, action, target, sample_weight in zip(
            rows, actions, targets, weights
        ):
            if action != selected_action:
                continue
            if sample_weight < 0:
                raise ValueError("normal-equation weights must be non-negative")
            vector = [row[name] for name in _FEATURE_NAMES]
            for left in range(size):
                if not vector[left]:
                    continue
                target_vector[left] += sample_weight * vector[left] * target
                for right in range(size):
                    normal[left][right] += (
                        sample_weight * vector[left] * vector[right]
                    )
        for index in range(size):
            normal[index][index] += ridge

        augmented = [normal[row] + [target_vector[row]] for row in range(size)]
        for column in range(size):
            pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            divisor = augmented[column][column]
            if abs(divisor) < 1e-12:
                continue
            for index in range(column, size + 1):
                augmented[column][index] /= divisor
            for row in range(size):
                if row == column:
                    continue
                factor = augmented[row][column]
                if not factor:
                    continue
                for index in range(column, size + 1):
                    augmented[row][index] -= factor * augmented[column][index]
        learned[selected_action] = [augmented[row][size] for row in range(size)]
    return learned


def _target_stats(targets: Sequence[float]) -> dict[str, Any]:
    support = len(targets)
    return {
        "support": support,
        "sum": sum(targets) if support else None,
        "mean": sum(targets) / support if support else None,
        "min": min(targets) if support else None,
        "max": max(targets) if support else None,
        "negative": sum(target < 0 for target in targets),
        "zero": sum(target == 0 for target in targets),
        "positive": sum(target > 0 for target in targets),
    }


def train_policy(
    records: Iterable[Mapping[str, Any]],
    *,
    holdout_project: str = "",
    ridge: float = 10.0,
    seed: int = 0,
    min_propensity: float = 0.05,
    max_weight: float = 10.0,
) -> dict[str, Any]:
    """Regress realized utility separately for each logged action."""
    if ridge <= 0 or not math.isfinite(ridge):
        raise ValueError("ridge must be positive")
    if not 0 < min_propensity <= 1 or max_weight < 1:
        raise ValueError("invalid propensity bounds")
    all_records = [dict(record) for record in records]
    training_raw = [
        record
        for record in all_records
        if not holdout_project or str(record.get("project", "")) != holdout_project
    ]
    validation_raw = [
        record
        for record in all_records
        if holdout_project and str(record.get("project", "")) == holdout_project
    ]
    training = deduplicate_semantics(training_raw)
    rows: list[Mapping[str, float]] = []
    actions: list[str] = []
    targets: list[float] = []
    weights: list[float] = []
    evidence_classes: list[str] = []
    skipped_propensity = 0
    skipped_unknown = 0
    skipped_action = 0
    for record in training:
        if _verdict(record) == "unknown":
            skipped_unknown += 1
            continue
        action = str(record.get("action", ""))
        if action not in ACTIONS:
            skipped_action += 1
            continue
        propensity = _number(record.get("label_propensity", 1.0), 0.0)
        if not 0 < propensity <= 1:
            skipped_propensity += 1
            continue
        target = record_utility(record, action)
        if target is None:
            skipped_unknown += 1
            continue
        bounded_weight = min(max_weight, 1.0 / max(min_propensity, propensity))
        evidence_class = _evidence_class(record)
        evidence_weight = _EVIDENCE_WEIGHT[evidence_class]
        rows.append(extract_features(record))
        actions.append(action)
        targets.append(target)
        weights.append(bounded_weight * evidence_weight)
        evidence_classes.append(evidence_class)
    learned = _solve_ridge(rows, actions, targets, weights, ridge) if rows else {
        action: [0.0] * len(_FEATURE_NAMES) for action in ACTIONS
    }
    known = sum(_verdict(record) != "unknown" for record in training)
    trusted_support = sum(value in TRUSTED_EVIDENCE for value in evidence_classes)
    return {
        "policy_version": POLICY_VERSION,
        "algorithm": "per-action-ridge-utility-regression",
        "feature_names": list(_FEATURE_NAMES),
        "actions": list(ACTIONS),
        "weights": learned,
        "ridge": ridge,
        "seed": seed,
        "min_propensity": min_propensity,
        "max_weight": max_weight,
        "holdout_project": holdout_project,
        "training_data_hash": data_hash(training_raw),
        "validation_data_hash": data_hash(validation_raw),
        "pool_data_hash": data_hash(all_records),
        "training": {
            "raw_records": len(training_raw),
            "unique_semantics": len(training),
            "support": len(targets),
            "labeled_actions": len(targets),
            "label_coverage": known / len(training) if training else 0.0,
            "support_by_action": {action: actions.count(action) for action in ACTIONS},
            "evidence_support": {
                value: evidence_classes.count(value) for value in sorted(set(evidence_classes))
            },
            "trusted_support": trusted_support,
            "target": _target_stats(targets),
            "target_by_action": {
                action: _target_stats(
                    [
                        target
                        for logged_action, target in zip(actions, targets)
                        if logged_action == action
                    ]
                )
                for action in ACTIONS
            },
            "skipped_unknown_outcome": skipped_unknown,
            "skipped_invalid_propensity": skipped_propensity,
            "skipped_invalid_action": skipped_action,
            "projects": sorted({str(record.get("project", "")) for record in training}),
            "status": "ok" if targets else "insufficient",
            "reason": None if targets else "no_known_utility_targets",
        },
        "validation": {
            "raw_records": len(validation_raw),
            "projects": sorted({str(record.get("project", "")) for record in validation_raw}),
        },
    }


def save_policy(path: str | Path, model: Mapping[str, Any]) -> Path:
    return write_json(path, model)


def load_policy(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("policy must be a JSON object")
    return payload


def _tp_reward(record: Mapping[str, Any]) -> float:
    if _verdict(record) != "tp" or _evidence_class(record) not in TRUSTED_EVIDENCE:
        return 0.0
    severity = str(_context_value(record, "severity", "unknown")).lower()
    confidence = str(_context_value(record, "confidence", "unknown")).lower()
    tier = _number(_context_value(record, "cve_tier", 0))
    tier_multiplier = 1.25 if tier == 1 else 1.1 if tier == 2 else 1.0
    return (
        _SEVERITY_REWARD.get(severity, 0.1)
        * _CONFIDENCE_REWARD.get(confidence, 0.4)
        * tier_multiplier
    )


def utility_details(
    record: Mapping[str, Any], action: str | None = None
) -> dict[str, float] | None:
    """Return realized utility for known labels; unknown labels never earn rewards."""
    if _verdict(record) == "unknown":
        return None
    selected = str(record.get("action", "")) if action is None else action
    cost = _mapping(record.get("cost"))
    agent_cost = 0.05 * max(0.0, _number(cost.get("agent_calls")))
    token_cost = 0.00001 * max(0.0, _number(cost.get("tokens")))
    review_cost = 0.01 * max(0.0, _number(cost.get("review_seconds")))
    duplicate_cost = 0.0
    if _verdict(record) == "duplicate" or (
        selected == "duplicate_candidate" and _verdict(record) != "duplicate"
    ):
        duplicate_cost = 0.25
    false_promotion_cost = (
        0.5 if _verdict(record) == "fp" and selected in PROMOTION_ACTIONS else 0.0
    )
    reward = _tp_reward(record)
    return {
        "reward": reward,
        "agent_cost": agent_cost,
        "token_cost": token_cost,
        "review_cost": review_cost,
        "duplicate_cost": duplicate_cost,
        "false_promotion_cost": false_promotion_cost,
        "utility": reward
        - agent_cost
        - token_cost
        - review_cost
        - duplicate_cost
        - false_promotion_cost,
    }


def record_utility(record: Mapping[str, Any], action: str | None = None) -> float | None:
    details = utility_details(record, action)
    return None if details is None else details["utility"]


def _replay_policy(
    records: Sequence[Mapping[str, Any]],
    policy_name: str,
    choose_action: Any,
) -> dict[str, Any]:
    per_project: dict[str, dict[str, Any]] = {}
    matched = 0
    support = 0
    support_by_action = {action: 0 for action in ACTIONS}
    utilities: list[float] = []
    for record in records:
        project = str(record.get("project", ""))
        bucket = per_project.setdefault(
            project,
            {"matched_logged_actions": 0, "support": 0, "utility": None},
        )
        selected = choose_action(record)
        if selected != str(record.get("action", "")):
            continue
        matched += 1
        bucket["matched_logged_actions"] += 1
        utility = record_utility(record, selected)
        if utility is None:
            continue
        support += 1
        support_by_action[selected] += 1
        utilities.append(utility)
        bucket["support"] += 1
        bucket["utility"] = (bucket["utility"] or 0.0) + utility
    for bucket in per_project.values():
        if bucket["support"]:
            bucket["utility"] = round(bucket["utility"], 6)
        bucket["status"] = "ok" if bucket["support"] else "insufficient"
    return {
        "policy": policy_name,
        "matched_logged_actions": matched,
        "support": support,
        "support_by_action": support_by_action,
        "utility": round(sum(utilities), 6) if support else None,
        "mean_utility": round(sum(utilities) / support, 6) if support else None,
        "per_project": dict(sorted(per_project.items())),
        "status": "ok" if support else "insufficient",
    }


def replay_policies(
    records: Iterable[Mapping[str, Any]],
    policy: VerificationPolicy,
    *,
    holdout_project: str = "",
) -> dict[str, Any]:
    """Compare only realized, matched-action utility; this is not causal OPE."""
    selected = [dict(record) for record in records]
    if holdout_project:
        selected = [record for record in selected if record.get("project") == holdout_project]
    unique = deduplicate_semantics(selected)
    known = sum(_verdict(record) != "unknown" for record in unique)
    coverage = known / len(unique) if unique else 0.0
    baseline = _replay_policy(
        unique, "legacy-severity-refine", lambda record: legacy_baseline_action(record)[0]
    )
    candidate = _replay_policy(
        unique,
        policy.policy_version,
        lambda record: policy.decide(record)["action"],
    )
    for result in (baseline, candidate):
        result["label_coverage"] = coverage
        result["labeled_semantics"] = known
        result["unique_semantics"] = len(unique)
    return {
        "status": "ok" if baseline["support"] and candidate["support"] else "insufficient",
        "evaluation": "matched-action realized utility; no causal uplift estimated",
        "holdout_project": holdout_project,
        "data_hash": data_hash(selected),
        "label_coverage": coverage,
        "baseline": baseline,
        "candidate": candidate,
    }


def merge_labels(
    records: Iterable[Mapping[str, Any]],
    labels: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Merge reviewed outcomes without changing identity or action propensity."""
    originals = [dict(record) for record in records]
    by_occurrence: dict[str, dict[str, Any]] = {}
    for record in originals:
        occurrence = str(record.get("occurrence_id") or "")
        if not occurrence or occurrence in by_occurrence:
            raise ValueError(f"duplicate or missing experience occurrence_id: {occurrence}")
        by_occurrence[occurrence] = record

    reviewed: dict[str, tuple[str, str, float]] = {}
    for label in labels:
        occurrence = str(label.get("occurrence_id") or "")
        if not occurrence or occurrence not in by_occurrence:
            raise ValueError(f"label identity does not match experience: {occurrence}")
        if occurrence in reviewed:
            raise ValueError(f"duplicate label occurrence_id: {occurrence}")
        original = by_occurrence[occurrence]
        for field in ("semantic_id", "project", "run_id", "commit"):
            expected = str(original.get(field) or "")
            supplied = str(label.get(field) or "")
            if supplied and supplied != expected:
                raise ValueError(
                    f"label {field} mismatch for occurrence_id {occurrence}"
                )
        raw_propensity = label.get("label_propensity")
        if isinstance(raw_propensity, bool):
            raise ValueError(f"invalid label_propensity for {occurrence}")
        propensity = _number(raw_propensity, 0.0)
        if not 0 < propensity <= 1:
            raise ValueError(f"invalid label_propensity for {occurrence}")
        outcome = _mapping(label.get("outcome"))
        verdict = str(outcome.get("verdict") or label.get("verdict") or "")
        evidence_class = str(
            outcome.get("evidence_class") or label.get("evidence_class") or ""
        )
        if not verdict or not evidence_class:
            raise ValueError(f"label verdict/evidence_class required for {occurrence}")
        reviewed[occurrence] = (verdict, evidence_class, propensity)

    merged = []
    for record in originals:
        occurrence = str(record["occurrence_id"])
        if occurrence not in reviewed:
            merged.append(record)
            continue
        verdict, evidence_class, propensity = reviewed[occurrence]
        outcome = dict(_mapping(record.get("outcome")))
        outcome.update({"verdict": verdict, "evidence_class": evidence_class})
        record["outcome"] = outcome
        record["label_propensity"] = propensity
        merged.append(record)
    return merged


def shadow_payload(
    records: Iterable[Mapping[str, Any]],
    policy: VerificationPolicy,
    *,
    epsilon: float = 0.0,
    seed: int = 0,
    holdout_project: str = "",
) -> dict[str, Any]:
    exploration = _validate_epsilon(epsilon)
    selected = [dict(record) for record in records]
    if holdout_project:
        selected = [record for record in selected if record.get("project") == holdout_project]
    training = _mapping(policy.model.get("training"))
    training_status = str(training.get("status", "insufficient"))
    ready = training_status == "ok"
    trusted_support = int(training.get("trusted_support", 0))
    evidence_status = "trusted" if trusted_support else "static-only"
    shadow_status = (
        "ok" if ready and trusted_support else "static-only" if ready else "insufficient"
    )
    reason = (
        None
        if ready and trusted_support
        else "no_trusted_utility_targets"
        if ready
        else str(training.get("reason") or "training utility targets are insufficient")
    )
    advice = []
    for record in sorted(selected, key=_record_key):
        scores = policy.scores(record)
        probabilities = policy.probabilities(record, exploration)
        baseline, baseline_reason = legacy_baseline_action(record)
        candidate = (
            policy.sample_action(record, seed=seed, epsilon=exploration)
            if ready
            else baseline
        )
        reasons = (
            [baseline_reason, *policy.reasons(record, candidate)]
            if ready
            else [baseline_reason, f"shadow fallback: {reason}"]
        )
        advice.append(
            {
                "occurrence_id": str(record.get("occurrence_id", "")),
                "semantic_id": str(record.get("semantic_id", "")),
                "project": str(record.get("project", "")),
                "run_id": str(record.get("run_id", "")),
                "baseline_action": baseline,
                "candidate_action": candidate,
                "scores": scores,
                "propensities": probabilities,
                "epsilon": exploration,
                "status": shadow_status,
                "evidence_status": evidence_status,
                "reason": reason,
                "reasons": reasons,
                "recommendation_only": True,
                "state_change": "none",
            }
        )
    return {
        "policy_version": policy.policy_version,
        "mode": "shadow",
        "status": shadow_status,
        "evidence_status": evidence_status,
        "reason": reason,
        "training_status": training_status,
        "trusted_support": trusted_support,
        "evidence_support": training.get("evidence_support", {}),
        "recommendation_only": True,
        "state_change": "none",
        "epsilon": exploration,
        "seed": seed,
        "holdout_project": holdout_project,
        "training_data_hash": policy.model.get("training_data_hash", data_hash([])),
        "validation_data_hash": policy.model.get("validation_data_hash", data_hash([])),
        "shadow_data_hash": data_hash(selected),
        "recommendations": advice,
    }


def write_shadow(
    path: str | Path,
    records: Iterable[Mapping[str, Any]],
    policy: VerificationPolicy,
    *,
    epsilon: float = 0.0,
    seed: int = 0,
    holdout_project: str = "",
) -> dict[str, Any]:
    payload = shadow_payload(
        records,
        policy,
        epsilon=epsilon,
        seed=seed,
        holdout_project=holdout_project,
    )
    write_json(path, payload)
    return payload
