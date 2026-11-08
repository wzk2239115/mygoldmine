#!/usr/bin/env python3
"""读取覆盖引导的项目探索与有界 Markdown 试用；不改变漏洞验收。"""

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path

from rsi_reward import VERSION, calculate
from skill_bank import ROOT, SkillBank, digest, identifier, now, read, write


def plan(repo, project):
    state = read(Path(repo) / "rsi/exploration" / project / "state.json", {})
    rendered = SkillBank(repo).render("orchestrator", project)
    trial = state.get("trial")
    if not any(
        x.get("scope") == "project_trial" and trial and x["id"] == trial["candidate"]
        for x in rendered["versions"]
    ):
        trial = None
    tasks = list(state.get("tasks", {}).values())
    tasks.sort(key=lambda x: (-x["energy"], x["attempts"]))
    return {
        "schema_version": 1,
        "project": project,
        "tasks": tasks[:40],
        "exploration_reserve": 0.2,
        "trial": trial,
        "notice": (
            "预算为建议档位，智能体可提出新任务、改变顺序并说明原因。"
            "读取量不代表审计完成；保留探索预算。"
        ),
    }


def report_signals(repo, project, run_id):
    """复用报告页面的严格验收；不可用时不产生强奖励。"""
    with urllib.request.urlopen(
        "http://127.0.0.1:8787/api/verified-reports", timeout=30
    ) as response:
        reports = json.load(response)["items"]
    with urllib.request.urlopen("http://127.0.0.1:8787/api/board", timeout=30) as response:
        findings = json.load(response)["findings"]
    lookup = {x["key"]: x for x in findings}
    signals = []
    for report in reports:
        if report["project"] != project:
            continue
        finding = lookup.get(report["key"])
        if not finding:
            continue
        semantic = finding.get("semanticId") or finding.get("semantic_id")
        if not semantic:
            semantic = digest(
                {
                    "root": finding.get("rootCause"),
                    "paths": sorted(finding.get("sourcePaths") or []),
                }
            )
            if not finding.get("rootCause") or not finding.get("sourcePaths"):
                continue
        signals.append(
            {
                "semantic_id": semantic,
                "report_key": report["key"],
                "historical": report["runId"] != run_id,
            }
        )
    return signals


