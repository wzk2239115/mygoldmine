"""Online/offline loop: explore, replay, dream, promote, plan."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .adapters.runs import (
    import_run,
    import_runs,
    load_labels,
    manifest_projects,
)
from .learning.discover import DiscoverResult, discover
from .learning.proposer import PolicyProposer
from .objective import (
    DEFAULT_BETAS,
    DEFAULT_MAX_ROUNDS,
    PolicyScore,
    evaluate,
)
from .policy.baseline import BaselinePolicy
from .policy.heuristics import BUILTIN_POLICIES
from .policy.loader import load_policy_file
from .world import TracePool


def policy_factory(name: str, out_dir: str | Path = "rsi"):
    if name in {"method", "learned"}:
        method = Path(out_dir) / "policy" / "method.py"
        if method.exists():
            return load_policy_file(method)
        return BaselinePolicy
    if name in BUILTIN_POLICIES:
        return BUILTIN_POLICIES[name]
    raise KeyError(f"unknown policy: {name}")


def _skill_tags(skill: str) -> list[str]:
    return [
        part.strip().lower()
        for part in re.split(r"[/,;|]", skill or "")
        if part.strip()
    ]


def _tag_stats(score: PolicyScore, pool: TracePool) -> dict[str, dict[str, Any]]:
    worlds = {world.world_id: world for world in pool.worlds}
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "tp": 0,
            "fp": 0,
            "duplicate": 0,
            "design": 0,
            "unclear": 0,
            "calls": 0,
            "skills": set(),
        }
    )
    for replay in score.per_world:
        world = worlds.get(replay.world_id)
        if world is None:
            continue
        for node_id in replay.revealed:
            node = world.tree.nodes.get(node_id)
            if node is None:
                continue
            verdict = node.outcome.verdict
            tags = set(node.tags)
            tags.update(_skill_tags(node.skill))
            if not tags:
                tags.add("unknown")
            for tag in tags:
                if len(tag) > 64:
                    continue
                entry = stats[tag]
                if verdict in entry:
                    entry[verdict] += 1
                entry["calls"] += node.cost.agent_calls
                entry["skills"].add(node.skill)
    return stats


def _ranked_tags(stats: dict[str, dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    priorities: list[dict[str, Any]] = []
    low: list[dict[str, Any]] = []
    for tag, entry in stats.items():
        judged = (
            entry["tp"]
            + entry["fp"]
            + entry["duplicate"]
            + entry["design"]
            + entry["unclear"]
        )
        tp_rate = entry["tp"] / judged if judged else 0.0
        fp_rate = (entry["fp"] + entry["duplicate"]) / judged if judged else 0.0
        item = {
            "tag": tag,
            "tp": entry["tp"],
            "fp": entry["fp"],
            "duplicate": entry["duplicate"],
            "design": entry["design"],
            "unclear": entry["unclear"],
            "calls": entry["calls"],
            "tp_rate": round(tp_rate, 4),
            "fp_rate": round(fp_rate, 4),
        }
        priorities.append(item)
        if judged and entry["tp"] == 0 and (entry["fp"] + entry["duplicate"]) > 0:
            low.append(item)
    priorities.sort(
        key=lambda x: (x["tp_rate"], x["tp"], -x["calls"]), reverse=True
    )
    low.sort(key=lambda x: (x["fp_rate"], x["calls"]), reverse=True)
    return priorities, low


def _per_project(score: PolicyScore, pool: TracePool) -> list[dict[str, Any]]:
    worlds = {world.world_id: world for world in pool.worlds}
    result: list[dict[str, Any]] = []
    for replay in score.per_world:
        world = worlds.get(replay.world_id)
        if world is None:
            continue
        nodes = []
        for node_id in replay.revealed:
            node = world.tree.nodes.get(node_id)
            if node is None or node.kind != "finding":
                continue
            if node.outcome.verdict != "tp":
                continue
            nodes.append(
                {
                    "id": node.observation.get("finding_id", node.id),
                    "title": node.label,
                    "scope": node.scope,
                    "tags": node.tags,
                    "severity": node.outcome.severity,
                    "cve_tier": node.outcome.cve_tier,
                    "score": round(node.score(), 4),
                }
            )
        nodes.sort(key=lambda x: x["score"], reverse=True)
        result.append(
            {
                "world_id": replay.world_id,
                "project": replay.project,
                "score": round(replay.score, 4),
                "top_findings": nodes[:8],
            }
        )
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def plan_from_pool(
    pool: TracePool,
    policy_name: str = "method",
    out_dir: str | Path = "rsi",
    betas: Sequence[float] = DEFAULT_BETAS,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    top: int = 12,
) -> dict[str, Any]:
    score = evaluate(
        policy_factory(policy_name, out_dir),
        pool,
        betas=betas,
        max_workers=max_workers,
        max_rounds=max_rounds,
    )
    stats = _tag_stats(score, pool)
    priorities, low = _ranked_tags(stats)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": score.policy,
        "score": round(score.score, 6),
        "mean_fp_rate": round(score.mean_fp_rate, 6),
        "mean_dup_rate": round(score.mean_dup_rate, 6),
        "mean_coverage": round(score.mean_coverage, 6),
        "total_calls": score.total_calls,
        "priorities": priorities[:top],
        "deprioritize": low[:top],
        "per_project": _per_project(score, pool),
        "worlds": [w.summary() for w in pool.worlds],
    }


def render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# audit-rsi 优先审计计划",
        "",
        f"- generated_at: {plan['generated_at']}",
        f"- policy: {plan['policy']}",
        f"- replay score: {plan['score']}",
        f"- FP rate: {plan['mean_fp_rate']}",
        f"- duplicate rate: {plan['mean_dup_rate']}",
        f"- coverage: {plan['mean_coverage']}",
        f"- total calls: {plan['total_calls']}",
        "",
        "## 高产出方向",
        "",
        "| tag | TP | FP | DUP | TP rate | calls |",
        "|---|---|---|---|---|---|",
    ]
    for item in plan["priorities"]:
        lines.append(
            f"| {item['tag']} | {item['tp']} | {item['fp']} | "
            f"{item['duplicate']} | {item['tp_rate']} | {item['calls']} |"
        )
    if plan["deprioritize"]:
        lines.extend(["", "## 降级方向", ""])
        for item in plan["deprioritize"]:
            lines.append(
                f"- {item['tag']}: tp=0 fp={item['fp']} "
                f"dup={item['duplicate']} calls={item['calls']}"
            )
    lines.extend(["", "## 按项目", ""])
    for project in plan["per_project"]:
        lines.append(
            f"### {project['project']} ({project['world_id']})"
        )
        if not project["top_findings"]:
            lines.append("- 无确认 finding")
            continue
        for finding in project["top_findings"]:
            lines.append(
                f"- {finding['id']} [{finding['severity']}] "
                f"{finding['title']} @ {finding['scope']}"
            )
    lines.extend(["", "## 预算建议", ""])
    if plan["mean_fp_rate"] > 0.15:
        lines.append("- 先做证据/可达性预筛，再升级到 CVE 跟踪，避免 FP 消耗。")
    elif plan["mean_coverage"] < 0.4:
        lines.append("- 先扩大入口/类别覆盖，再对单条链路加深。")
    else:
        lines.append("- 维持覆盖面，把预算集中到高产出 tag 的深挖与验证。")
    lines.append("")
    return "\n".join(lines)


def write_plan(plan: dict[str, Any], out_dir: str | Path = "rsi") -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "plan.json"
    md_path = out / "plan.md"
    json_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_plan_markdown(plan), encoding="utf-8")
    return json_path, md_path


@dataclass
class MineExplorer:
    repo_root: Path
    model: str = "360-proxy/deepseek/deepseek-v4.1-flash"
    agent: str = "security-orchestrator"
    timeout: int = 21600

    def run(
        self,
        project: str,
        target: Path,
        run_dir: Path,
        plan_file: Path,
    ) -> Path:
        command = [
            "bash",
            str(self.repo_root / "scripts" / "mine" / "mine_one.sh"),
            "--target",
            str(target),
            "--project",
            project,
            "--run-dir",
            str(run_dir),
            "--timeout",
            str(self.timeout),
            "--model",
            self.model,
            "--agent",
            self.agent,
        ]
        env = os.environ.copy()
        env["RSI_PLAN_FILE"] = str(plan_file)
        subprocess.run(
            command,
            cwd=str(self.repo_root),
            env=env,
            check=True,
        )
        return run_dir


def resolve_targets(repo_root: str | Path) -> list[tuple[str, Path]]:
    root = Path(repo_root)
    manifest = root / "targets" / "manifest.json"
    if not manifest.exists():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    targets = []
    for project, entry in data.get("projects", {}).items():
        if entry.get("status", "ok") != "ok":
            continue
        path = Path(entry.get("path") or root / "targets" / project)
        if path.exists():
            targets.append((project, path))
    return targets


def evolve(
    runs_root: str | Path = "runs",
    out_dir: str | Path = "rsi",
    cycles: int = 1,
    rounds: int = 3,
    online: bool = False,
    proposer: PolicyProposer | None = None,
    targets: list[tuple[str, Path]] | None = None,
    curated_path: str | Path | None = None,
    handoff_path: str | Path | None = None,
    adjudication_path: str | Path | None = None,
    betas: Sequence[float] = DEFAULT_BETAS,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parent.parent
    projects = manifest_projects(repo_root) or None
    pool = import_runs(
        runs_root,
        projects=projects,
        latest=True,
        curated_path=curated_path,
        handoff_path=handoff_path,
        adjudication_path=adjudication_path,
    )
    history: list[dict[str, Any]] = []
    discover_result: DiscoverResult | None = None
    plan: dict[str, Any] | None = None

    for cycle in range(max(1, cycles)):
        discover_result = discover(
            pool,
            proposer=proposer,
            rounds=rounds,
            betas=betas,
            max_workers=max_workers,
            max_rounds=max_rounds,
            out_dir=out_dir,
        )
        plan = plan_from_pool(
            pool,
            policy_name="method",
            out_dir=out_dir,
            betas=betas,
            max_workers=max_workers,
            max_rounds=max_rounds,
        )
        write_plan(plan, out_dir)
        history.append(
            {
                "cycle": cycle,
                "worlds": len(pool.worlds),
                "best_policy": discover_result.best_policy,
                "best_score": round(discover_result.best_score, 6),
                "baseline_score": round(discover_result.baseline_score, 6),
            }
        )
        if not online:
            break
        if targets is None:
            targets = resolve_targets(repo_root)
        if not targets:
            break
        curated, handoff = load_labels(
            curated_path, handoff_path, adjudication_path
        )
        explorer = MineExplorer(repo_root)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for project, target in targets:
            run_dir = Path(runs_root) / project / stamp
            explorer.run(project, target, run_dir, Path(out_dir) / "plan.md")
            world = import_run(run_dir, curated=curated, handoff=handoff)
            pool.worlds.append(world)

    return {
        "cycles": history,
        "discover": discover_result.to_dict() if discover_result else None,
        "plan": plan,
        "pool": pool.summary(),
    }
