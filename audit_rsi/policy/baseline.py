from __future__ import annotations

from ..env import Observation
from .base import BasePolicy


class BaselinePolicy(BasePolicy):
    name = "baseline"

    def select(self, obs: Observation) -> list[str]:
        return self.pick(obs, self.rank_baseline)
