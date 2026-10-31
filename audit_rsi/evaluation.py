from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from .objective import PolicyScore
from .world import ReplayWorld, TracePool


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _project(item: Any) -> str:
    return str(_field(item, "project", "") or "unknown")


def _time(item: Any, time_key: str) -> Any:
    value = _field(item, time_key)
    if value is None:
        for key in ("timestamp", "created_at", "started_at", "run_id"):
            value = _field(item, key)
            if value is not None:
                break
    if value is None and isinstance(item, ReplayWorld):
        for key in (time_key, "timestamp", "created_at", "started_at", "run_id"):
            value = item.meta.get(key)
            if value is not None:
                break
    return value if value is not None else ""


def _project_type(item: Any) -> str:
    value = _field(item, "project_type")
    if value is None and isinstance(item, ReplayWorld):
        value = item.meta.get("project_type")
    return str(value or "unknown")


def _semantic_ids(item: Any) -> set[str]:
    value = _field(item, "semantic_ids")
    if value is not None:
        return {str(entry) for entry in value if str(entry)}
    value = _field(item, "semantic_id")
    if value:
        return {str(value)}
    if isinstance(item, ReplayWorld):
        return {
            node.outcome.semantic_id
            for node in item.tree.nodes.values()
            if node.outcome.semantic_id
        }
    return set()


def _time_sort_key(value: Any) -> tuple[str, str]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("0", f"{float(value):030.6f}")
    return ("1", str(value))


def semantic_leakage(splits: Mapping[str, Iterable[Any]]) -> list[str]:
    seen: dict[str, str] = {}
    errors: list[str] = []
    for split in ("train", "val", "test"):
        for item in splits.get(split, []):
            for semantic_id in _semantic_ids(item):
                previous = seen.get(semantic_id)
                if previous is not None and previous != split:
                    errors.append(f"semantic_id {semantic_id!r} crosses {previous}/{split}")
                else:
                    seen[semantic_id] = split
    return sorted(set(errors))


def assert_semantic_isolation(splits: Mapping[str, Iterable[Any]]) -> None:
    errors = semantic_leakage(splits)
    if errors:
        raise ValueError("semantic leakage: " + "; ".join(errors))


def split_by_project_time(
    data: TracePool | Sequence[Any],
    *,
    val_fraction: float = 0.2,
    test_fraction: float = 0.2,
    time_key: str = "time",
) -> dict[str, Any]:
    if not 0 <= val_fraction < 1 or not 0 <= test_fraction < 1:
        raise ValueError("split fractions must be in [0, 1)")
    if val_fraction + test_fraction >= 1:
        raise ValueError("val_fraction + test_fraction must be less than 1")
    items = list(data.worlds if isinstance(data, TracePool) else data)
    groups: dict[str, list[Any]] = defaultdict(list)
    for item in items:
        groups[_project(item)].append(item)
    if len(groups) < 2:
        raise ValueError("insufficient projects: at least two are required")

    semantic_projects: dict[str, set[str]] = defaultdict(set)
    for item in items:
        for semantic_id in _semantic_ids(item):
            semantic_projects[semantic_id].add(_project(item))
    conflicts = sorted(
        semantic_id for semantic_id, projects in semantic_projects.items() if len(projects) > 1
    )
    if conflicts:
        raise ValueError("semantic leakage across projects: " + ", ".join(conflicts))

    ordered_projects = sorted(
        groups,
        key=lambda project: (
            min(
                (_time_sort_key(_time(item, time_key)) for item in groups[project]),
                default=("1", ""),
            ),
            project,
        ),
    )
    count = len(ordered_projects)
    test_count = max(1, int(count * test_fraction)) if test_fraction else 0
    val_count = max(1, int(count * val_fraction)) if val_fraction else 0
    while test_count + val_count > count - 1:
        if val_count:
            val_count -= 1
        else:
            test_count -= 1
    train_count = count - val_count - test_count
    assignments = {
        "train": ordered_projects[:train_count],
        "val": ordered_projects[train_count : train_count + val_count],
        "test": ordered_projects[train_count + val_count :],
    }
    result: dict[str, Any] = {}
    for split, projects in assignments.items():
        selected = [
            item
            for project in projects
            for item in sorted(
                groups[project],
                key=lambda entry: (
                    _time_sort_key(_time(entry, time_key)),
                    str(_field(entry, "world_id", "")),
                ),
            )
        ]
        result[split] = (
            TracePool(selected, dict(data.meta)) if isinstance(data, TracePool) else selected
        )
    assert_semantic_isolation(result)
    result["projects"] = assignments
    return result


def split_manifest(splits: Mapping[str, Any], *, name: str = "offline") -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema": "mygoldmine-rsi-dataset/v1",
        "name": name,
        "holdout_key": "project",
        "splits": {},
        "counts": {},
    }
    for split in ("train", "val", "test"):
        value = splits.get(split, [])
        items = list(value.worlds if isinstance(value, TracePool) else value)
        rows = []
        for index, item in enumerate(items):
            item_id = _field(item, "world_id") or _field(item, "id") or index
            rows.append(
                {
                    "id": str(item_id),
                    "project": _project(item),
                    "time": str(_time(item, "time")),
                    "semantic_ids": sorted(_semantic_ids(item)),
                }
            )
        manifest["splits"][split] = rows
        manifest["counts"][split] = len(rows)
    return manifest


