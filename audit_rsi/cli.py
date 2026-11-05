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
        fp = f"{data.mean_fp_rate:.3f}" if data.mean_fp_rate is not None else "N/A"
        dup = (
            f"{data.mean_dup_rate:.3f}" if data.mean_dup_rate is not None else "N/A"
        )
        labels = (
            f"{data.mean_label_coverage:.3f}"
            if data.mean_label_coverage is not None
            else "N/A"
        )
        print(
            f"{data.policy:>16}  score={data.score:.4f}  "
            f"fp={fp}  dup={dup}  labels={labels}  "
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
        holdout_project=args.holdout_project,
        betas=args.betas,
        max_workers=args.workers,
        max_rounds=args.max_rounds,
    )
    _emit(result, args.json)
    return 0


def cmd_experience_build(args: argparse.Namespace) -> int:
    try:
        from .experience import build_experience
    except ImportError as exc:
        raise SystemExit(
            "experience-build requires audit_rsi.experience.build_experience"
        ) from exc
    records = build_experience(runs_root=Path(args.runs), output_path=Path(args.output))
    _emit(
        {"output": str(Path(args.output)), "records": len(records)}, args.json
    )
    return 0


def cmd_label_sample(args: argparse.Namespace) -> int:
    try:
        from .labeling import stratified_sample
    except ImportError as exc:
        raise SystemExit("label-sample requires audit_rsi.labeling.stratified_sample") from exc
    from .verification import read_experience, write_jsonl

    records = read_experience(args.pool)
    sample = stratified_sample(records, sample_size=args.limit, seed=args.seed)
    write_jsonl(args.output, sample)
    _emit(
        {"output": str(Path(args.output)), "records": len(sample)}, args.json
    )
    return 0


def cmd_label_plan(args: argparse.Namespace) -> int:
    from .labeling import trusted_label_plan
    from .verification import read_experience, write_json, write_jsonl

    records = read_experience(args.pool)
    plan = trusted_label_plan(records, sample_size=args.limit, seed=args.seed)
    write_jsonl(args.output, plan["tasks"])
    if args.report:
        write_json(args.report, {"analysis": plan["analysis"], "status": plan["status"]})
    _emit(
        {
            "output": str(Path(args.output)),
            **plan["analysis"],
            "records": len(plan["tasks"]),
        },
        args.json,
    )
    return 0


def cmd_label_merge(args: argparse.Namespace) -> int:
    from .verification import merge_labels, read_experience, write_jsonl

    records = read_experience(args.pool)
    labels = read_experience(args.labels)
    try:
        merged = merge_labels(records, labels)
    except ValueError as exc:
        raise SystemExit(f"label-merge rejected input: {exc}") from exc
    write_jsonl(args.output, merged)
    _emit(
        {
            "output": str(Path(args.output)),
            "records": len(merged),
            "merged_labels": len(labels),
        },
        args.json,
    )
    return 0


def _verification_policy(path: str, epsilon: float):
    from .verification import VerificationPolicy, load_policy

    model = load_policy(path) if path else {}
    return VerificationPolicy(model, epsilon=epsilon)


def cmd_verify_train(args: argparse.Namespace) -> int:
    from .verification import read_experience, save_policy, train_policy

    records = read_experience(args.pool)
    model = train_policy(
        records,
        holdout_project=args.holdout_project,
        ridge=args.ridge,
        seed=args.seed,
    )
    save_policy(args.output, model)
    _emit(model, args.json)
    return 0


def cmd_verify_shadow(args: argparse.Namespace) -> int:
    from .verification import read_experience, write_shadow

    records = read_experience(args.pool)
    policy = _verification_policy(args.train_path, args.epsilon)
    payload = write_shadow(
        args.output,
        records,
        policy,
        epsilon=args.epsilon,
        seed=args.seed,
        holdout_project=args.holdout_project,
    )
    _emit(
        {
            "output": str(Path(args.output)),
            "policy_version": payload["policy_version"],
            "recommendations": len(payload["recommendations"]),
            "mode": payload["mode"],
            "status": payload["status"],
            "reason": payload["reason"],
        },
        args.json,
    )
    return 0


