from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from .schema import SPLITS, STAGES, validate_dataset
from .store import VersionStore


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_init(args: argparse.Namespace) -> int:
    store = VersionStore(args.root)
    stages = args.stage or list(STAGES)
    for stage in stages:
        path = store.init_stage(stage)
        print(f"initialized {stage}: {path}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    store = VersionStore(args.root)
    cost = json.loads(args.cost_json) if args.cost_json else {}
    parent = "" if args.no_parent else args.parent
    meta = store.create(
        stage=args.stage,
        skill_path=args.skill,
        dataset_path=args.dataset or None,
        eval_path=args.eval or None,
        gate_path=args.gate or None,
        provenance_path=args.provenance or None,
        parent=parent,
        tag=args.tag,
        promote=args.promote,
        operator=args.operator or os.environ.get("USER", "unknown"),
        optimizer_model=args.optimizer_model,
        target_model=args.target_model,
        prompt_path=args.prompt or None,
        cost=cost,
        base_git_commit=args.base_git_commit,
        base_git_dirty=args.base_git_dirty,
    )
    payload = {
        "stage": meta["stage"],
        "version_id": meta["version_id"],
        "tag": meta["tag"],
        "parent_version": meta["parent_version"],
        "path": str(store.versions_dir(args.stage) / meta["version_id"]),
    }
    if args.json:
        _print_json({**meta, "path": payload["path"]})
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    store = VersionStore(args.root)
    errors = store.validate()
    if args.json:
        _print_json({"errors": errors, "ok": not errors})
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print(f"ok: {args.root}")
    return 1 if errors else 0


def cmd_list(args: argparse.Namespace) -> int:
    store = VersionStore(args.root)
    rows = store.list(args.stage)
    if args.json:
        _print_json(rows)
        return 0
    if not rows:
        print("no versions")
        return 0
    print(f"{'STAGE':<8} {'TAG':<18} {'VERSION':<12} {'PARENT':<12} {'GATE':<10} {'CREATED'}")
    for row in rows:
        print(
            f"{row.get('stage',''):<8} {row.get('tag',''):<18} "
            f"{str(row.get('version_id',''))[:12]:<12} "
            f"{str(row.get('parent_version') or '-')[:12]:<12} "
            f"{str(row.get('gate',{}).get('status','')):<10} "
            f"{row.get('created_at','')}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = VersionStore(args.root)
    version_id = args.version or store.current_version(args.stage)
    if not version_id:
        print(f"no current version for stage {args.stage}", file=sys.stderr)
        return 1
    meta = store.load(args.stage, version_id)
    if args.json:
        _print_json(meta)
        return 0
    for key in (
        "stage",
        "version_id",
        "tag",
        "parent_version",
        "base_git_commit",
        "base_git_dirty",
        "created_at",
        "operator",
        "optimizer_model",
        "target_model",
    ):
        print(f"{key}: {meta.get(key)}")
    print("gate:", json.dumps(meta.get("gate", {}), ensure_ascii=False))
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    store = VersionStore(args.root)
    current = store.promote(args.stage, args.version)
    if args.json:
        _print_json(current)
    else:
        print(json.dumps(current, ensure_ascii=False, indent=2))
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    store = VersionStore(args.root)
    current = store.current(args.stage)
    if args.json:
        _print_json(current)
    elif current:
        print(json.dumps(current, ensure_ascii=False, indent=2))
    else:
        print(f"no current version for stage {args.stage}")
    return 0 if current else 1


def cmd_check_dataset(args: argparse.Namespace) -> int:
    path = Path(args.dataset)
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = validate_dataset(dataset, strict_holdout=args.strict_holdout)
    counts = {
        split: len(dataset.get("splits", {}).get(split, []))
        for split in SPLITS
    }
    if args.json:
        _print_json({"ok": not errors, "errors": errors, "counts": counts})
    else:
        print(f"dataset: {path}")
        print("counts:", counts)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
        else:
            print("ok")
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rsi-version",
        description="Version and provenance store for mygoldmine RSI skills",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize stage directories")
    p_init.add_argument("--root", default="rsi")
    p_init.add_argument("--stage", action="append", default=[])
    p_init.set_defaults(func=cmd_init)

    p_create = sub.add_parser("create", help="create an immutable version")
    p_create.add_argument("--root", default="rsi")
    p_create.add_argument("--stage", required=True)
    p_create.add_argument("--skill", required=True)
    p_create.add_argument("--dataset", default="")
    p_create.add_argument("--eval", default="")
    p_create.add_argument("--gate", default="")
    p_create.add_argument("--provenance", default="")
    p_create.add_argument("--parent", default=None)
    p_create.add_argument("--no-parent", action="store_true")
    p_create.add_argument("--tag", default="")
    p_create.add_argument("--promote", action="store_true")
    p_create.add_argument("--operator", default="")
    p_create.add_argument("--optimizer-model", default="")
    p_create.add_argument("--target-model", default="")
    p_create.add_argument("--prompt", default="")
    p_create.add_argument("--cost-json", default="")
    p_create.add_argument("--base-git-commit", default=None)
    p_create.add_argument(
        "--base-git-dirty", action=argparse.BooleanOptionalAction, default=None
    )
    p_create.add_argument("--json", action="store_true")
    p_create.set_defaults(func=cmd_create)

    p_validate = sub.add_parser("validate", help="validate versions and datasets")
    p_validate.add_argument("--root", default="rsi")
    p_validate.add_argument("--json", action="store_true")
    p_validate.set_defaults(func=cmd_validate)

    p_list = sub.add_parser("list", help="list versions")
    p_list.add_argument("--root", default="rsi")
    p_list.add_argument("--stage", default="")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="show a version manifest")
    p_show.add_argument("--root", default="rsi")
    p_show.add_argument("--stage", required=True)
    p_show.add_argument("--version", default="")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_promote = sub.add_parser("promote", help="update current.json")
    p_promote.add_argument("--root", default="rsi")
    p_promote.add_argument("--stage", required=True)
    p_promote.add_argument("--version", required=True)
    p_promote.add_argument("--json", action="store_true")
    p_promote.set_defaults(func=cmd_promote)

    p_current = sub.add_parser("current", help="print current.json")
    p_current.add_argument("--root", default="rsi")
    p_current.add_argument("--stage", required=True)
    p_current.add_argument("--json", action="store_true")
    p_current.set_defaults(func=cmd_current)

    p_dataset = sub.add_parser("check-dataset", help="validate a dataset manifest")
    p_dataset.add_argument("--dataset", required=True)
    p_dataset.add_argument(
        "--strict-holdout", action=argparse.BooleanOptionalAction, default=True
    )
    p_dataset.add_argument("--json", action="store_true")
    p_dataset.set_defaults(func=cmd_check_dataset)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
