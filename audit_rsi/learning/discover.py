from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..evaluation import compare
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
    status: str = "evaluated"
    holdout_score: float | None = None
    gate: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoverResult:
    best_policy: str
    best_score: float
    baseline_score: float
    versions: list[DiscoverVersion]
    output_dir: str
    holdout_score: float | None = None
    holdout_policy: str | None = None
    baseline_holdout_score: float | None = None
    validation_status: str = "unvalidated"
    method_status: str = "unchanged"
    gate_status: str = "insufficient"
    gate_reasons: list[str] = field(default_factory=list)
    shadow_policy: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_policy": self.best_policy,
            "best_score": round(self.best_score, 6),
            "baseline_score": round(self.baseline_score, 6),
            "holdout_score": (
                round(self.holdout_score, 6) if self.holdout_score is not None else None
            ),
            "holdout_policy": self.holdout_policy,
            "baseline_holdout_score": (
                round(self.baseline_holdout_score, 6)
                if self.baseline_holdout_score is not None
                else None
            ),
            "validation_status": self.validation_status,
            "method_status": self.method_status,
            "gate_status": self.gate_status,
            "gate_reasons": list(self.gate_reasons),
            "shadow_policy": self.shadow_policy,
            "output_dir": self.output_dir,
            "versions": [
                {
                    "version": v.version,
                    "policy": v.policy,
                    "score": round(v.score, 6),
                    "status": v.status,
                    "holdout_score": (
                        round(v.holdout_score, 6) if v.holdout_score is not None else None
                    ),
                    "error": v.error,
                    "gate": v.gate,
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
    min_label_coverage: float = 0.5,
    min_projects: int = 1,
    min_support: int = 1,
    bootstrap: int = 1000,
    seed: int = 0,
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
    has_holdout = holdout is not None and bool(holdout.worlds)
    best_holdout_result = None
    if has_holdout:
        best_holdout_result = evaluate(
            current_cls,
            holdout,
            betas=betas,
            max_workers=max_workers,
            max_rounds=max_rounds,
        )
        (learning / "baseline_holdout.json").write_text(
            json.dumps(best_holdout_result.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    best_cls = current_cls
    best_source = current_source
    best_result = baseline_score
    latest_gate: dict[str, Any] = {}
    versions: list[DiscoverVersion] = [
        DiscoverVersion(
            version=0,
            policy=baseline_score.policy,
            score=baseline_score.score,
            source=current_source,
            replay=baseline_score.to_dict(),
            status="baseline",
            holdout_score=(best_holdout_result.score if best_holdout_result else None),
        )
    ]
    history: list[dict[str, Any]] = [
        {
            "version": 0,
            "policy": baseline_score.policy,
            "score": round(baseline_score.score, 6),
            "status": "baseline",
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
                    status="error",
                )
            )
            history.append(
                {
                    "version": index,
                    "policy": "<proposer-error>",
                    "score": 0.0,
                    "status": "error",
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
                    status="empty",
                )
            )
            break
        (round_dir / "policy.py").write_text(source, encoding="utf-8")
        try:
            candidate_cls = load_policy_source(source, filename=str(round_dir / "policy.py"))
        except PolicyRejected as exc:
            versions.append(
                DiscoverVersion(
                    version=index,
                    policy="<rejected>",
                    score=0.0,
                    source=source,
                    error=str(exc),
                    status="rejected",
                )
            )
            history.append(
                {
                    "version": index,
                    "policy": "<rejected>",
                    "score": 0.0,
                    "status": "rejected",
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
        if score.score > best_result.score + 1e-9:
            if best_holdout_result is not None:
                candidate_holdout = evaluate(
                    candidate_cls,
                    holdout,
                    betas=betas,
                    max_workers=max_workers,
                    max_rounds=max_rounds,
                )
                version.holdout_score = candidate_holdout.score
                (round_dir / "holdout.json").write_text(
                    json.dumps(candidate_holdout.to_dict(), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                gate = compare(
                    candidate_holdout,
                    best_holdout_result,
                    pool=holdout,
                    min_label_coverage=min_label_coverage,
                    min_projects=min_projects,
                    min_support=min_support,
                    n_bootstrap=bootstrap,
                    seed=seed,
                )
                version.gate = gate
                latest_gate = gate
                (round_dir / "gate.json").write_text(
                    json.dumps(gate, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                regressed = not gate["no_regression"]
                if gate["accepted"]:
                    version.status = "accepted"
                    best_cls = candidate_cls
                    best_source = source
                    best_result = score
                    best_holdout_result = candidate_holdout
                else:
                    version.status = "rejected" if regressed else "insufficient"
                    if regressed:
                        version.error = (
                            "holdout regression: "
                            f"candidate={candidate_holdout.score:.6f} "
                            f"baseline={best_holdout_result.score:.6f}; "
                            f"reasons={','.join(gate['reasons'])}"
                        )
                    else:
                        version.error = "holdout gate insufficient: " + ",".join(gate["reasons"])
            else:
                version.status = "shadow"
                version.error = "holdout missing: candidate retained as shadow"
                version.gate = {
                    "status": "insufficient",
                    "accepted": False,
                    "reasons": ["holdout_missing"],
                }
                latest_gate = version.gate
                best_cls = candidate_cls
                best_source = source
                best_result = score
        versions.append(version)
        history.append(
            {
                "version": index,
                "policy": score.policy,
                "score": round(score.score, 6),
                "status": version.status,
                "holdout_score": version.holdout_score,
                "fp_rate": (
                    round(score.mean_fp_rate, 6) if score.mean_fp_rate is not None else None
                ),
                "coverage": round(score.mean_coverage, 6),
                "error": version.error,
                "gate_reasons": version.gate.get("reasons", []),
            }
        )

    promoted = has_holdout and best_source != current_source
    method = policy_dir / "method.py"
    if promoted:
        method.write_text(best_source, encoding="utf-8")
    shadow_policy = None
    if not has_holdout and best_source != current_source:
        shadow = policy_dir / "shadow.py"
        shadow.write_text(best_source, encoding="utf-8")
        shadow_policy = str(shadow)
    if promoted:
        method_status = "promoted"
        gate_status = "accepted"
        gate_reasons: list[str] = []
    elif has_holdout:
        method_status = "unchanged"
        gate_status = latest_gate.get("status", "insufficient")
        gate_reasons = latest_gate.get("reasons", ["no_accepted_candidate"])
    else:
        method_status = "shadow" if shadow_policy else "unvalidated"
        gate_status = "insufficient"
        gate_reasons = ["holdout_missing"]
    result = DiscoverResult(
        best_policy=getattr(best_cls, "name", best_cls.__name__),
        best_score=best_result.score,
        baseline_score=baseline_score.score,
        versions=versions,
        output_dir=str(out),
        holdout_score=(best_holdout_result.score if best_holdout_result else None),
        holdout_policy=(best_holdout_result.policy if best_holdout_result else None),
        baseline_holdout_score=(versions[0].holdout_score if has_holdout else None),
        validation_status="validated" if has_holdout else "unvalidated",
        method_status=method_status,
        gate_status=gate_status,
        gate_reasons=gate_reasons,
        shadow_policy=shadow_policy,
    )
    (learning / "discover_summary.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