def cmd_verify_replay(args: argparse.Namespace) -> int:
    from .verification import read_experience, replay_policies, write_json

    records = read_experience(args.pool)
    policy = _verification_policy(args.train_path, args.epsilon)
    payload = replay_policies(
        records, policy, holdout_project=args.holdout_project
    )
    if args.output:
        write_json(args.output, payload)
    _emit(payload, args.json)
    return 0


def cmd_verify_flips(args: argparse.Namespace) -> int:
    from .verification import outcome_flip_report, read_experience, write_json

    baseline = read_experience(args.baseline)
    candidate = read_experience(args.candidate)
    payload = outcome_flip_report(
        baseline,
        candidate,
        holdout_project=args.holdout_project,
        min_coverage=args.min_coverage,
        max_pass_to_fail=args.max_pass_to_fail,
        min_fail_to_pass=args.min_fail_to_pass,
    )
    write_json(args.output, payload)
    _emit(payload, args.json)
    return 0


def cmd_redteam_experience(args: argparse.Namespace) -> int:
    from .adapters.redteam import scan_redteam_runs
    from .verification import write_jsonl

    records, steps = scan_redteam_runs(args.runs)
    write_jsonl(args.output, records)
    if args.steps_output:
        write_jsonl(args.steps_output, steps)
    _emit(
        {
            "output": str(Path(args.output)),
            "records": len(records),
            "steps": len(steps),
            "steps_output": args.steps_output or None,
        },
        args.json,
    )
    return 0


def cmd_redteam_weakness(args: argparse.Namespace) -> int:
    from .adapters.redteam import scan_redteam_runs
    from .verification import write_json
    from .weakness import mine_redteam_weaknesses

    records, steps = scan_redteam_runs(args.runs)
    payload = mine_redteam_weaknesses(records, steps)
    write_json(args.output, payload)
    _emit(payload, args.json)
    return 0


def cmd_harness_propose(args: argparse.Namespace) -> int:
    from .harness import propose_harness_candidates
    from .verification import write_json

    weakness = json.loads(Path(args.weakness).read_text(encoding="utf-8"))
    candidates = propose_harness_candidates(weakness, limit=args.limit)
    write_json(args.output, candidates)
    _emit({"output": str(Path(args.output)), "candidates": len(candidates)}, args.json)
    return 0


def cmd_harness_validate(args: argparse.Namespace) -> int:
    from .harness import validate_harness_candidate
    from .verification import write_json

    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    flips = json.loads(Path(args.flips).read_text(encoding="utf-8"))
    payload = validate_harness_candidate(candidate, flips)
    write_json(args.output, payload)
    _emit(payload, args.json)
    return 0


