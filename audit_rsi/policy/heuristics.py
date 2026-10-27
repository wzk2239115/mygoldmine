from __future__ import annotations

from ..env import Observation
from .base import BasePolicy
from .baseline import BaselinePolicy


class BreadthFirstPolicy(BasePolicy):
    name = "breadth"

    def select(self, obs: Observation) -> list[str]:
        return self.pick(obs, self.rank_breadth)


class DepthFirstPolicy(BasePolicy):
    name = "depth"

    def select(self, obs: Observation) -> list[str]:
        return self.pick(obs, self.rank_depth)


class EvidenceFirstPolicy(BasePolicy):
    name = "evidence"

    def select(self, obs: Observation) -> list[str]:
        return self.pick(obs, self.rank_evidence)


class CVEFirstPolicy(BasePolicy):
    name = "cve"

    def select(self, obs: Observation) -> list[str]:
        return self.pick(obs, self.rank_cve)


class PrecisionFirstPolicy(BasePolicy):
    name = "precision"

    def select(self, obs: Observation) -> list[str]:
        return self.pick(obs, self.rank_precision)


BUILTIN_POLICIES = {
    "baseline": BaselinePolicy,
    "breadth": BreadthFirstPolicy,
    "depth": DepthFirstPolicy,
    "evidence": EvidenceFirstPolicy,
    "cve": CVEFirstPolicy,
    "precision": PrecisionFirstPolicy,
}
