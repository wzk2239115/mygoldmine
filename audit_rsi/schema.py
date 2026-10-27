"""Discovery-tree primitives shared by online rollout and offline replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SEVERITY_WEIGHT = {
    "critical": 1.0,
    "high": 0.7,
    "medium": 0.45,
    "low": 0.2,
    "info": 0.05,
    "unknown": 0.1,
}

VERDICT_WEIGHT = {
    "tp": 1.0,
    "unclear": 0.3,
    "unverified": 0.12,
    "design": 0.05,
    "duplicate": -0.25,
    "fp": -0.5,
}

CONFIDENCE_WEIGHT = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.45,
    "unknown": 0.45,
}

JUDGED_VERDICTS = frozenset({"tp", "fp", "duplicate", "design", "unclear"})


@dataclass
class Cost:
    agent_calls: int = 1
    seconds: float = 0.0
    tokens: int = 0

    def add(self, other: "Cost") -> None:
        self.agent_calls += other.agent_calls
        self.seconds += other.seconds
        self.tokens += other.tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_calls": self.agent_calls,
            "seconds": round(self.seconds, 3),
            "tokens": self.tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Cost":
        data = data or {}
        return cls(
            agent_calls=int(data.get("agent_calls", 1)),
            seconds=float(data.get("seconds", 0.0)),
            tokens=int(data.get("tokens", 0)),
        )


@dataclass
class Outcome:
    verdict: str = "unverified"
    severity: str = "unknown"
    confidence: str = "unknown"
    cve_tier: int | None = None
    known_cve: str = ""
    source: str = ""
    note: str = ""

    def novelty(self) -> float:
        if self.known_cve:
            return 0.0
        if self.cve_tier == 1:
            return 1.0
        if self.cve_tier == 2:
            return 0.8
        if self.verdict in {"tp", "unclear"}:
            return 0.6
        if self.verdict == "unverified":
            return 0.3
        return 0.0

    def score(self) -> float:
        base = SEVERITY_WEIGHT.get(self.severity, SEVERITY_WEIGHT["unknown"])
        base *= CONFIDENCE_WEIGHT.get(
            self.confidence, CONFIDENCE_WEIGHT["unknown"]
        )
        weight = VERDICT_WEIGHT.get(self.verdict, VERDICT_WEIGHT["unverified"])
        if weight < 0:
            return weight * max(base, 0.2)
        if self.verdict in {"tp", "unclear", "unverified"}:
            return base * weight * self.novelty()
        return base * weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "severity": self.severity,
            "confidence": self.confidence,
            "cve_tier": self.cve_tier,
            "known_cve": self.known_cve,
            "source": self.source,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Outcome":
        data = data or {}
        tier = data.get("cve_tier")
        return cls(
            verdict=str(data.get("verdict", "unverified")),
            severity=str(data.get("severity", "unknown")),
            confidence=str(data.get("confidence", "unknown")),
            cve_tier=int(tier) if tier is not None else None,
            known_cve=str(data.get("known_cve", "")),
            source=str(data.get("source", "")),
            note=str(data.get("note", "")),
        )


@dataclass
class Node:
    id: str
    parent_id: str | None
    kind: str
    label: str
    scope: str = ""
    skill: str = ""
    hypothesis: str = ""
    tags: list[str] = field(default_factory=list)
    prior_severity: str = "unknown"
    observation: dict[str, Any] = field(default_factory=dict)
    outcome: Outcome = field(default_factory=Outcome)
    cost: Cost = field(default_factory=Cost)
    children: list[str] = field(default_factory=list)

    def score(self) -> float:
        if self.kind in {"root", "stage"}:
            return 0.0
        return self.outcome.score()

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
            "observation": self.observation,
            "outcome": self.outcome.to_dict(),
            "cost": self.cost.to_dict(),
            "children": list(self.children),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        return cls(
            id=str(data["id"]),
            parent_id=data.get("parent_id"),
            kind=str(data.get("kind", "finding")),
            label=str(data.get("label", "")),
            scope=str(data.get("scope", "")),
            skill=str(data.get("skill", "")),
            hypothesis=str(data.get("hypothesis", "")),
            tags=[str(t) for t in data.get("tags", [])],
            prior_severity=str(data.get("prior_severity", "unknown")),
            observation=dict(data.get("observation", {})),
            outcome=Outcome.from_dict(data.get("outcome")),
            cost=Cost.from_dict(data.get("cost")),
            children=[str(c) for c in data.get("children", [])],
        )


@dataclass
class DiscoveryTree:
    root_id: str
    nodes: dict[str, Node] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)

    def add(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        self.nodes[node.id] = node
        self.order.append(node.id)
        if node.parent_id is not None:
            parent = self.nodes.get(node.parent_id)
            if parent is None:
                raise ValueError(
                    f"parent {node.parent_id} missing for node {node.id}"
                )
            parent.children.append(node.id)

    def children(self, node_id: str) -> list[str]:
        node = self.nodes.get(node_id)
        return list(node.children) if node else []

    def leaves(self) -> list[str]:
        return [nid for nid in self.order if not self.nodes[nid].children]

    def depth(self, node_id: str) -> int:
        depth = 0
        cursor = self.nodes.get(node_id)
        seen: set[str] = set()
        while cursor is not None and cursor.parent_id is not None:
            if cursor.id in seen:
                raise ValueError(f"cycle at {cursor.id}")
            seen.add(cursor.id)
            cursor = self.nodes.get(cursor.parent_id)
            depth += 1
        return depth

    def index(self, node_id: str) -> int:
        return self.order.index(node_id)

    def best_score(self) -> float:
        return max((n.score() for n in self.nodes.values()), default=0.0)

    def total_calls(self) -> int:
        return sum(n.cost.agent_calls for n in self.nodes.values() if n.kind != "root")

    def skills(self) -> set[str]:
        return {n.skill for n in self.nodes.values() if n.skill}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "order": list(self.order),
            "nodes": [self.nodes[nid].to_dict() for nid in self.order],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DiscoveryTree":
        tree = cls(root_id=str(data["root_id"]))
        for raw in data.get("nodes", []):
            node = Node.from_dict(raw)
            tree.nodes[node.id] = node
            tree.order.append(node.id)
        return tree

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.root_id not in self.nodes:
            errors.append(f"root missing: {self.root_id}")
        for nid in self.order:
            node = self.nodes[nid]
            if node.parent_id is None and nid != self.root_id:
                errors.append(f"orphan node: {nid}")
            if node.parent_id is not None and node.parent_id not in self.nodes:
                errors.append(f"missing parent {node.parent_id} for {nid}")
        for nid in self.order:
            for child in self.nodes[nid].children:
                if child not in self.nodes:
                    errors.append(f"missing child {child} of {nid}")
        return errors


def outcome_from_lookup(
    project: str,
    finding_id: str,
    finding: dict[str, Any],
    curated: dict[str, Any],
    handoff: dict[tuple[str, str], dict[str, Any]],
    verify: dict[str, Any],
) -> Outcome:
    verdict = "unverified"
    severity = str(finding.get("severity", "unknown")).lower()
    confidence = str(finding.get("confidence", "unknown")).lower()
    cve_tier: int | None = None
    known_cve = ""
    sources: list[str] = []
    note = ""

    handoff_entry = handoff.get((project, finding_id))
    if handoff_entry:
        tier = handoff_entry.get("tier")
        cve_tier = int(tier) if tier is not None else None
        note = str(handoff_entry.get("known_overlap", ""))
        sources.append("handoff")

    curated_entry = curated.get(f"{project}:{finding_id}")
    if curated_entry:
        verdict = str(curated_entry.get("verdict", "unverified")).lower()
        if "cveTier" in curated_entry:
            tier = curated_entry.get("cveTier")
            cve_tier = int(tier) if tier is not None else None
        known_cve = str(curated_entry.get("knownCve", "") or "")
        if curated_entry.get("note"):
            note = str(curated_entry["note"])
        sources.append("curated")
    elif finding_id in verify:
        raw = str(verify[finding_id].get("verdict", "")).lower()
        verdict = {
            "confirmed": "tp",
            "rejected": "fp",
            "inconclusive": "unclear",
        }.get(raw, "unverified")
        note = str(verify[finding_id].get("reason", ""))
        sources.append("verify")

    if verdict == "unverified":
        final_note = str(finding.get("final_review_note", "")).lower()
        if "false positive" in final_note or "误报" in final_note:
            verdict = "fp"
            sources.append("final_review")

    if verdict == "unverified" and finding_id in verify:
        raw = str(verify[finding_id].get("verdict", "")).lower()
        verdict = {
            "confirmed": "tp",
            "rejected": "fp",
            "inconclusive": "unclear",
        }.get(raw, "unverified")
        sources.append("verify")

    return Outcome(
        verdict=verdict,
        severity=severity,
        confidence=confidence,
        cve_tier=cve_tier,
        known_cve=known_cve,
        source="+".join(dict.fromkeys(sources)),
        note=note,
    )
