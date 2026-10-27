from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "policy_proposer.txt"
)

BASELINE_SOURCE = '''class Policy(BasePolicy):
    name = "baseline"

    def select(self, obs):
        return self.pick(obs, self.rank_baseline)
'''

TEMPLATES = {
    "breadth": '''class Policy(BasePolicy):
    name = "dreamed-breadth"

    def select(self, obs):
        return self.pick(obs, self.rank_breadth)
''',
    "depth": '''class Policy(BasePolicy):
    name = "dreamed-depth"

    def select(self, obs):
        return self.pick(obs, self.rank_depth)
''',
    "evidence": '''class Policy(BasePolicy):
    name = "dreamed-evidence"

    def select(self, obs):
        return self.pick(obs, self.rank_evidence)
''',
    "cve": '''class Policy(BasePolicy):
    name = "dreamed-cve"

    def select(self, obs):
        return self.pick(obs, self.rank_cve)
''',
    "precision": '''class Policy(BasePolicy):
    name = "dreamed-precision"

    def select(self, obs):
        return self.pick(obs, self.rank_precision)
''',
}


@dataclass
class DiscoveryContext:
    version: int
    policy: str
    score: float
    mean_fp_rate: float
    mean_dup_rate: float
    mean_coverage: float
    total_calls: int
    per_world: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    betas: list[float] = field(default_factory=list)
    max_workers: int = 10
    max_rounds: int = 64

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "policy": self.policy,
            "score": round(self.score, 6),
            "mean_fp_rate": round(self.mean_fp_rate, 6),
            "mean_dup_rate": round(self.mean_dup_rate, 6),
            "mean_coverage": round(self.mean_coverage, 6),
            "total_calls": self.total_calls,
            "per_world": self.per_world,
            "history": self.history,
            "betas": self.betas,
            "max_workers": self.max_workers,
            "max_rounds": self.max_rounds,
        }


class PolicyProposer(Protocol):
    def propose(self, context: DiscoveryContext, round_dir: Path) -> str | None:
        ...


class TemplateProposer:
    def propose(self, context: DiscoveryContext, round_dir: Path) -> str | None:
        if context.mean_fp_rate > 0.15:
            return TEMPLATES["precision"]
        if context.mean_coverage < 0.4:
            return TEMPLATES["cve"]
        if context.mean_dup_rate > 0.1:
            return TEMPLATES["evidence"]
        if context.total_calls > 0 and context.mean_coverage > 0.75:
            return TEMPLATES["breadth"]
        return TEMPLATES["evidence"]


def extract_policy_source(text: str) -> str:
    for match in re.finditer(
        r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE
    ):
        body = match.group(1)
        marker = body.find("class Policy")
        if marker != -1:
            return body[marker:].strip() + "\n"
    marker = text.find("class Policy")
    if marker == -1:
        raise ValueError("agent output does not define class Policy")
    return text[marker:].strip() + "\n"


class AgentProposer:
    def __init__(
        self,
        cmd: list[str],
        timeout: int = 1800,
        dry_run: bool = False,
    ) -> None:
        self.cmd = list(cmd)
        self.timeout = timeout
        self.dry_run = dry_run

    def build_prompt(self, context: DiscoveryContext) -> str:
        template = PROMPT_PATH.read_text(encoding="utf-8")
        return template.replace(
            "{context_json}",
            json.dumps(context.to_dict(), ensure_ascii=False, indent=2),
        )

    def propose(self, context: DiscoveryContext, round_dir: Path) -> str | None:
        prompt = self.build_prompt(context)
        round_dir.mkdir(parents=True, exist_ok=True)
        (round_dir / "prompt.md").write_text(prompt, encoding="utf-8")
        if self.dry_run:
            return None
        completed = subprocess.run(
            [*self.cmd, prompt],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        (round_dir / "agent.stdout.log").write_text(
            completed.stdout, encoding="utf-8"
        )
        (round_dir / "agent.stderr.log").write_text(
            completed.stderr, encoding="utf-8"
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"policy proposer exited {completed.returncode}: "
                f"{completed.stderr[-400:]}"
            )
        return extract_policy_source(completed.stdout)
