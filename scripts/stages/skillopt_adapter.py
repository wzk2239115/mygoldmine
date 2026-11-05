#!/usr/bin/env python3
"""把第 08 阶段的改进请求交给 SkillOpt，并转换为现有技能候选。"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "stages"))
from claude_connection import claude_connection  # noqa: E402
from skill_bank import STAGES, SkillBank, identifier, now, read, write  # noqa: E402

DEFAULT_MODEL = "360-proxy/deepseek/deepseek-v4.1-flash"
SKILLOPT_ENTRY = "skillopt.optimizer.rewrite.rewrite_skill_from_suggestions"
FORBIDDEN = (
    re.compile(r"FLAG\{[0-9a-fA-F]{8,}\}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def skillopt_root(repo: Path) -> Path:
    return Path(os.environ.get("SKILLOPT_ROOT") or repo / "third_party/SkillOpt").resolve()


def skillopt_metadata(repo: Path) -> dict[str, Any]:
    root = skillopt_root(repo)
    pin = read(repo / "third_party/SkillOpt.pin.json", {}) or {}
    commit = pin.get("commit", "")
    if not commit:
        try:
            commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10, check=False,
            ).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            commit = ""
    version = pin.get("version", "")
    if not version:
        try:
            text = (root / "pyproject.toml").read_text(encoding="utf-8")
            match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            version = match.group(1) if match else ""
        except OSError:
            version = ""
    return {"root": str(root), "commit": commit, "version": version, "entry": SKILLOPT_ENTRY}


def _configure_skillopt(model: str | None) -> str:
    selected = model or os.environ.get("RSI_LEARNER_MODEL") or DEFAULT_MODEL
    model_name, env = claude_connection(selected)
    os.environ.update(env)
    os.environ.update({
        "OPTIMIZER_BACKEND": "claude_chat",
        "OPTIMIZER_DEPLOYMENT": model_name,
        "CLAUDE_CLI_BIN": os.environ.get("CLAUDE_BIN", "claude"),
        "CLAUDE_PERMISSION_MODE": "dontAsk",
        "CLAUDE_SETTING_SOURCES": "project,local",
    })
    return model_name


def _rewrite_function(repo: Path, model: str | None):
    root = skillopt_root(repo)
    if not (root / "skillopt/optimizer/rewrite.py").is_file():
        raise FileNotFoundError(f"SkillOpt 源码不完整：{root}")
    model_name = _configure_skillopt(model)
    pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(root) + (os.pathsep + pythonpath if pythonpath else "")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from skillopt.optimizer.rewrite import rewrite_skill_from_suggestions
    return rewrite_skill_from_suggestions, model_name


def _suggestions(request: Mapping[str, Any]) -> list[dict[str, str]]:
    result = []
    for item in request.get("suggestions", []):
        if not isinstance(item, Mapping):
            continue
        instruction = str(item.get("instruction") or "").strip()
        if not instruction:
            continue
        result.append({
            "type": str(item.get("type") or "add"),
            "title": str(item.get("title") or "阶段技能改进")[:120],
            "instruction": instruction[:2000],
        })
    return result[:4]


def _clean_skill(text: Any) -> str:
    value = str(text or "").strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 2:
            value = "\n".join(lines[1:-1]).strip()
    if not value:
        raise ValueError("SkillOpt 没有返回技能正文")
    if len(value) > 12000:
        raise ValueError("SkillOpt 返回的技能正文超过 12000 字符")
    if any(pattern.search(value) for pattern in FORBIDDEN):
        raise ValueError("SkillOpt 返回内容包含随机标记或私钥，拒绝写入技能")
    return value + "\n"


def optimize_request(
    request_path: str | Path,
    *,
    repo: str | Path = ROOT,
    project: str = "",
    model: str | None = None,
    rewrite: Callable[..., dict | None] | None = None,
) -> dict[str, Any]:
    repo = Path(repo).resolve()
    os.environ["SKILLOPT_RUN"] = "1"
    request_path = Path(request_path).resolve()
    request = read(request_path, {})
    if not request:
        raise ValueError(f"无法读取改进请求：{request_path}")
    stage = request.get("target_stage")
    scope = request.get("scope")
    if stage not in STAGES or scope not in ("general", "project"):
        raise ValueError("改进请求的目标阶段或层级无效")
    target_project = identifier(request.get("project") or project or "unknown")
    if scope == "project" and project and target_project != project:
        raise ValueError("仓库专属请求的项目与当前运行不一致")
    evidence = request.get("evidence") or []
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("改进请求缺少证据")
    run_dir = Path(request.get("run_dir") or request_path.parents[2]).resolve()
    result_dir = run_dir / "rsi/skillopt"
    result_file = result_dir / f"{identifier(request.get('id') or request_path.stem)}.json"
    prior = read(result_file, {})
    if prior.get("status") == "candidate" and prior.get("candidate_id"):
        return prior

    bank = SkillBank(repo)
    base = bank.render(stage, target_project)
    base_text = base.get("text") or f"# {stage} 阶段技能\n"
    suggestions = _suggestions(request)
    if not suggestions:
        raise ValueError("改进请求没有可执行的修改建议")
    patch = {
        "reasoning": str(request.get("problem") or "第 08 阶段根据多阶段反馈提出修改"),
        "revise_suggestions": suggestions,
    }
    started = time.monotonic()
    meta = skillopt_metadata(repo)
    attempts = 0
    try:
        if rewrite is None:
            rewrite, model_name = _rewrite_function(repo, model)
        else:
            model_name = model or "test-rewrite"
        response = None
        max_attempts = max(1, min(2, int(os.environ.get("SKILLOPT_MAX_ATTEMPTS", "2"))))
        for attempts in range(1, max_attempts + 1):
            response = rewrite(base_text, patch, reasoning_effort=None)
            if isinstance(response, Mapping):
                break
        if not isinstance(response, Mapping):
            raise ValueError("SkillOpt 未返回可解析的 JSON")
        content = _clean_skill(response.get("new_skill"))
        if content.strip() == base_text.strip():
            raise ValueError("SkillOpt 返回内容与基线相同，没有可评估的修改")
        provenance = {
            "source_stages": request.get("source_stages") or ["learner"],
            "target_stage": stage,
            "source_run": run_dir.name,
            "source_commit": request.get("source_commit") or "",
            "base_versions": base.get("versions", []),
            "problem": str(request.get("problem") or ""),
            "change": suggestions,
            "scope": scope,
            "expected_improvement": str(request.get("expected_improvement") or ""),
            "possible_regression": str(request.get("possible_regression") or ""),
            "engine": {**meta, "backend": "claude_chat", "model": model_name},
        }
        candidate = bank.propose(
            stage, target_project, scope, content, evidence,
            request.get("conditions") or {}, provenance=provenance,
        )
        result = {
            "status": "candidate",
            "request_id": request.get("id"),
            "candidate_id": candidate["id"],
            "target_stage": stage,
            "scope": scope,
            "model": model_name,
            "skillopt": meta,
            "base_versions": base.get("versions", []),
            "suggestions": suggestions,
            "reasoning": str(response.get("reasoning") or ""),
            "change_summary": (
                response.get("change_summary")
                if isinstance(response.get("change_summary"), list) else []
            ),
            "new_skill": content,
            "attempts": attempts,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "created_at": now(),
        }
    except Exception as exc:
        result = {
            "status": "failed",
            "request_id": request.get("id"),
            "target_stage": stage,
            "scope": scope,
            "skillopt": meta,
            "error": f"{type(exc).__name__}: {exc}",
            "attempts": attempts,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "created_at": now(),
        }
    write(result_file, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--project", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    print(json.dumps(optimize_request(
        args.request, repo=args.root, project=args.project, model=args.model or None,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
