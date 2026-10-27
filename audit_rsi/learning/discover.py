from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..objective import (
    DEFAULT_BETAS,
    DEFAULT_MAX_ROUNDS,
    PolicyScore,
    evaluate,
)
from ..policy.base import BasePolicy
from ..policy.baseline import BaselinePolicy
from ..policy.loader import PolicyRejected, load_policy_file, load_policy_source
from ..world import TracePool
from .proposer import (
    BASELINE_SOURCE,
    DiscoveryContext,
    PolicyProposer,
    TemplateProposer,
)


@dataclass
class DiscoverVersion:
    version: int
    policy: str
    score: float
    source: str = ""
    error: str = ""
    replay: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoverResult:
    best_policy: str
    best_score: float
    baseline_score: float
    versions: list[DiscoverVersion]
    output_dir: str
    holdout_score: float | None = None
    holdout_policy: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_policy": self.best_policy,
            "best_score": round(self.best_score, 6),
            "baseline_score": round(self.baseline_score, 6),
            "holdout_score": (
                round(self.holdout_score, 6)
                if self.holdout_score is not None
                else None
            ),
            "holdout_policy": self.holdout_policy,
            "output_dir": self.output_dir,
            "versions": [
                {
                    "version": v.version,
                    "policy": v.policy,
                    "score": round(v.score, 6),
                    "error": v.error,
                    "replay": v.replay,
                }
                for v in self.versions
            ],
        }


def _context(
    version: int,
    score: PolicyScore,
    history: list[dict[str, Any]],
    betas: Sequence[float],
    max_workers: int,
    max_rounds: int,
) -> DiscoveryContext:
    return DiscoveryContext(
        version=version,
        policy=score.policy,
        score=score.score,
        mean_fp_rate=score.mean_fp_rate,
        mean_dup_rate=score.mean_dup_rate,
        mean_coverage=score.mean_coverage,
        total_calls=score.total_calls,
        per_world=[r.to_dict() for r in score.per_world],
        history=history,
        betas=list(betas),
        max_workers=max_workers,
        max_rounds=max_rounds,
    )


def _current_factory(
    out_dir: Path,
) -> tuple[type[BasePolicy], str]:
    method = out_dir / "policy" / "method.py"
    if method.exists():
        try:
            return load_policy_file(method), method.read_text(encoding="utf-8")
        except PolicyRejected:
            pass
    return BaselinePolicy, BASELINE_SOURCE


def discover(
    pool: TracePool,
    proposer: PolicyProposer | None = None,
    rounds: int = 3,
    betas: Sequence[float] = DEFAULT_BETAS,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    out_dir: str | Path = "rsi",
    holdout: TracePool | None = None,
) -> DiscoverResult:
    proposer = proposer or TemplateProposer()
    out = Path(out_dir)
    learning = out / "learning"
    policy_dir = out / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    learning.mkdir(parents=True, exist_ok=True)

    current_cls, current_source = _current_factory(out)
    baseline_score = evaluate(
        current_cls,
        pool,
        betas=betas,
        max_workers=max_workers,
        max_rounds=max_rounds,
    )
    best_cls = current_cls
    best_source = current_source
    best_result = baseline_score
    versions: list[DiscoverVersion] = [
        DiscoverVersion(
            version=0,
            policy=baseline_score.policy,
            score=baseline_score.score,
            source=current_source,
            replay=baseline_score.to_dict(),
        )
    ]
    history: list[dict[str, Any]] = [
        {
            "version": 0,
            "policy": baseline_score.policy,
            "score": round(baseline_score.score, 6),
        }
    ]

    for index in range(1, rounds + 1):
        round_dir = learning / f"iter{index:03d}"
        round_dir.mkdir(parents=True, exist_ok=True)
        context = _context(
            index,
            best_result,
            history,
            betas,
            max_workers,
            max_rounds,
        )
        try:
            source = proposer.propose(context, round_dir)
        except Exception as exc:
            versions.append(
                DiscoverVersion(
                    version=index,
                    policy="<proposer-error>",
                    score=0.0,
                    error=str(exc),
                )
            )
            history.append(
                {
                    "version": index,
                    "policy": "<proposer-error>",
                    "score": 0.0,
                    "error": str(exc),
                }
            )
            continue
        if source is None:
            versions.append(
                DiscoverVersion(
                    version=index,
                    policy="<no-proposal>",
                    score=0.0,
                    error="proposer returned no policy",
                )
            )
            break
        (round_dir / "policy.py").write_text(source, encoding="utf-8")
        try:
            candidate_cls = load_policy_source(
                source, filename=str(round_dir / "policy.py")
            )
        except PolicyRejected as exc:
            versions.append(
                DiscoverVersion(
                    version=index,
                    policy="<rejected>",
                    score=0.0,
                    source=source,
                    error=str(exc),
                )
            )
            history.append(
                {
                    "version": index,
                    "policy": "<rejected>",
                    "score": 0.0,
                    "error": str(exc),
                }
            )
            continue

        score = evaluate(
            candidate_cls,
            pool,
            betas=betas,
            max_workers=max_workers,
            max_rounds=max_rounds,
        )
        (round_dir / "replay.json").write_text(
            json.dumps(score.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        version = DiscoverVersion(
            version=index,
            policy=score.policy,
            score=score.score,
            source=source,
            replay=score.to_dict(),
        )
        versions.append(version)
        history.append(
            {
                "version": index,
                "policy": score.policy,
                "score": round(score.score, 6),
                "fp_rate": round(score.mean_fp_rate, 6),
                "coverage": round(score.mean_coverage, 6),
            }
        )
        if score.score > best_result.score + 1e-9:
            best_cls = candidate_cls
            best_source = source
            best_result = score

    (policy_dir / "method.py").write_text(best_source, encoding="utf-8")
    holdout_score = None
    holdout_policy = None
    if holdout is not None and holdout.worlds:
        holdout_result = evaluate(
            best_cls,
            holdout,
            betas=betas,
            max_workers=max_workers,
            max_rounds=max_rounds,
        )
        holdout_score = holdout_result.score
        holdout_policy = holdout_result.policy

    result = DiscoverResult(
        best_policy=getattr(best_cls, "name", best_cls.__name__),
        best_score=best_result.score,
        baseline_score=baseline_score.score,
        versions=versions,
        output_dir=str(out),
        holdout_score=holdout_score,
        holdout_policy=holdout_policy,
    )
    (learning / "discover_summary.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