def _mining_repair_candidate(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("mining repair candidate must be a JSON object")
    return payload


def cmd_mining_repair_propose(args: argparse.Namespace) -> int:
    from .mining_repair import (
        load_finding_ledger,
        propose_mining_repairs,
        save_mining_repair_candidates,
    )
    from .verification import read_experience

    records = read_experience(args.pool)
    for additional_pool in args.additional_pool:
        records.extend(read_experience(additional_pool))
    candidates = propose_mining_repairs(
        records,
        ledger=load_finding_ledger(args.ledger),
    )
    report = save_mining_repair_candidates(candidates, args.output)
    _emit({"output": str(Path(args.output) / "index.json"), **report}, args.json)
    return 0


def cmd_mining_repair_evaluate(args: argparse.Namespace) -> int:
    from .mining_repair import evaluate_mining_repair
    from .verification import read_experience, write_json

    candidate = _mining_repair_candidate(args.candidate)
    payload = evaluate_mining_repair(
        candidate,
        read_experience(args.baseline),
        read_experience(args.candidate_pool),
        holdout_projects=args.holdout_project,
    )
    write_json(args.output, payload)
    _emit(payload, args.json)
    return 0


def cmd_mining_repair_apply(args: argparse.Namespace) -> int:
    from .mining_repair import MiningRepairStore

    candidate = _mining_repair_candidate(args.candidate)
    evaluation = json.loads(Path(args.evaluation).read_text(encoding="utf-8"))
    version = MiningRepairStore(REPO_ROOT).apply(candidate, evaluation)
    _emit(version, args.json)
    return 0


def cmd_mining_repair_rollback(args: argparse.Namespace) -> int:
    from .mining_repair import MiningRepairStore

    version = MiningRepairStore(REPO_ROOT).rollback(args.version)
    _emit(version, args.json)
    return 0


def cmd_mining_repair_context(args: argparse.Namespace) -> int:
    from .mining_repair import render_mining_repair_context

    rendered = render_mining_repair_context(
        REPO_ROOT,
        args.project,
        max_bytes=args.max_bytes,
    )
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


def cmd_mining_repair_cycle(args: argparse.Namespace) -> int:
    from .mining_repair import load_finding_ledger, run_mining_repair_cycle
    from .verification import read_experience, write_json

    payload = run_mining_repair_cycle(
        read_experience(args.train_pool),
        read_experience(args.baseline),
        read_experience(args.candidate_pool),
        repo_root=REPO_ROOT,
        ledger=load_finding_ledger(args.ledger),
        holdout_projects=args.holdout_project,
        apply_accepted=not args.dry_run,
    )
    write_json(args.output, payload)
    _emit(
        {
            "output": args.output,
            "status": payload["status"],
            "candidates": payload["candidates"],
            "accepted": payload["accepted"],
            "published": payload["published"],
        },
        args.json,
    )
    return 0


def cmd_mining_repair_drive(args: argparse.Namespace) -> int:
    from .mining_driver import drive_mining_repairs

    payload = drive_mining_repairs(
        REPO_ROOT,
        scope=args.scope,
        project=args.project,
        target=args.target,
        baseline_run=args.baseline_run,
        image=args.image,
        miner_image=args.miner_image,
        manifest=args.manifest,
        output=args.output,
        max_candidates=args.max_candidates,
    )
    _emit(payload, args.json)
    return 2 if payload["status"] == "error" else 0


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
    p_evolve.add_argument("--holdout-project", default="")
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

    p_experience = sub.add_parser(
        "experience-build", help="build verification experience JSONL"
    )
    p_experience.add_argument("--runs", default=str(REPO_ROOT / "runs"))
    p_experience.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "verification-experience.jsonl")
    )
    p_experience.add_argument("--json", action="store_true")
    p_experience.set_defaults(func=cmd_experience_build)

    p_label = sub.add_parser("label-sample", help="sample verification decisions for labels")
    p_label.add_argument(
        "--pool", default=str(REPO_ROOT / "rsi" / "verification-experience.jsonl")
    )
    p_label.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "verification-label-sample.jsonl")
    )
    p_label.add_argument("--limit", type=int, default=100)
    p_label.add_argument("--seed", type=int, default=0)
    p_label.add_argument("--json", action="store_true")
    p_label.set_defaults(func=cmd_label_sample)

    p_label_plan = sub.add_parser(
        "label-plan", help="prioritize missing trusted projects and actions"
    )
    p_label_plan.add_argument(
        "--pool", default=str(REPO_ROOT / "rsi" / "verification-experience.jsonl")
    )
    p_label_plan.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "verification-label-plan.jsonl")
    )
    p_label_plan.add_argument("--report", default="")
    p_label_plan.add_argument("--limit", type=int, default=100)
    p_label_plan.add_argument("--seed", type=int, default=0)
    p_label_plan.add_argument("--json", action="store_true")
    p_label_plan.set_defaults(func=cmd_label_plan)

    p_label_merge = sub.add_parser(
        "label-merge", help="merge reviewed labels into verification experience"
    )
    p_label_merge.add_argument(
        "--pool", default=str(REPO_ROOT / "rsi" / "verification-experience.jsonl")
    )
    p_label_merge.add_argument(
        "--labels", default=str(REPO_ROOT / "rsi" / "verification-label-sample.jsonl")
    )
    p_label_merge.add_argument(
        "--output",
        default=str(REPO_ROOT / "rsi" / "verification-experience-labeled.jsonl"),
    )
    p_label_merge.add_argument("--json", action="store_true")
    p_label_merge.set_defaults(func=cmd_label_merge)

    p_verify_train = sub.add_parser("verify-train", help="train the verification policy")
    p_verify_train.add_argument(
        "--pool", default=str(REPO_ROOT / "rsi" / "verification-experience.jsonl")
    )
    p_verify_train.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "verification-policy.json")
    )
    p_verify_train.add_argument("--holdout-project", default="")
    p_verify_train.add_argument("--ridge", type=float, default=10.0)
    p_verify_train.add_argument("--seed", type=int, default=0)
    p_verify_train.add_argument("--json", action="store_true")
    p_verify_train.set_defaults(func=cmd_verify_train)

    p_verify_shadow = sub.add_parser(
        "verify-shadow", help="write recommendation-only verification advice"
    )
    p_verify_shadow.add_argument(
        "--pool", default=str(REPO_ROOT / "rsi" / "verification-experience.jsonl")
    )
    p_verify_shadow.add_argument(
        "--train", "--model", dest="train_path", default=""
    )
    p_verify_shadow.add_argument(
        "--output", default=str(REPO_ROOT / "ui" / "data" / "verification-shadow.json")
    )
    p_verify_shadow.add_argument("--holdout-project", default="")
    p_verify_shadow.add_argument("--epsilon", type=float, default=0.0)
    p_verify_shadow.add_argument("--seed", type=int, default=0)
    p_verify_shadow.add_argument("--json", action="store_true")
    p_verify_shadow.set_defaults(func=cmd_verify_shadow)

    p_verify_replay = sub.add_parser(
        "verify-replay", help="compare realized baseline/candidate utility"
    )
    p_verify_replay.add_argument(
        "--pool", default=str(REPO_ROOT / "rsi" / "verification-experience.jsonl")
    )
    p_verify_replay.add_argument(
        "--train", "--model", dest="train_path", default=""
    )
    p_verify_replay.add_argument("--output", default="")
    p_verify_replay.add_argument("--holdout-project", default="")
    p_verify_replay.add_argument("--epsilon", type=float, default=0.0)
    p_verify_replay.add_argument("--seed", type=int, default=0)
    p_verify_replay.add_argument("--json", action="store_true")
    p_verify_replay.set_defaults(func=cmd_verify_replay)

    p_verify_flips = sub.add_parser(
        "verify-flips", help="compare per-semantic observed outcome flips"
    )
    p_verify_flips.add_argument("--baseline", required=True)
    p_verify_flips.add_argument("--candidate", required=True)
    p_verify_flips.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "verification-flips.json")
    )
    p_verify_flips.add_argument("--holdout-project", default="")
    p_verify_flips.add_argument("--min-coverage", type=float, default=0.8)
    p_verify_flips.add_argument("--max-pass-to-fail", type=int, default=0)
    p_verify_flips.add_argument("--min-fail-to-pass", type=int, default=1)
    p_verify_flips.add_argument("--json", action="store_true")
    p_verify_flips.set_defaults(func=cmd_verify_flips)

    p_redteam_experience = sub.add_parser(
        "redteam-experience", help="build role-aware red-team experiences and tool steps"
    )
    p_redteam_experience.add_argument("--runs", default=str(REPO_ROOT / "runs" / "redteam"))
    p_redteam_experience.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "redteam-experience.jsonl")
    )
    p_redteam_experience.add_argument("--steps-output", default="")
    p_redteam_experience.add_argument("--json", action="store_true")
    p_redteam_experience.set_defaults(func=cmd_redteam_experience)

    p_redteam_weakness = sub.add_parser(
        "redteam-weakness", help="mine verifier-grounded red-team failure signatures"
    )
    p_redteam_weakness.add_argument("--runs", default=str(REPO_ROOT / "runs" / "redteam"))
    p_redteam_weakness.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "redteam-weakness.json")
    )
    p_redteam_weakness.add_argument("--json", action="store_true")
    p_redteam_weakness.set_defaults(func=cmd_redteam_weakness)

    p_harness_propose = sub.add_parser(
        "harness-propose", help="create bounded, non-mutating harness candidates"
    )
    p_harness_propose.add_argument("--weakness", required=True)
    p_harness_propose.add_argument("--output", required=True)
    p_harness_propose.add_argument("--limit", type=int, default=3)
    p_harness_propose.add_argument("--json", action="store_true")
    p_harness_propose.set_defaults(func=cmd_harness_propose)

    p_harness_validate = sub.add_parser(
        "harness-validate", help="validate a harness candidate against outcome flips"
    )
    p_harness_validate.add_argument("--candidate", required=True)
    p_harness_validate.add_argument("--flips", required=True)
    p_harness_validate.add_argument("--output", required=True)
    p_harness_validate.add_argument("--json", action="store_true")
    p_harness_validate.set_defaults(func=cmd_harness_validate)

    repair_pool_default = str(REPO_ROOT / "rsi" / "verification-experience-labeled.jsonl")
    repair_ledger_default = str(REPO_ROOT / "ui" / "data" / "finding-ledger.json")

    p_repair_propose = sub.add_parser(
        "mining-repair-propose",
        help="propose shared and project mining repairs from verified outcomes",
    )
    p_repair_propose.add_argument("--pool", default=repair_pool_default)
    p_repair_propose.add_argument("--additional-pool", action="append", default=[])
    p_repair_propose.add_argument("--ledger", default=repair_ledger_default)
    p_repair_propose.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "mining-repairs" / "candidates")
    )
    p_repair_propose.add_argument("--json", action="store_true")
    p_repair_propose.set_defaults(func=cmd_mining_repair_propose)

    p_repair_evaluate = sub.add_parser(
        "mining-repair-evaluate",
        help="evaluate a mining repair on two real mining runs",
    )
    p_repair_evaluate.add_argument("--candidate", required=True)
    p_repair_evaluate.add_argument("--baseline", required=True)
    p_repair_evaluate.add_argument("--candidate-pool", required=True)
    p_repair_evaluate.add_argument("--holdout-project", action="append", default=[])
    p_repair_evaluate.add_argument("--output", required=True)
    p_repair_evaluate.add_argument("--json", action="store_true")
    p_repair_evaluate.set_defaults(func=cmd_mining_repair_evaluate)

    p_repair_apply = sub.add_parser(
        "mining-repair-apply",
        help="publish an evaluated mining repair and retain a rollback version",
    )
    p_repair_apply.add_argument("--candidate", required=True)
    p_repair_apply.add_argument("--evaluation", required=True)
    p_repair_apply.add_argument("--json", action="store_true")
    p_repair_apply.set_defaults(func=cmd_mining_repair_apply)

    p_repair_rollback = sub.add_parser(
        "mining-repair-rollback",
        help="roll back the latest active mining repair version",
    )
    p_repair_rollback.add_argument("--version", required=True)
    p_repair_rollback.add_argument("--json", action="store_true")
    p_repair_rollback.set_defaults(func=cmd_mining_repair_rollback)

    p_repair_context = sub.add_parser(
        "mining-repair-context",
        help="render published shared and current-project mining repairs",
    )
    p_repair_context.add_argument("--project", required=True)
    p_repair_context.add_argument("--max-bytes", type=int, default=65536)
    p_repair_context.add_argument("--output", default="")
    p_repair_context.set_defaults(func=cmd_mining_repair_context)

    p_repair_cycle = sub.add_parser(
        "mining-repair-cycle",
        help="propose, independently evaluate and publish mining repairs",
    )
    p_repair_cycle.add_argument("--train-pool", required=True)
    p_repair_cycle.add_argument("--baseline", required=True)
    p_repair_cycle.add_argument("--candidate-pool", required=True)
    p_repair_cycle.add_argument("--ledger", default=repair_ledger_default)
    p_repair_cycle.add_argument("--holdout-project", action="append", default=[])
    p_repair_cycle.add_argument(
        "--output", default=str(REPO_ROOT / "rsi" / "mining-repairs" / "cycle.json")
    )
    p_repair_cycle.add_argument("--dry-run", action="store_true")
    p_repair_cycle.add_argument("--json", action="store_true")
    p_repair_cycle.set_defaults(func=cmd_mining_repair_cycle)

    p_repair_drive = sub.add_parser(
        "mining-repair-drive",
        help="run candidates through isolated real mining, verification and red-team stages",
    )
    p_repair_drive.add_argument("--scope", choices=["project", "shared"], required=True)
    p_repair_drive.add_argument("--project", default="")
    p_repair_drive.add_argument("--target", default="")
    p_repair_drive.add_argument("--baseline-run", default="")
    p_repair_drive.add_argument("--image", default="")
    p_repair_drive.add_argument("--miner-image", default="")
    p_repair_drive.add_argument("--manifest", default="")
    p_repair_drive.add_argument("--output", default="")
    p_repair_drive.add_argument("--max-candidates", type=int, default=1)
    p_repair_drive.add_argument("--json", action="store_true")
    p_repair_drive.set_defaults(func=cmd_mining_repair_drive)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
