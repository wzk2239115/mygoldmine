from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Sequence

from .adapters.runs import import_runs, manifest_projects
from .learning.discover import discover
from .learning.proposer import AgentProposer, TemplateProposer
from .learning.replay import replay_all_builtin
from .objective import (
    DEFAULT_BETAS,
    DEFAULT_MAX_ROUNDS,
    PolicyScore,
    evaluate,
)
from .orchestrate import (
    evolve,
    plan_from_pool,
    policy_factory,
    resolve_targets,
    write_plan,
)
from .world import TracePool

REPO_ROOT = Path(__file__).resolve().parent.parent


def _betas(text: str) -> list[float]:
    values = [float(part) for part in text.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("betas must not be empty")
    return values


def _targets(text: str | None) -> list[tuple[str, Path]] | None:
    if not text:
        return None
    manifest = dict(resolve_targets(REPO_ROOT))
    result: list[tuple[str, Path]] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            project, path = item.split("=", 1)
            result.append((project, Path(path)))
        elif item in manifest:
            result.append((item, manifest[item]))
        else:
            raise SystemExit(f"unknown target: {item}")
    return result


def _load_pool(path: str | Path) -> TracePool:
    return TracePool.load(path)


def _emit(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if isinstance(data, PolicyScore):
        print(
            f"{data.policy:>16}  score={data.score:.4f}  "
            f"fp={data.mean_fp_rate:.3f}  dup={data.mean_dup_rate:.3f}  "
            f"coverage={data.mean_coverage:.3f}  calls={data.total_calls}"
        )
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_import(args: argparse.Namespace) -> int:
    key = {"curated": args.curated, "handoff": args.handoff}
    projects = args.project or manifest_projects(REPO_ROOT) or None
    pool = import_runs(
        args.runs,
        projects=projects,
        latest=not args.all,
        curated_path=key["curated"],
        handoff_path=key["handoff"],
        adjudication_path=args.adjudication,
        skip_empty=not args.include_empty,
    )
    out = Path(args.out)
    pool.save(out / "trace_pool.json")
    for world in pool.worlds:
        safe = world.world_id.replace("/", "_").replace(":", "_")
        world.save(out / "worlds" / f"{safe}.json")
    _emit(pool.summary(), args.json)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    pool = _load_pool(args.pool)
    payload = {
        "summary": pool.summary(),
        "worlds": [world.summary() for world in pool.worlds],
    }
    _emit(payload, args.json)
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    pool = _load_pool(args.pool)
    if args.policy == "all":
        results = replay_all_builtin(
            pool,
            betas=args.betas,
            max_workers=args.workers,
            max_rounds=args.max_rounds,
        )
        if args.json:
            print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
        else:
            for result in results:
                _emit(result, False)
        return 0
    result = evaluate(
        policy_factory(args.policy, args.out),
        pool,
        betas=args.betas,
        max_workers=args.workers,
        max_rounds=args.max_rounds,
    )
    _emit(result.to_dict() if args.json else result, args.json)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    pool = _load_pool(args.pool)
    holdout = None
    if args.holdout_project:
        holdout_ids = [
            world.world_id
            for world in pool.worlds
            if world.project == args.holdout_project
        ]
        if not holdout_ids:
            raise SystemExit(f"no worlds for project: {args.holdout_project}")
        holdout = pool.subset(holdout_ids)
        pool = pool.exclude(holdout_ids)
    proposer = None
    if args.agent_cmd:
        proposer = AgentProposer(
            shlex.split(args.agent_cmd),
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
    else:
        proposer = TemplateProposer()
    result = discover(
        pool,
        proposer=proposer,
        rounds=args.rounds,
        betas=args.betas,
        max_workers=args.workers,
        max_rounds=args.max_rounds,
        out_dir=args.out,
        holdout=holdout,
    )
    _emit(result.to_dict(), args.json)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    pool = _load_pool(args.pool)
    plan = plan_from_pool(
        pool,
        policy_name=args.policy,
        out_dir=args.out,
        betas=args.betas,
        max_workers=args.workers,
        max_rounds=args.max_rounds,
        top=args.top,
    )
    json_path, md_path = write_plan(plan, args.out)
    payload = {
        "plan_json": str(json_path),
        "plan_md": str(md_path),
        "policy": plan["policy"],
        "score": plan["score"],
        "priorities": plan["priorities"],
        "deprioritize": plan["deprioritize"],
    }
    _emit(payload, args.json)
    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    proposer = None
    if args.agent_cmd:
        proposer = AgentProposer(
            shlex.split(args.agent_cmd),
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
    else:
        proposer = TemplateProposer()
    result = evolve(
        runs_root=args.runs,
        out_dir=args.out,
        cycles=args.cycles,
        rounds=args.rounds,
        online=args.online,
        proposer=proposer,
        targets=_targets(args.targets),
        curated_path=args.curated,
        handoff_path=args.handoff,
        adjudication_path=args.adjudication,
        betas=args.betas,
        max_workers=args.workers,
        max_rounds=args.max_rounds,
    )
    _emit(result, args.json)
    return 0


def _common(sub: argparse.ArgumentParser, pool_default: str) -> None:
    sub.add_argument("--pool", default=pool_default)
    sub.add_argument("--out", default=str(REPO_ROOT / "rsi"))
    sub.add_argument("--betas", type=_betas, default=list(DEFAULT_BETAS))
    sub.add_argument("--workers", type=int, default=10)
    sub.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    sub.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit-rsi",
        description="Dream-RSI meta-layer for the mygoldmine audit pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="turn runs/ into replay worlds")
    p_import.add_argument("--runs", default=str(REPO_ROOT / "runs"))
    p_import.add_argument("--out", default=str(REPO_ROOT / "rsi"))
    p_import.add_argument("--project", action="append", default=[])
    p_import.add_argument("--all", action="store_true")
    p_import.add_argument("--include-empty", action="store_true")
    p_import.add_argument(
        "--curated", default=str(REPO_ROOT / "ui" / "data" / "curated.json")
    )
    p_import.add_argument(
        "--handoff", default=str(REPO_ROOT / "docs" / "cve-handoff.json")
    )
    p_import.add_argument(
        "--adjudication",
        default=str(REPO_ROOT / "docs" / "cve-adjudication.json"),
    )
    p_import.add_argument("--json", action="store_true")
    p_import.set_defaults(func=cmd_import)

    p_show = sub.add_parser("show", help="summarize a trace pool")
    p_show.add_argument(
        "--pool", default=str(REPO_ROOT / "rsi" / "trace_pool.json")
    )
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_replay = sub.add_parser("replay", help="score a policy offline")
    _common(p_replay, str(REPO_ROOT / "rsi" / "trace_pool.json"))
    p_replay.add_argument("--policy", default="baseline")
    p_replay.set_defaults(func=cmd_replay)

    p_discover = sub.add_parser("discover", help="dream a new policy")
    _common(p_discover, str(REPO_ROOT / "rsi" / "trace_pool.json"))
    p_discover.add_argument("--rounds", type=int, default=3)
    p_discover.add_argument("--agent-cmd", default="")
    p_discover.add_argument("--timeout", type=int, default=1800)
    p_discover.add_argument("--dry-run", action="store_true")
    p_discover.add_argument("--holdout-project", default="")
    p_discover.set_defaults(func=cmd_discover)

    p_plan = sub.add_parser("plan", help="emit the next audit plan")
    _common(p_plan, str(REPO_ROOT / "rsi" / "trace_pool.json"))
    p_plan.add_argument("--policy", default="method")
    p_plan.add_argument("--top", type=int, default=12)
    p_plan.set_defaults(func=cmd_plan)

    p_evolve = sub.add_parser("evolve", help="run the full loop")
    p_evolve.add_argument("--runs", default=str(REPO_ROOT / "runs"))
    p_evolve.add_argument("--out", default=str(REPO_ROOT / "rsi"))
    p_evolve.add_argument("--cycles", type=int, default=1)
    p_evolve.add_argument("--rounds", type=int, default=3)
    p_evolve.add_argument("--online", action="store_true")
    p_evolve.add_argument("--targets", default="")
    p_evolve.add_argument("--agent-cmd", default="")
    p_evolve.add_argument("--timeout", type=int, default=1800)
    p_evolve.add_argument("--dry-run", action="store_true")
    p_evolve.add_argument(
        "--curated", default=str(REPO_ROOT / "ui" / "data" / "curated.json")
    )
    p_evolve.add_argument(
        "--handoff", default=str(REPO_ROOT / "docs" / "cve-handoff.json")
    )
    p_evolve.add_argument(
        "--adjudication",
        default=str(REPO_ROOT / "docs" / "cve-adjudication.json"),
    )
    p_evolve.add_argument("--betas", type=_betas, default=list(DEFAULT_BETAS))
    p_evolve.add_argument("--workers", type=int, default=10)
    p_evolve.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    p_evolve.add_argument("--json", action="store_true")
    p_evolve.set_defaults(func=cmd_evolve)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
