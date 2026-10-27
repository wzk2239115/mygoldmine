from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..objective import (
    DEFAULT_BETAS,
    DEFAULT_MAX_ROUNDS,
    PolicyScore,
    evaluate,
)
from ..policy.baseline import BaselinePolicy
from ..policy.heuristics import BUILTIN_POLICIES
from ..policy.loader import load_policy_file
from ..world import TracePool


def policy_factory(name: str, out_dir: str | Path = "rsi"):
    if name in BUILTIN_POLICIES:
        return BUILTIN_POLICIES[name]
    if name in {"method", "learned"}:
        return load_policy_file(Path(out_dir) / "policy" / "method.py")
    raise KeyError(f"unknown policy: {name}")


def replay_named(
    name: str,
    pool: TracePool,
    out_dir: str | Path = "rsi",
    betas: Sequence[float] = DEFAULT_BETAS,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> PolicyScore:
    return evaluate(
        policy_factory(name, out_dir),
        pool,
        betas=betas,
        max_workers=max_workers,
        max_rounds=max_rounds,
    )


def replay_all_builtin(
    pool: TracePool,
    betas: Sequence[float] = DEFAULT_BETAS,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> list[PolicyScore]:
    classes = [BaselinePolicy]
    classes.extend(
        cls for cls in BUILTIN_POLICIES.values() if cls is not BaselinePolicy
    )
    return [
        evaluate(
            cls,
            pool,
            betas=betas,
            max_workers=max_workers,
            max_rounds=max_rounds,
        )
        for cls in classes
    ]
