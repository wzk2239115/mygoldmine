"""Policy primitives shared by built-in heuristics and dreamed policies."""

from __future__ import annotations

from ..env import NodeView, Observation
from ..schema import SEVERITY_WEIGHT

HIGH_YIELD_TAGS = (
    "auth",
    "authentication",
    "api-key",
    "control-plane",
    "unauthenticated",
    "config",
    ".env",
    "git",
    "ssrf",
    "deserial",
    "pickle",
    "agent",
    "mcp",
    "default",
)

LOW_YIELD_TAGS = ("documented", "design", "docs", "info")


class BasePolicy:
    name = "base"

    def __init__(self) -> None:
        self.current_rho = 0.5
        self.current_obs: Observation | None = None

    def select(self, obs: Observation) -> list[str]:
        raise NotImplementedError

    def budget_limit(self, obs: Observation) -> int:
        if obs.max_workers <= 1:
            return 1
        if obs.rho <= 0.0:
            return 1
        if obs.rho < 0.5:
            return max(1, obs.max_workers // 2)
        return obs.max_workers

    def pick(self, obs: Observation, key) -> list[str]:
        self.current_rho = obs.rho
        self.current_obs = obs
        ranked = sorted(
            obs.eligible,
            key=lambda node_id: key(obs.nodes[node_id]),
            reverse=True,
        )
        return ranked[: self.budget_limit(obs)]

    def tag_hits(self, view: NodeView) -> int:
        text = " ".join(
            [
                view.label,
                view.scope,
                view.skill,
                view.hypothesis,
                " ".join(view.tags),
            ]
        ).lower()
        return sum(1 for tag in HIGH_YIELD_TAGS if tag in text)

    def low_yield_hits(self, view: NodeView) -> int:
        text = " ".join(
            [
                view.label,
                view.scope,
                view.skill,
                view.hypothesis,
                " ".join(view.tags),
            ]
        ).lower()
        return sum(1 for tag in LOW_YIELD_TAGS if tag in text)

    def kind_rank(self, view: NodeView) -> int:
        return {"stage": 3, "finding": 2, "verification": 1}.get(view.kind, 0)

    def severity_rank(self, view: NodeView) -> float:
        return SEVERITY_WEIGHT.get(
            view.prior_severity, SEVERITY_WEIGHT["unknown"]
        )

    def rank_baseline(self, view: NodeView) -> float:
        return self.kind_rank(view) * 1000.0 - view.index

    def rank_breadth(self, view: NodeView) -> float:
        return self.kind_rank(view) * 100.0 - view.depth * 10.0 - view.index * 0.01

    def rank_depth(self, view: NodeView) -> float:
        return view.depth * 100.0 + self.kind_rank(view) * 10.0 - view.index * 0.01

    def rank_evidence(self, view: NodeView) -> float:
        rho = self.current_rho
        return (1.0 - rho) * self.rank_precision(view) + rho * self.rank_breadth(
            view
        )

    def _rank_cve_core(self, view: NodeView) -> float:
        finding_bonus = 20.0 if view.kind == "finding" else 0.0
        return (
            self.tag_hits(view) * 120.0
            + finding_bonus
            + self.severity_rank(view) * 40.0
            - view.index * 0.01
        )

    def rank_cve(self, view: NodeView) -> float:
        rho = self.current_rho
        return (1.0 - rho) * self.rank_precision(view) + rho * self._rank_cve_core(
            view
        )

    def rank_precision(self, view: NodeView) -> float:
        finding_bonus = 10.0 if view.kind == "finding" else 0.0
        return (
            self.tag_hits(view) * 100.0
            - self.low_yield_hits(view) * 150.0
            + self.severity_rank(view) * 30.0
            + finding_bonus
            - view.index * 0.01
        )
