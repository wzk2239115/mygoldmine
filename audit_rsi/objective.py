"""Security-adapted replay objective (Dream-RSI Eq. 1 plus precision terms)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .env import TraceEnv
from .policy.base import BasePolicy
from .schema import JUDGED_VERDICTS
from .world import ReplayWorld, TracePool

DEFAULT_BETAS = (0.0, 0.25, 0.5, 0.75, 1.0)
DEFAULT_LAMBDA = 0.05
DEFAULT_MU = 0.5
DEFAULT_NU = 0.25
DEFAULT_DELTA = 0.05
DEFAULT_MAX_ROUNDS = 64

PolicyFactory = Callable[[], BasePolicy]


@dataclass
class Point:
    rho: float
    calls: int
    quality: float
    rounds: int
    fp_rate: float
    dup_rate: float
    coverage: float
    best_score: float
    revealed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "rho": self.rho,
            "calls": self.calls,
            "quality": round(self.quality, 6),
            "rounds": self.rounds,
            "fp_rate": round(self.fp_rate, 6),
            "dup_rate": round(self.dup_rate, 6),
            "coverage": round(self.coverage, 6),
            "best_score": round(self.best_score, 6),
            "revealed": self.revealed,
        }


@dataclass
class WorldReplay:
    world_id: str
    project: str
    points: list[Point]
    hypervolume: float
    parallel_penalty: float
    fp_rate: float
    dup_rate: float
    coverage: float
    score: float
    revealed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "project": self.project,
            "points": [p.to_dict() for p in self.points],
            "hypervolume": round(self.hypervolume, 6),
            "parallel_penalty": round(self.parallel_penalty, 6),
            "fp_rate": round(self.fp_rate, 6),
            "dup_rate": round(self.dup_rate, 6),
            "coverage": round(self.coverage, 6),
            "score": round(self.score, 6),
            "revealed": list(self.revealed),
        }


@dataclass
class PolicyScore:
    policy: str
    score: float
    per_world: list[WorldReplay]

    @property
    def mean_fp_rate(self) -> float:
        return _mean(r.fp_rate for r in self.per_world)

    @property
    def mean_dup_rate(self) -> float:
        return _mean(r.dup_rate for r in self.per_world)

    @property
    def mean_coverage(self) -> float:
        return _mean(r.coverage for r in self.per_world)

    @property
    def total_calls(self) -> int:
        return sum(p.calls for r in self.per_world for p in r.points)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "score": round(self.score, 6),
            "mean_fp_rate": round(self.mean_fp_rate, 6),
            "mean_dup_rate": round(self.mean_dup_rate, 6),
            "mean_coverage": round(self.mean_coverage, 6),
            "total_calls": self.total_calls,
            "per_world": [r.to_dict() for r in self.per_world],
        }


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _instantiate(factory: PolicyFactory | type[BasePolicy]) -> BasePolicy:
    return factory()


def policy_label(factory: PolicyFactory | type[BasePolicy]) -> str:
    if isinstance(factory, type):
        return getattr(factory, "name", factory.__name__)
    instance = factory()
    return getattr(instance, "name", type(instance).__name__)


def playthrough(
    policy: BasePolicy,
    world: ReplayWorld,
    rho: float,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> Point:
    env = TraceEnv(
        world,
        rho=rho,
        max_workers=max_workers,
        max_rounds=max_rounds,
    )
    obs = env.reset()
    while not obs.done:
        batch = policy.select(obs)
        if not batch:
            break
        obs = env.step(batch)

    revealed = env.revealed_nodes()
    judged = [
        world.tree.nodes[nid]
        for nid in revealed
        if world.tree.nodes[nid].outcome.verdict in JUDGED_VERDICTS
    ]
    fp = sum(1 for n in judged if n.outcome.verdict == "fp")
    dup = sum(1 for n in judged if n.outcome.verdict == "duplicate")
    fp_rate = fp / len(judged) if judged else 0.0
    dup_rate = dup / len(judged) if judged else 0.0

    skills = {world.tree.nodes[nid].skill for nid in revealed}
    skills.discard("")
    world_skills = world.skills
    coverage = len(skills & world_skills) / len(world_skills) if world_skills else 0.0

    best = env.best_score()
    quality = 0.0
    if world.best_score > 0:
        quality = max(0.0, min(1.0, best / world.best_score))

    return Point(
        rho=rho,
        calls=env.spent.agent_calls,
        quality=quality,
        rounds=env.rounds,
        fp_rate=fp_rate,
        dup_rate=dup_rate,
        coverage=coverage,
        best_score=best,
        revealed=len(revealed),
    )


def hypervolume(points: Sequence[tuple[int, float]], budget: int) -> float:
    if not points or budget <= 0:
        return 0.0
    nondominated: list[tuple[int, float]] = []
    for calls, quality in points:
        dominated = any(
            other_calls <= calls
            and other_quality >= quality
            and (other_calls < calls or other_quality > quality)
            for other_calls, other_quality in points
        )
        if not dominated:
            nondominated.append((calls, quality))
    nondominated.sort()
    deduped: list[tuple[int, float]] = []
    for calls, quality in nondominated:
        if deduped and calls == deduped[-1][0]:
            deduped[-1] = (calls, max(quality, deduped[-1][1]))
        else:
            deduped.append((calls, quality))
    area = 0.0
    previous = 0.0
    for calls, quality in deduped:
        if quality > previous:
            area += (quality - previous) * max(0, budget - calls)
            previous = quality
    return area / budget


def replay_world(
    factory: PolicyFactory | type[BasePolicy],
    world: ReplayWorld,
    betas: Sequence[float] = DEFAULT_BETAS,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    lambda_parallel: float = DEFAULT_LAMBDA,
    mu_fp: float = DEFAULT_MU,
    nu_dup: float = DEFAULT_NU,
    delta_coverage: float = DEFAULT_DELTA,
) -> WorldReplay:
    points: list[Point] = []
    for rho in betas:
        policy = _instantiate(factory)
        points.append(
            playthrough(
                policy,
                world,
                rho=rho,
                max_workers=max_workers,
                max_rounds=max_rounds,
            )
        )
    hv = hypervolume(
        [(p.calls, p.quality) for p in points], world.total_calls
    )
    parallel = _mean(
        p.rounds / p.calls for p in points if p.calls > 0
    )
    fp_rate = _mean(p.fp_rate for p in points)
    dup_rate = _mean(p.dup_rate for p in points)
    coverage = _mean(p.coverage for p in points)
    score = (
        hv
        - lambda_parallel * parallel
        - mu_fp * fp_rate
        - nu_dup * dup_rate
        + delta_coverage * coverage
    )
    last_env_nodes = _revealed_from_last_run(
        factory, world, betas[-1], max_workers, max_rounds
    )
    return WorldReplay(
        world_id=world.world_id,
        project=world.project,
        points=points,
        hypervolume=hv,
        parallel_penalty=parallel,
        fp_rate=fp_rate,
        dup_rate=dup_rate,
        coverage=coverage,
        score=score,
        revealed=last_env_nodes,
    )


def _revealed_from_last_run(
    factory: PolicyFactory | type[BasePolicy],
    world: ReplayWorld,
    rho: float,
    max_workers: int,
    max_rounds: int,
) -> list[str]:
    env = TraceEnv(world, rho=rho, max_workers=max_workers, max_rounds=max_rounds)
    policy = _instantiate(factory)
    obs = env.reset()
    while not obs.done:
        batch = policy.select(obs)
        if not batch:
            break
        obs = env.step(batch)
    return env.revealed_nodes()


def evaluate(
    factory: PolicyFactory | type[BasePolicy],
    pool: TracePool,
    betas: Sequence[float] = DEFAULT_BETAS,
    max_workers: int = 10,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    lambda_parallel: float = DEFAULT_LAMBDA,
    mu_fp: float = DEFAULT_MU,
    nu_dup: float = DEFAULT_NU,
    delta_coverage: float = DEFAULT_DELTA,
) -> PolicyScore:
    per_world = [
        replay_world(
            factory,
            world,
            betas=betas,
            max_workers=max_workers,
            max_rounds=max_rounds,
            lambda_parallel=lambda_parallel,
            mu_fp=mu_fp,
            nu_dup=nu_dup,
            delta_coverage=delta_coverage,
        )
        for world in pool.worlds
    ]
    score = _mean(r.score for r in per_world)
    return PolicyScore(
        policy=policy_label(factory),
        score=score,
        per_world=per_world,
    )
