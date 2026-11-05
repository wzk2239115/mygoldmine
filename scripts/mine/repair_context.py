#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

render_mining_repair_context = importlib.import_module(
    "audit_rsi.mining_repair"
).render_mining_repair_context


def main() -> int:
    parser = argparse.ArgumentParser(description="Render active mining repairs for one project")
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", default=os.environ.get("MYGOLDMINE_HOME", str(REPO_ROOT)))
    parser.add_argument("--max-bytes", type=int, default=65536)
    args = parser.parse_args()
    rendered = render_mining_repair_context(
        args.root,
        args.project,
        max_bytes=args.max_bytes,
    )
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