def feedback(repo, source, output, project, candidate_ids=(), reports=None):
    repo, source, output = Path(repo).resolve(), Path(source).resolve(), Path(output).resolve()
    identifier(project)
    bank = SkillBank(repo)
    folder = repo / "rsi/exploration" / project
    source_key = str(source.relative_to(repo))
    if not source.is_relative_to(repo / "runs" / project) or not output.is_relative_to(
        repo / "runs"
    ):
        raise ValueError("探索反馈必须属于当前项目运行")
    coverage = read(source / "task-artifacts/read-coverage/summary.json", {})
    ledger = read(source / "task-artifacts/coverage-ledger.json", {})
    jev = read(source / "triage/jev-infra.json", {})
    marker = {
        "formula_version": VERSION,
        "jev": digest(jev),
        "source": source_key,
        "coverage": digest(coverage),
        "ledger": digest(ledger),
        "run_state": read(Path(str(source) + ".meta") / "status.json", {}).get("state"),
    }
    unavailable = None
    if reports is None:
        try:
            reports = report_signals(repo, project, source.name)
        except (OSError, ValueError, KeyError) as exc:
            reports = []
            unavailable = type(exc).__name__
    # 全局状态与候选共享原有锁，不再创建第二套锁或发布指针。
    with bank.lock():
        state = read(
            folder / "state.json",
            {
                "schema_version": 1,
                "project": project,
                "tasks": {},
                "seen_reads": [],
                "seen_reports": [],
                "rounds": {},
            },
        )
        fingerprint = digest(
            {
                **marker,
                "reports": reports,
                "report_signal_unavailable": unavailable,
                "candidates": sorted(candidate_ids),
            }
        )
        previous = state["rounds"].get(source_key)
        if previous and previous.get("fingerprint") == fingerprint:
            result = previous["result"]
            write(output / "rsi/exploration-feedback.json", result)
            write(output / "rsi/reward.json", result.get("objective", {}))
            return result
        reads = {
            digest([x.get("file"), x.get("file_sha256")])
            for x in coverage.get("files", [])
            if x.get("kind") == "read" and x.get("file")
        }
        new_reads = reads - set(state["seen_reads"])
        state["seen_reads"] = sorted(set(state["seen_reads"]) | reads)
        known_reports = set(state["seen_reports"]) | {
            x["semantic_id"] for x in reports if x.get("historical")
        }
        fresh_reports = list(
            {x["semantic_id"]: x for x in reports if x["semantic_id"] not in known_reports}.values()
        )
        state["seen_reports"] = sorted(known_reports | {x["semantic_id"] for x in reports})
        evidence_changes = 0
        for entry in ledger.get("entries", []):
            # 不以意图自由文本的新名字作为新颖性奖励。
            key = digest([ledger.get("source_version"), entry.get("area"), entry.get("view")])
            task = state["tasks"].get(
                key,
                {
                    "area": entry.get("area"),
                    "view": entry.get("view"),
                    "hypothesis": entry.get("hypothesis"),
                    "attempts": 0,
                    "stale": 0,
                    "energy": 1,
                },
            )
            signature = digest(entry.get("evidence") or [])
            changed = bool(entry.get("evidence")) and signature != task.get("evidence_hash")
            if not previous:
                task["attempts"] += 1
                task["stale"] = 0 if changed else task["stale"] + 1
            evidence_changes += int(changed)
            task.update(
                evidence_hash=signature,
                status=entry.get("status"),
                hypothesis=entry.get("hypothesis"),
                next_action=entry.get("next_action"),
            )
            task["energy"] = (
                0
                if entry.get("status") == "blocked"
                else 3
                if changed and entry.get("risk") in ("critical", "high")
                else 2
                if changed
                else 1
                if task["stale"] < 3
                else 0
            )
            state["tasks"][key] = task
        prior_result = previous.get("result", {}) if previous else {}
        # 首次迁移只用已观测历史建立覆盖基线，不伪造历史奖励。
        if "reward_coverage" not in state:
            state["reward_coverage"] = {}
            for old_key in state["rounds"]:
                if old_key == source_key:
                    continue
                old_source = (repo / old_key).resolve()
                if old_source.is_relative_to(repo / "runs" / project):
                    calculate(
                        read(old_source / "task-artifacts/read-coverage/summary.json", {}),
                        {},
                        state["reward_coverage"],
                        [],
                    )
        objective = calculate(
            coverage,
            jev,
            state["reward_coverage"],
            [x["semantic_id"] for x in fresh_reports],
            report_available=unavailable is None,
            prior=prior_result.get("objective"),
        )
        objective.update(
            project=project,
            run_id=source.name,
            updated_at=now(),
            input_fingerprint=fingerprint,
            coverage_sha256=digest(coverage),
            jev_sha256=digest(jev),
        )
        reward = objective["total"]
        trial = state.get("trial")
        used = read(source / "task-artifacts/exploration-plan.json", {}).get("trial")
        if (
            trial
            and used
            and used.get("candidate") == trial.get("candidate")
            and marker.get("run_state") in ("failed", "timeout", "stopped")
        ):
            trial["status"] = "retired"
            trial["reason"] = "运行失败，先撤回项目试用；不作因果归责"
            write(folder / "trials" / (trial["candidate"] + ".json"), trial)
            state["trial"] = None
            trial = None
        if trial and used and used.get("candidate") == trial.get("candidate") and not previous:
            trial["observed_runs"] = trial.get("observed_runs", 0) + 1
            trial["associated_report_reward"] = trial.get("associated_report_reward", 0) + 10 * len(
                fresh_reports
            )
            trial["attribution"] = "association_only"
            stages = read(Path(str(source) + ".meta") / "status.json", {})
            failure = stages.get("state") in ("failed", "timeout", "stopped")
            if objective["status"] == "complete":
                trial["no_gain_runs"] = (
                    trial.get("no_gain_runs", 0) + 1 if not reward or failure else 0
                )
            if failure or trial["no_gain_runs"] >= 2:
                trial["status"] = "retired"
                state["trial"] = None
            elif trial["observed_runs"] >= 3:
                trial["status"] = "project_retained"
            write(folder / "trials" / (trial["candidate"] + ".json"), trial)
        # 仅新生成、明确标为方法改进的阶段二候选进入项目级试用。
        selected = None
        if not state.get("trial"):
            for cid in candidate_ids:
                candidate = bank.candidate(cid)
                provenance = candidate.get("provenance") or {}
                if (
                    candidate["project"] != project
                    or candidate["stage"] != "orchestrator"
                    or provenance.get("change_kind") != "method"
                ):
                    continue
                from skillopt_adapter import execution_baseline

                _, documents = execution_baseline(
                    repo, "orchestrator", bank.render("orchestrator", project)
                )
                selected = {
                    "candidate": cid,
                    "status": "probation",
                    "project": project,
                    "base_documents": documents,
                    "created_at": now(),
                    "observed_runs": 0,
                    "notice": "项目限定试用，不是稳定发布或因果效果证明",
                }
                state["trial"] = selected
                write(folder / "trials" / (cid + ".json"), selected)
                break
        write(folder / "trial.json", state.get("trial") or {})
        result = {
            "status": "trial_selected" if selected else "observed",
            "published": [],
            "results": [],
            "interesting": bool(reward > 0),
            "new_read_regions": len(new_reads) + prior_result.get("new_read_regions", 0),
            "evidence_changes": evidence_changes + prior_result.get("evidence_changes", 0),
            "verified_reports": prior_result.get("verified_reports", []) + fresh_reports,
            "report_signal_unavailable": unavailable,
            "reward": reward,
            "objective": objective,
            "trial": state.get("trial"),
            "notice": (
                "奖励由新增风险加权覆盖和新验证漏洞计算；表示关联收益，不证明技能改动的因果效果。"
            ),
        }
        state["rounds"][source_key] = {"fingerprint": fingerprint, "result": result}
        write(folder / "state.json", state)
        write(output / "rsi/exploration-feedback.json", result)
        write(output / "rsi/reward.json", objective)
    return result


def trial_text(bank, stage, project, pins):
    if stage != "orchestrator" or os.environ.get("STAGE_SKILL_EVALUATING"):
        return ""
    trial = read(bank.repo / "rsi/exploration" / project / "trial.json", {})
    baseline_file = os.environ.get("STAGE_SKILL_BASELINE")
    cid = pins.get("trial/orchestrator/" + project) if baseline_file else trial.get("candidate")
    if not cid or trial.get("candidate") != cid:
        return ""
    for item in trial.get("base_documents", []):
        file = (bank.repo / item["path"]).resolve(strict=True)
        if (
            not file.is_relative_to(bank.repo)
            or hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]
        ):
            return ""
    candidate = bank.candidate(cid)
    if candidate["project"] != project or candidate["stage"] != stage:
        return ""
    return (
        "\n项目限定的阶段二方法试用（版本 " + cid + "）：\n"
        "以下补充只适用于阅读、假设追踪和任务分派；不得修改验证状态、工具权限、隔离、证据或发布门槛。"
        "可按项目判断不适用并说明原因。\n" + candidate["content"]
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    write(
        Path(args.run) / "task-artifacts/exploration-plan.json",
        plan(ROOT, identifier(args.project)),
    )


if __name__ == "__main__":
    main()
