#!/usr/bin/env python3
"""Read-only RSI scorecard for the stage VIII learner."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "rsi-scorecard-v1"
RISK_WEIGHT = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0, "info": 0.5}
ANCHOR_RE = re.compile(r"(?P<path>[^\s:,{}]+):(?P<start>\d+)(?:-(?P<end>\d+))?")

def _read(path, scope=None):
    try:
        if path.is_symlink() or (scope is not None and not path.resolve(strict=True).is_relative_to(Path(scope).resolve())):
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None

def _sha(path, scope=None):
    try:
        if path.is_symlink() or (scope is not None and not path.resolve(strict=True).is_relative_to(Path(scope).resolve())):
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None

def _intervals(summary):
    result = {}
    for item in summary.get("files", []) if isinstance(summary, dict) else []:
        if not isinstance(item, dict) or item.get("kind") != "read" or not item.get("file"):
            continue
        path = str(item["file"]).removeprefix("./").lstrip("/")
        ranges = result.setdefault(path, [])
        for row in item.get("ranges", []):
            if not isinstance(row, dict):
                continue
            start, end = row.get("start"), row.get("end")
            if isinstance(start, int) and isinstance(end, int) and 0 < start <= end:
                ranges.append((start, end))
    return result

def _anchors(ledger):
    anchors = []
    for entry in ledger.get("entries", []) if isinstance(ledger, dict) else []:
        if not isinstance(entry, dict):
            continue
        risk = str(entry.get("risk", "info")).lower()
        weight = RISK_WEIGHT.get(risk, 0.5)
        seen = set()
        for evidence in entry.get("evidence", []):
            if not isinstance(evidence, str):
                continue
            for match in ANCHOR_RE.finditer(evidence):
                path = match.group("path").removeprefix("./").lstrip("/")
                start = int(match.group("start"))
                end = int(match.group("end") or start)
                anchor = (path, start, end)
                if start > 0 and end >= start and anchor not in seen:
                    seen.add(anchor)
                    anchors.append({"id": entry.get("id"), "risk": risk, "weight": weight,
                                    "path": path, "start": start, "end": end})
    return anchors

def _overlap(anchor, reads):
    return any(max(anchor["start"], start) <= min(anchor["end"], end)
               for start, end in reads.get(anchor["path"], []))

def _score(summary, ledger, jev, feedback):
    reads = _intervals(summary or {})
    anchors = _anchors(ledger or {})
    total = sum(a["weight"] for a in anchors)
    hit = sum(a["weight"] for a in anchors if _overlap(a, reads))
    risk_score = round(100 * hit / total, 1) if total else None
    risk_evidence = {"availability": "available", "basis": "AgentCov read ranges and ledger source anchors"} if anchors else {"availability": "unavailable", "reason": "coverage ledger lacks parseable file:line evidence"}

    observations = summary.get("observations") if isinstance(summary, dict) else None
    unattributed = summary.get("unattributed") if isinstance(summary, dict) else None
    if isinstance(observations, int) and observations > 0 and isinstance(unattributed, int):
        attribution = round(100 * max(0, observations - unattributed) / observations, 1)
        attribution_evidence = {"availability": "available", "basis": "AgentCov intent attribution summary"}
    else:
        attribution, attribution_evidence = None, {"availability": "unavailable", "reason": "AgentCov attribution counters unavailable"}

    jev_units = jev.get("units", []) if isinstance(jev, dict) else []
    prioritized = []
    for unit in jev_units:
        if not isinstance(unit, dict):
            continue
        path = str(unit.get("path") or unit.get("id") or "").split("#", 1)[0].removeprefix("./").lstrip("/")
        start, end, priority = unit.get("line_start"), unit.get("line_end"), unit.get("priority")
        if path and isinstance(start, int) and isinstance(end, int) and end >= start and isinstance(priority, (int, float)):
            prioritized.append({"path": path, "start": start, "end": end, "weight": max(0.0, min(1.0, float(priority)))})
    jden = sum(a["weight"] for a in prioritized)
    jnum = sum(a["weight"] for a in prioritized if _overlap(a, reads))
    jev_score = round(100 * jnum / jden, 1) if prioritized and jden else None
    jev_evidence = {"availability": "available", "profile": jev.get("profile"), "model": jev.get("model_returned"),
                    "basis": "JEV line priorities compared with AgentCov read ranges"} if prioritized else {"availability": "unavailable", "reason": "JEV output or line-level priorities unavailable"}

    reports = feedback.get("verified_reports") if isinstance(feedback, dict) else None
    report_score = min(100.0, 25.0 * len(reports)) if isinstance(reports, list) else None
    report_evidence = {"availability": "available", "attribution": "associated signal, not causal proof"} if isinstance(reports, list) else {"availability": "unavailable", "reason": "no persisted verified-report feedback for this run"}
    return {
        "agentcov_risk_region_coverage": {"score": risk_score, "evidence": risk_evidence},
        "agentcov_intent_attribution": {"score": attribution, "evidence": attribution_evidence},
        "jev_priority_coverage": {"score": jev_score, "evidence": jev_evidence},
        "verified_discovery_signal": {"score": report_score, "evidence": report_evidence},
        "resource_efficiency": {"score": None, "evidence": {"reason": "no complete, stage-II-attributed resource counter is available"}},
    }

def scorecard(repo: Path, run: Path, project: str, history_limit: int = 8):
    repo, run = Path(repo).resolve(), Path(run).resolve()
    if not isinstance(project, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", project) or project in {".", ".."}:
        raise ValueError("invalid project identifier")
    runs_root = (repo / "runs" / project).resolve()
    if not run.is_relative_to(runs_root) or not run.is_dir():
        raise ValueError("scorecard scope must be the current project's run directory")
    paths = {
        "read_coverage": run / "task-artifacts/read-coverage/summary.json",
        "coverage_ledger": run / "task-artifacts/coverage-ledger.json",
        "jev": run / "triage/jev-infra.json",
        "exploration_feedback": run / "rsi/exploration-feedback.json",
    }
    summary, ledger, jev, feedback = (_read(paths[name], run) for name in paths)
    source_version = (summary or {}).get("source_version")
    current = _score(summary, ledger, jev, feedback)
    candidates = []
    try:
        children = [p for p in runs_root.iterdir() if p.is_dir() and not p.is_symlink() and p != run and not p.name.endswith(".meta")]
    except OSError:
        children = []
    for candidate in children:
        old_summary = _read(candidate / "task-artifacts/read-coverage/summary.json", candidate)
        if old_summary and source_version and old_summary.get("source_version") == source_version:
            candidates.append((candidate, old_summary))
    candidates.sort(key=lambda pair: pair[0].name, reverse=True)
    history = []
    for candidate, old_summary in candidates[:max(0, history_limit)]:
        history.append({"run_id": candidate.name, "scores": _score(old_summary,
            _read(candidate / "task-artifacts/coverage-ledger.json", candidate),
            _read(candidate / "triage/jev-infra.json", candidate), _read(candidate / "rsi/exploration-feedback.json", candidate))})
    deltas = {}
    for key, item in current.items():
        old = [row["scores"].get(key, {}).get("score") for row in history]
        old = [value for value in old if isinstance(value, (int, float))]
        deltas[key] = round(item["score"] - old[0], 1) if item["score"] is not None and old else None
    return {
        "objective": (feedback or {}).get("objective"),
        "schema_version": SCHEMA_VERSION, "project": project, "run_id": run.name,
        "source_version": source_version, "scores": current,
        "change_from_latest_comparable_run": deltas, "history": history,
        "evidence": {name + "_sha256": _sha(path, run) for name, path in paths.items()},
        "limitations": [
            "历史对照仅包含相同 source_version 的运行；不同源码版本不可直接比较。",
            "JEV 是初筛优先级信号，不是漏洞概率或最终结论。",
            "AgentCov 读取记录是过程证据，不等同于理解或审计质量。",
            "资源效率因缺少阶段二归属的完整成本数据而暂不评分。",
            "评分卡不改变 finding、验证、审核、发布或 RSI 工作流状态。",
        ],
    }
