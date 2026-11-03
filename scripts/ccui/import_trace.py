#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from import_runs import convert_run


def main() -> int:
    parser = argparse.ArgumentParser(description="将一个 Claude Code 节点轨迹导入只读会话")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--sidecar", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--agent", default="")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    result = convert_run(
        run_dir,
        Path(args.home).resolve(),
        run_dir.parent.name,
        raw_path=Path(args.raw).resolve(),
        sidecar_path=Path(args.sidecar).resolve(),
        title_suffix=args.title,
        agent_name=args.agent,
    )
    if not result:
        return 1
    session_id, out_path = result
    print(f"{session_id} ({out_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
