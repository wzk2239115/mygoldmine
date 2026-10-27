"""Replay worlds and the accumulated simulator pool."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import DiscoveryTree


@dataclass
class ReplayWorld:
    world_id: str
    project: str
    commit: str
    tree: DiscoveryTree
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def best_score(self) -> float:
        return self.tree.best_score()

    @property
    def total_calls(self) -> int:
        return self.tree.total_calls()

    @property
    def skills(self) -> set[str]:
        return self.tree.skills()

    def summary(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "project": self.project,
            "commit": self.commit,
            "nodes": len(self.tree.nodes),
            "total_calls": self.total_calls,
            "best_score": round(self.best_score, 6),
            "skills": sorted(self.skills),
            "meta": self.meta,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "project": self.project,
            "commit": self.commit,
            "meta": self.meta,
            "tree": self.tree.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReplayWorld":
        return cls(
            world_id=str(data["world_id"]),
            project=str(data.get("project", "")),
            commit=str(data.get("commit", "")),
            tree=DiscoveryTree.from_dict(data["tree"]),
            meta=dict(data.get("meta", {})),
        )

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return target

    @classmethod
    def load(cls, path: str | Path) -> "ReplayWorld":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class TracePool:
    worlds: list[ReplayWorld] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def by_id(self, world_id: str) -> ReplayWorld:
        for world in self.worlds:
            if world.world_id == world_id:
                return world
        raise KeyError(world_id)

    def ids(self) -> list[str]:
        return [w.world_id for w in self.worlds]

    def subset(self, ids: list[str] | set[str] | None) -> "TracePool":
        if ids is None:
            return TracePool(list(self.worlds), dict(self.meta))
        wanted = set(ids)
        return TracePool(
            [w for w in self.worlds if w.world_id in wanted], dict(self.meta)
        )

    def exclude(self, ids: list[str] | set[str]) -> "TracePool":
        drop = set(ids)
        return TracePool(
            [w for w in self.worlds if w.world_id not in drop], dict(self.meta)
        )

    def summary(self) -> dict[str, Any]:
        return {
            "worlds": len(self.worlds),
            "projects": sorted({w.project for w in self.worlds}),
            "total_calls": sum(w.total_calls for w in self.worlds),
            "best_scores": {
                w.world_id: round(w.best_score, 6) for w in self.worlds
            },
            "meta": self.meta,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "worlds": [w.to_dict() for w in self.worlds],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TracePool":
        return cls(
            worlds=[ReplayWorld.from_dict(w) for w in data.get("worlds", [])],
            meta=dict(data.get("meta", {})),
        )

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return target

    @classmethod
    def load(cls, path: str | Path) -> "TracePool":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