def _metric_value(item: Any, metric: str) -> float | None:
    value = _field(item, metric)
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _records(data: Any, metric: str) -> list[dict[str, Any]]:
    if isinstance(data, PolicyScore):
        source: Iterable[Any] = data.per_world
    elif isinstance(data, Mapping) and "per_world" in data:
        source = data["per_world"]
    elif isinstance(data, Mapping):
        records = []
        for project, values in data.items():
            if isinstance(values, (int, float)) and not isinstance(values, bool):
                values = [values]
            for value in values:
                records.append(
                    {
                        "project": str(project),
                        "project_type": "unknown",
                        "value": _metric_value({metric: value}, metric),
                        "label_coverage": None,
                    }
                )
        return [record for record in records if record["value"] is not None]
    else:
        source = data
    records = []
    for item in source:
        value = _metric_value(item, metric)
        if value is None:
            continue
        records.append(
            {
                "project": _project(item),
                "project_type": _project_type(item),
                "value": value,
                "label_coverage": _metric_value(item, "label_coverage"),
                "raw": item,
            }
        )
    return records


def _project_means(records: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for record in records:
        grouped[str(record["project"])].append(float(record["value"]))
    return {project: sum(values) / len(values) for project, values in grouped.items() if values}


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def project_bootstrap(
    data: Any,
    *,
    metric: str = "value",
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    means = _project_means(_records(data, metric))
    projects = sorted(means)
    if not projects:
        return {
            "status": "insufficient",
            "mean": None,
            "ci": None,
            "ci_low": None,
            "ci_high": None,
            "n_projects": 0,
            "seed": seed,
        }
    rng = random.Random(seed)
    values = [means[project] for project in projects]
    estimates = []
    for _ in range(n_bootstrap):
        sample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(sum(sample) / len(sample))
    alpha = (1 - confidence) / 2
    low = _quantile(estimates, alpha)
    high = _quantile(estimates, 1 - alpha)
    return {
        "status": "ok",
        "mean": sum(values) / len(values),
        "ci": [low, high],
        "ci_low": low,
        "ci_high": high,
        "n_projects": len(projects),
        "per_project": means,
        "n_bootstrap": n_bootstrap,
        "confidence": confidence,
        "seed": seed,
    }


def bootstrap_project_ci(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return project_bootstrap(*args, **kwargs)


def _pool_metadata(pool: TracePool | None) -> dict[str, ReplayWorld]:
    return {world.project: world for world in pool.worlds} if pool else {}


def compare(
    candidate: Any,
    incumbent: Any,
    *,
    metric: str = "score",
    pool: TracePool | None = None,
    min_label_coverage: float = 0.8,
    min_projects: int = 2,
    min_support: int = 1,
    regression_tolerance: float = 1e-9,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    candidate_records = _records(candidate, metric)
    incumbent_records = _records(incumbent, metric)
    metadata = _pool_metadata(pool)
    if pool:
        for records in (candidate_records, incumbent_records):
            for record in records:
                world = metadata.get(record["project"])
                if world is not None:
                    record["project_type"] = _project_type(world)
    candidate_means = _project_means(candidate_records)
    incumbent_means = _project_means(incumbent_records)
    common = sorted(set(candidate_means) & set(incumbent_means))
    differences = {
        project: candidate_means[project] - incumbent_means[project] for project in common
    }
    difference = project_bootstrap(
        differences,
        n_bootstrap=n_bootstrap,
        confidence=confidence,
        seed=seed,
    )
    candidate_summary = project_bootstrap(
        candidate,
        metric=metric,
        n_bootstrap=n_bootstrap,
        confidence=confidence,
        seed=seed,
    )
    incumbent_summary = project_bootstrap(
        incumbent,
        metric=metric,
        n_bootstrap=n_bootstrap,
        confidence=confidence,
        seed=seed,
    )

    slices: dict[str, list[float]] = defaultdict(list)
    types = {
        record["project"]: record["project_type"]
        for record in candidate_records + incumbent_records
    }
    for project, value in differences.items():
        slices[types.get(project, "unknown")].append(value)
    slice_rows = [
        {
            "project_type": project_type,
            "difference": sum(values) / len(values),
            "n_projects": len(values),
        }
        for project_type, values in slices.items()
    ]
    slice_rows.sort(key=lambda row: (row["difference"], row["project_type"]))
    worst = slice_rows[0] if slice_rows else None

    coverages = [
        record["label_coverage"]
        for record in candidate_records + incumbent_records
        if record["label_coverage"] is not None
    ]
    coverage_count = sum(
        record["label_coverage"] is not None for record in candidate_records + incumbent_records
    )
    expected_coverage_count = len(candidate_records) + len(incumbent_records)
    label_coverage = sum(coverages) / expected_coverage_count if expected_coverage_count else 0.0
    reasons: list[str] = []
    if not common:
        reasons.append("no_paired_projects")
    if set(candidate_means) != set(incumbent_means):
        reasons.append("project_mismatch")
    if len(common) < min_projects:
        reasons.append("insufficient_project_support")
    if min(len(candidate_records), len(incumbent_records)) < min_support:
        reasons.append("insufficient_world_support")
    if coverage_count < expected_coverage_count or label_coverage < min_label_coverage:
        reasons.append("insufficient_label_coverage")
    overall_delta = difference["mean"]
    overall_regression = overall_delta is not None and overall_delta < -regression_tolerance
    worst_regression = bool(worst and worst["difference"] < -regression_tolerance)
    if overall_regression:
        reasons.append("overall_regression")
    if worst_regression:
        reasons.append("worst_project_type_regression")
    insufficient = {
        "no_paired_projects",
        "project_mismatch",
        "insufficient_project_support",
        "insufficient_world_support",
        "insufficient_label_coverage",
    }
    status = (
        "insufficient"
        if any(reason in insufficient for reason in reasons)
        else "rejected"
        if reasons
        else "accepted"
    )
    return {
        "status": status,
        "accepted": status == "accepted",
        "metric": metric,
        "candidate": candidate_summary,
        "incumbent": incumbent_summary,
        "difference": difference,
        "delta": overall_delta,
        "ci": difference["ci"],
        "label_coverage": label_coverage,
        "support": {
            "projects": len(common),
            "candidate_worlds": len(candidate_records),
            "incumbent_worlds": len(incumbent_records),
        },
        "per_project_difference": differences,
        "project_type_slices": slice_rows,
        "worst_project_type": worst,
        "no_regression": not overall_regression and not worst_regression,
        "reasons": list(dict.fromkeys(reasons)),
        "gate": {
            "min_label_coverage": min_label_coverage,
            "min_projects": min_projects,
            "min_support": min_support,
            "regression_tolerance": regression_tolerance,
        },
    }


def compare_policies(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return compare(*args, **kwargs)


def statistical_gate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return compare(*args, **kwargs)


def evaluate_verification(
    records: Any,
    *,
    metric: str = "value",
    min_label_coverage: float = 0.8,
    min_projects: int = 1,
    min_support: int = 1,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    rows = _records(records, metric)
    summary = project_bootstrap(
        rows,
        n_bootstrap=n_bootstrap,
        confidence=confidence,
        seed=seed,
    )
    coverages = [row["label_coverage"] for row in rows]
    present = [value for value in coverages if value is not None]
    coverage = sum(present) / len(rows) if rows else 0.0
    reasons = []
    if len(summary.get("per_project", {})) < min_projects:
        reasons.append("insufficient_project_support")
    if len(rows) < min_support:
        reasons.append("insufficient_world_support")
    if len(present) < len(rows) or coverage < min_label_coverage:
        reasons.append("insufficient_label_coverage")
    return {
        **summary,
        "status": "insufficient" if reasons else "accepted",
        "accepted": not reasons,
        "metric": metric,
        "label_coverage": coverage,
        "support": len(rows),
        "reasons": reasons,
    }


def rolling_forward(
    records: Sequence[Any],
    *,
    evaluator: Callable[[list[Any], list[Any]], Any] | None = None,
    metric: str = "value",
    min_train: int = 1,
    horizon: int = 1,
    time_key: str = "time",
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    if min_train < 1 or horizon < 1:
        raise ValueError("min_train and horizon must be positive")
    groups: dict[str, list[Any]] = defaultdict(list)
    for record in records:
        groups[_project(record)].append(record)
    folds = []
    values = []
    for project in sorted(groups):
        ordered = sorted(
            groups[project],
            key=lambda item: _time_sort_key(_time(item, time_key)),
        )
        for start in range(min_train, len(ordered) - horizon + 1, horizon):
            train = ordered[:start]
            test = ordered[start : start + horizon]
            outcome = evaluator(train, test) if evaluator else None
            if outcome is None:
                outcome_values = [_metric_value(item, metric) for item in test]
                present = [value for value in outcome_values if value is not None]
                value = sum(present) / len(present) if present else None
            elif isinstance(outcome, Mapping):
                value = _metric_value(outcome, metric)
            else:
                value = _metric_value({"value": outcome}, "value")
            fold = {
                "project": project,
                "train_size": len(train),
                "test_size": len(test),
                "train_end": str(_time(train[-1], time_key)),
                "test_start": str(_time(test[0], time_key)),
                "value": value,
            }
            folds.append(fold)
            if value is not None:
                values.append(fold)
    summary = project_bootstrap(
        values,
        n_bootstrap=n_bootstrap,
        confidence=confidence,
        seed=seed,
    )
    return {
        **summary,
        "status": "ok" if values else "insufficient",
        "folds": folds,
        "n_folds": len(folds),
        "metric": metric,
    }


def rolling_forward_evaluate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return rolling_forward(*args, **kwargs)
