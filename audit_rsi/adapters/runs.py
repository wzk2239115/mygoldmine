"""Turn existing audit runs into replay worlds without re-running the agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..policy.base import HIGH_YIELD_TAGS
from ..schema import Cost, DiscoveryTree, Node, Outcome, outcome_from_lookup
from ..world import ReplayWorld, TracePool

DEFAULT_STAGES = (
    "workspace_scan",
    "project_profile",
    "route_auth",
    "access_control",
    "ssrf_analysis",
    "general_code_security",
    "model_loading",
    "deserialization",
    "path_traversal",
    "sensitive_info",
    "agent_config",
    "combination_analysis",
    "final_crosscheck",
)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _tags(*parts: Any) -> list[str]:
    text = " ".join(str(p) for p in parts if p).lower()
    tags = sorted({tag for tag in HIGH_YIELD_TAGS if tag in text})
    if "document" in text or "design" in text:
        tags.append("design")
    return tags


def _stage_for(
    category: str, stage_ids: dict[str, str]
) -> str:
    category = category.lower()
    preferred: list[str] = []
    if "ssrf" in category:
        preferred = ["ssrf_analysis"]
    elif any(
        key in category
        for key in ("deserial", "pickle", "model-loading", "model_loading")
    ):
        preferred = ["deserialization", "model_loading"]
    elif any(
        key in category
        for key in ("access-control", "broken-function", "idor")
    ):
        preferred = ["access_control", "route_auth"]
    elif any(key in category for key in ("auth", "csrf", "session")):
        preferred = ["route_auth", "access_control"]
    elif any(key in category for key in ("sensitive", "secret", "credential")):
        preferred = ["sensitive_info"]
    elif any(
        key in category for key in ("path", "lfi", "rfi", "traversal")
    ):
        preferred = ["path_traversal"]
    elif any(key in category for key in ("agent", "mcp", "config")):
        preferred = ["agent_config"]
    else:
        preferred = ["general_code_security"]
    for name in preferred:
        if name in stage_ids:
            return stage_ids[name]
    for name in stage_ids:
        if name in category:
            return stage_ids[name]
    if "general_code_security" in stage_ids:
        return stage_ids["general_code_security"]
    return "root"


def _load_verify(run_dir: Path) -> dict[str, dict[str, Any]]:
    summary = _load_json(run_dir / "verify" / "auto" / "summary.json", {})
    result: dict[str, dict[str, Any]] = {}
    for item in summary.get("findings", []):
        finding_id = item.get("finding_id")
        if finding_id:
            result[str(finding_id)] = item
    for verdict_path in sorted(run_dir.glob("**/verify/**/verdict.json")):
        data = _load_json(verdict_path, {})
        finding_id = data.get("finding_id")
        if not finding_id:
            sibling = verdict_path.parent / "finding.json"
            finding = _load_json(sibling, {})
            finding_id = finding.get("id")
        if finding_id:
            result.setdefault(str(finding_id), data)
    return result


def _verify_outcome(
    item: dict[str, Any], finding: dict[str, Any]
) -> Outcome:
    raw = str(item.get("verdict", "")).lower()
    verdict = {
        "confirmed": "tp",
        "rejected": "fp",
        "inconclusive": "unclear",
    }.get(raw, "unverified")
    return Outcome(
        verdict=verdict,
        severity=str(finding.get("severity", "unknown")).lower(),
        confidence="medium",
        source="verify",
        note=str(item.get("reason", "")),
    )


def manifest_projects(repo_root: str | Path) -> list[str]:
    data = _load_json(Path(repo_root) / "targets" / "manifest.json", {})
    return sorted(
        name
        for name, entry in data.get("projects", {}).items()
        if entry.get("status", "ok") == "ok"
    )


def find_run_dirs(runs_root: str | Path) -> list[Path]:
    root = Path(runs_root)
    found: list[Path] = []
    if not root.exists():
        return found
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        for run_dir in sorted(project_dir.iterdir()):
            if run_dir.is_dir() and (run_dir / "audit-report.json").exists():
                found.append(run_dir)
    return found


def import_run(
    run_dir: str | Path,
    curated: dict[str, Any] | None = None,
    handoff: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> ReplayWorld:
    run_path = Path(run_dir)
    report = _load_json(run_path / "audit-report.json", {})
    meta = _load_json(run_path / "run-meta.json", {})
    curated = curated or {}
    handoff = handoff or {}
    verify = _load_verify(run_path)

    target_raw = report.get("target")
    target = target_raw if isinstance(target_raw, dict) else {}
    project = run_path.parent.name
    if not project or project in {".", ""}:
        project = str(target.get("name") or "project")
    commit = str(target.get("commit") or meta.get("commit") or "")
    duration = float(meta.get("duration_seconds") or 0.0)
    stages = list(
        (report.get("coverage", {}) or {}).get("stages", {}) or DEFAULT_STAGES
    )
    findings = list(report.get("findings", []) or [])
    node_budget = max(1, len(stages) + len(findings) + len(verify))
    share = duration / node_budget

    tree = DiscoveryTree(root_id="root")
    tree.add(
        Node(
            id="root",
            parent_id=None,
            kind="root",
            label=project,
            skill="",
            cost=Cost(agent_calls=0, seconds=0.0, tokens=0),
            observation={"commit": commit},
        )
    )

    stage_ids: dict[str, str] = {}
    stage_status = (report.get("coverage", {}) or {}).get("stages", {}) or {}
    for name in stages:
        node_id = f"stage:{name}"
        stage_ids[name] = node_id
        tree.add(
            Node(
                id=node_id,
                parent_id="root",
                kind="stage",
                label=name.replace("_", " "),
                skill=name,
                tags=_tags(name),
                cost=Cost(agent_calls=1, seconds=share),
                observation={"status": stage_status.get(name, "unknown")},
            )
        )

    for index, finding in enumerate(findings):
        finding_id = str(finding.get("id") or f"F-{index + 1:02d}")
        category = str(finding.get("category", "unknown"))
        evidence = finding.get("evidence", []) or []
        scope = str(evidence[0]) if evidence else ""
        parent_id = _stage_for(category, stage_ids)
        outcome = outcome_from_lookup(
            project, finding_id, finding, curated, handoff, verify
        )
        node = Node(
            id=f"finding:{finding_id}",
            parent_id=parent_id,
            kind="finding",
            label=str(finding.get("title", finding_id)),
            scope=scope,
            skill=category,
            hypothesis=str(finding.get("root_cause", "")),
            tags=_tags(
                finding.get("title", ""),
                category,
                " ".join(map(str, finding.get("cwe", []) or [])),
                " ".join(map(str, evidence)),
                finding.get("root_cause", ""),
            ),
            prior_severity=str(finding.get("severity", "unknown")).lower(),
            observation={
                "finding_id": finding_id,
                "category": category,
                "cwe": finding.get("cwe", []),
                "preconditions": finding.get("preconditions", []),
                "reproduction_idea": finding.get("reproduction_idea", ""),
            },
            outcome=outcome,
            cost=Cost(agent_calls=1, seconds=share),
        )
        tree.add(node)
        if finding_id in verify:
            tree.add(
                Node(
                    id=f"verify:{finding_id}",
                    parent_id=node.id,
                    kind="verification",
                    label=f"verify {finding_id}",
                    skill="verify-agent",
                    tags=_tags(
                        "verify",
                        finding_id,
                        verify[finding_id].get("verdict", ""),
                    ),
                    prior_severity=str(finding.get("severity", "unknown")).lower(),
                    observation={
                        "verdict": verify[finding_id].get("verdict", ""),
                        "reason": verify[finding_id].get("reason", ""),
                    },
                    outcome=_verify_outcome(verify[finding_id], finding),
                    cost=Cost(agent_calls=1, seconds=share),
                )
            )

    errors = tree.validate()
    if errors:
        raise ValueError(f"invalid tree for {run_path}: {errors}")

    world = ReplayWorld(
        world_id=f"{project}@{commit[:8]}-{run_path.name}",
        project=project,
        commit=commit,
        tree=tree,
        meta={
            "run_dir": str(run_path),
            "model": meta.get("model", ""),
            "agent": meta.get("agent", ""),
            "duration_seconds": duration,
            "project_type": target.get("project_type", ""),
            "severity_counts": (report.get("summary", {}) or {}).get(
                "severity_counts", {}
            ),
            "stages": stage_status,
            "has_verify": bool(verify),
        },
    )
    return world


def load_labels(
    curated_path: str | Path | None,
    handoff_path: str | Path | None,
    adjudication_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    curated = _load_json(Path(curated_path), {}) if curated_path else {}
    adjudication_raw = (
        _load_json(Path(adjudication_path), {}) if adjudication_path else {}
    )
    adjudication = (
        adjudication_raw.get("findings", adjudication_raw)
        if isinstance(adjudication_raw, dict)
        else {}
    )
    for key, entry in adjudication.items():
        if not isinstance(entry, dict):
            continue
        merged = dict(curated.get(key, {}))
        merged.update(entry)
        curated[key] = merged
    handoff_raw = _load_json(Path(handoff_path), {}) if handoff_path else {}
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in handoff_raw.get("candidates", []):
        project = candidate.get("project")
        finding_id = candidate.get("finding_id")
        if project and finding_id:
            index[(str(project), str(finding_id))] = candidate
    return curated, index


def import_runs(
    runs_root: str | Path,
    projects: Iterable[str] | None = None,
    latest: bool = True,
    curated_path: str | Path | None = None,
    handoff_path: str | Path | None = None,
    adjudication_path: str | Path | None = None,
    skip_empty: bool = True,
) -> TracePool:
    curated, handoff = load_labels(
        curated_path, handoff_path, adjudication_path
    )
    wanted = set(projects) if projects else None
    run_dirs = find_run_dirs(runs_root)
    if wanted:
        run_dirs = [
            path for path in run_dirs if path.parent.name in wanted
        ]
    if latest:
        by_project: dict[str, Path] = {}
        for path in run_dirs:
            by_project[path.parent.name] = path
        run_dirs = sorted(by_project.values())

    worlds = []
    for path in run_dirs:
        world = import_run(path, curated=curated, handoff=handoff)
        if skip_empty and not any(
            node.kind == "finding" for node in world.tree.nodes.values()
        ):
            continue
        worlds.append(world)
    return TracePool(
        worlds=worlds,
        meta={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "runs_root": str(Path(runs_root)),
            "latest_per_project": latest,
            "projects": sorted({w.project for w in worlds}),
            "count": len(worlds),
        },
    )
