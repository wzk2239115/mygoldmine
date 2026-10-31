#!/usr/bin/env python3
"""Bound one native Claude process by wall time and actual transcript progress."""

import argparse
import os
import signal
import subprocess
from pathlib import Path

from durable_recovery import atomic_json, now, watch_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--health", required=True)
    parser.add_argument("--idle", type=float, default=180)
    parser.add_argument("--setup-idle", type=float)
    parser.add_argument("--wall", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    setup_idle = args.setup_idle if args.setup_idle is not None else max(args.idle, 900)
    if not command or min(args.idle, setup_idle, args.wall) <= 0:
        parser.error("command and positive budgets required")
    raw = Path(args.raw)
    initial_offset = raw.stat().st_size if raw.exists() else 0
    process = subprocess.Popen(command, start_new_session=True)
    health = Path(args.health)
    phase = "setup"

    def write_health(code, reason, **extra):
        atomic_json(
            health,
            {
                "exit_code": code,
                "phase": phase,
                "reason": reason,
                "ended_at": now(),
                **extra,
            },
        )

    def update_health(state):
        nonlocal phase
        phase = state["phase"]
        extra = {key: value for key, value in state.items() if key not in {"phase", "reason"}}
        write_health(-1, state["reason"], **extra)

    def stop():
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()

    def interrupted(_signal, _frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    try:
        code, reason = watch_process(
            process,
            raw,
            initial_offset=initial_offset,
            idle=args.idle,
            setup_idle=setup_idle,
            timeout=args.wall,
            stop=stop,
            poll=min(1, args.idle / 10),
            status=update_health,
        )
    except KeyboardInterrupt:
        stop()
        code, reason = 130, "interrupted"
    write_health(code, reason)
    if reason in {"setup_timeout", "model_idle_timeout"}:
        return 125
    return 128 - code if code < 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
