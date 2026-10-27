"""Shared decision interface for online audit rollout and offline replay."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .schema import Cost, Outcome
from .world import ReplayWorld


@dataclass(frozen=True)
class NodeView:
    id: str
    parent_id: str | None
    kind: str
    label: str
    scope: str
    skill: str
    hypothesis: str
    tags: tuple[str, ...]
    prior_severity: str
    depth: int
    index: int
    cost: Cost
    revealed: bool
    outcome: Outcome | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "kind": self.kind,
            "label": self.label,
            "scope": self.scope,
            "skill": self.skill,
            "hypothesis": self.hypothesis,
            "tags": list(self.tags),
            "prior_severity": self.prior_severity,
            "depth": self.depth,
            "index": self.index,
            "cost": self.cost.to_dict(),
            "revealed": self.revealed,
            "outcome": self.outcome.to_dict() if self.outcome else None,
        }


@dataclass
class Observation:
    world_id: str
    rho: float
    rounds: int
    eligible: tuple[str, ...]
    nodes: dict[str, NodeView]
    spent: Cost
    best_score: float
    done: bool
    max_workers: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "rho": self.rho,
            "rounds": self.rounds,
            "eligible": list(self.eligible),
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "spent": self.spent.to_dict(),
            "best_score": round(self.best_score, 6),
            "done": self.done,
            "max_workers": self.max_workers,
        }


class TraceEnv:
    """Progressive-disclosure replay over a recorded discovery tree.

    A candidate node is visible once its parent has been revealed, but its
    recorded outcome stays hidden until the policy spends a call on it.
    """

    def __init__(
        self,
        world: ReplayWorld,
        rho: float = 0.5,
        max_workers: int = 10,
        max_rounds: int = 10_000,
    ) -> None:
        self.world = world
        self.tree = world.tree
        self.rho = float(rho)
        self.max_workers = max(1, int(max_workers))
        self.max_rounds = max(1, int(max_rounds))
        self.revealed: set[str] = set()
        self.rounds = 0
        self.spent = Cost(agent_calls=0, seconds=0.0, tokens=0)
        self.done = False

    def reset(self) -> Observation:
        if self.tree.root_id not in self.tree.nodes:
            raise ValueError(f"world {self.world.world_id} has no root")
        self.revealed = {self.tree.root_id}
        self.rounds = 0
        self.spent = Cost(agent_calls=0, seconds=0.0, tokens=0)
        self.done = False
        return self.observe()

    def frontier(self) -> list[str]:
        candidates: list[str] = []
        for node_id in self.tree.order:
            if node_id not in self.revealed:
                continue
            for child in self.tree.nodes[node_id].children:
                if child not in self.revealed:
                    candidates.append(child)
        return candidates

    def best_score(self) -> float:
        scores = [
            self.tree.nodes[nid].score()
            for nid in self.revealed
            if self.tree.nodes[nid].kind != "root"
        ]
        return max(scores, default=0.0)

    def observe(self) -> Observation:
        eligible = self.frontier()
        if not eligible or self.rounds >= self.max_rounds:
            self.done = True
        visible: dict[str, NodeView] = {}
        for node_id in self.tree.order:
            if node_id not in self.revealed and node_id not in eligible:
                continue
            visible[node_id] = self._view(node_id, node_id in self.revealed)
        return Observation(
            world_id=self.world.world_id,
            rho=self.rho,
            rounds=self.rounds,
            eligible=tuple(eligible),
            nodes=visible,
            spent=Cost(
                self.spent.agent_calls,
                self.spent.seconds,
                self.spent.tokens,
            ),
            best_score=self.best_score(),
            done=self.done,
            max_workers=self.max_workers,
        )

    def step(self, batch: list[str] | tuple[str, ...]) -> Observation:
        if self.done:
            return self.observe()
        eligible = set(self.frontier())
        selected: list[str] = []
        seen: set[str] = set()
        for node_id in batch:
            if node_id in seen or node_id not in eligible:
                continue
            selected.append(node_id)
            seen.add(node_id)
            if len(selected) >= self.max_workers:
                break
        if not selected:
            self.done = True
            return self.observe()
        for node_id in selected:
            node = self.tree.nodes[node_id]
            self.revealed.add(node_id)
            self.spent.add(node.cost)
        self.rounds += 1
        return self.observe()

    def revealed_nodes(self) -> list[str]:
        return [
            nid
            for nid in self.tree.order
            if nid in self.revealed and self.tree.nodes[nid].kind != "root"
        ]

    def _view(self, node_id: str, revealed: bool) -> NodeView:
        node = self.tree.nodes[node_id]
        outcome = copy.deepcopy(node.outcome) if revealed else None
        return NodeView(
            id=node.id,
            parent_id=node.parent_id,
            kind=node.kind,
            label=node.label,
            scope=node.scope,
            skill=node.skill,
            hypothesis=node.hypothesis,
            tags=tuple(node.tags),
            prior_severity=node.prior_severity,
            depth=self.tree.depth(node_id),
            index=self.tree.index(node_id),
            cost=copy.deepcopy(node.cost),
            revealed=revealed,
            outcome=outcome,
        )
