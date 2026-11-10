#!/usr/bin/env python3
"""离线检查安全审计编排说明、项目画像和波次计划。

这个工具只供开发期检查使用，不参与真实审计运行，也不会限制编排智能体
选择哪个技能。它检查的是：说明是否给出了跨波次换技能的规则，项目画像
是否为已识别入口保留了对应技能，波次计划是否出现明显的单技能集中。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MAX_TASKS_PER_WAVE = 6
MAX_WAVES = 3
MAX_TASKS_PER_SKILL_PER_WAVE = 2

ENTRY_SKILL_RULES = {
    "http": (
        "web-auth-analyzer",
        "unauth-route-scanner",
        "rpc-surface-scanner",
    ),
    "grpc": (
        "rpc-surface-scanner",
        "web-auth-analyzer",
    ),
    "ipc": ("ipc-serialization-analyzer",),
    "exec": (
        "command-injection-analyzer",
        "code-injection-analyzer",
    ),
    "model": (
        "model-loading-analyzer",
        "insecure-deserialization-analyzer",
    ),
    "sandbox": ("sandbox-boundary-analyzer",),
    "cli": ("command-injection-analyzer",),
    "native": ("memory-safety-analyzer",),
}

ORCHESTRATOR_RULES = (
    (
        "orchestrator.multi_wave",
        r"最多\s*3\s*[波批轮]",
        "说明里应写明最多 3 波，避免无限循环。",
    ),
    (
        "orchestrator.wave_size",
        r"每波[^。\n]{0,30}(?:最多\s*)?6|最多\s*6\s*个",
        "说明里应写明每波最多 6 个分析任务。",
    ),
    (
        "orchestrator.wait_all",
        r"(?:等|等待)[^。\n]{0,40}(?:全部|本波|该波)[^。\n]{0,20}返回",
        "说明里应要求每波全部返回后再合并和生成下一波。",
    ),
    (
        "orchestrator.skill_loading",
        r"调用[^。\n]{0,20}Skill[^。\n]{0,30}加载|实际加载",
        "说明里应要求由子智能体实际加载技能，而不是只写技能名。",
    ),
    (
        "orchestrator.cross_domain",
        r"recommended_skills|传统|跨[^。\n]{0,10}(?:域|边界)",
        "说明里应保留传统技能和项目画像推荐技能的候选入口。",
    ),
    (
        "orchestrator.stop_condition",
        r"没有新证据|无新证据|不能带来新",
        "说明里应写明没有新证据时停止。",
    ),
    (
        "orchestrator.blocked",
        r"blocked|受阻",
        "说明里应区分受阻和已完成，避免把未执行写成完成。",
    ),
)


def finding(severity: str, code: str, message: str, where: str = "") -> dict[str, str]:
    item = {"severity": severity, "code": code, "message": message}
    if where:
        item["where"] = where
    return item


def check_orchestrator(text: str) -> list[dict[str, str]]:
    findings = []
    for code, pattern, message in ORCHESTRATOR_RULES:
        if not re.search(pattern, text):
            findings.append(finding("warning", code, message, "security-orchestrator"))
    return findings


def check_profile(profile: dict[str, Any]) -> list[dict[str, str]]:
    entrypoints = profile.get("entrypoints") or {}
    infra = entrypoints.get("infra") if isinstance(entrypoints, dict) else None
    if not isinstance(infra, list):
        infra = []
    kinds = {
        str(item.get("kind"))
        for item in infra
        if isinstance(item, dict) and item.get("kind")
    }
    skills = {str(item) for item in (profile.get("recommended_skills") or [])}
    findings = []
    for kind, expected in ENTRY_SKILL_RULES.items():
        if kind not in kinds:
            continue
        if skills.intersection(expected):
            continue
        findings.append(
            finding(
                "warning",
                "profile.missing_skill",
                f"存在 {kind} 入口，但推荐技能中没有 {', '.join(expected)}；"
                "请确认是入口不需要这些技能，还是画像漏掉了候选。",
                f"entrypoint:{kind}",
            )
        )
    return findings


def _wave_number(task: dict[str, Any]) -> int:
    try:
        return int(task.get("wave", 1))
    except (TypeError, ValueError):
        return 1


def check_plan(plan: Any) -> list[dict[str, str]]:
    tasks = plan.get("tasks") if isinstance(plan, dict) else plan
    if not isinstance(tasks, list):
        return [finding("error", "plan.invalid", "波次计划必须是任务数组。")]
    findings = []
    waves: dict[int, list[dict[str, Any]]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            findings.append(finding("warning", "plan.invalid_task", "任务必须是对象。"))
            continue
        waves.setdefault(_wave_number(task), []).append(task)

    if len(waves) > MAX_WAVES:
        findings.append(
            finding(
                "warning",
                "plan.too_many_waves",
                f"计划包含 {len(waves)} 波，超过 {MAX_WAVES} 波上限。",
            )
        )

    seen_dedup: dict[str, str] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        coverage_id = str(task.get("coverage_id", ""))
        skill = str(task.get("skill", ""))
        if not coverage_id:
            findings.append(finding("warning", "plan.missing_coverage", "任务缺少 coverage_id。"))
        if not skill:
            findings.append(finding("warning", "plan.missing_skill", "任务缺少 skill。"))
        dedup_key = task.get("dedup_key")
        if dedup_key:
            key = str(dedup_key)
            if key in seen_dedup and seen_dedup[key] != coverage_id:
                findings.append(
                    finding(
                        "warning",
                        "plan.duplicate_dedup",
                        f"去重键 {key} 被多个覆盖条目重复使用。",
                        coverage_id,
                    )
                )
            seen_dedup[key] = coverage_id

    for wave in sorted(waves):
        items = waves[wave]
        skills = [str(item.get("skill", "")) for item in items if item.get("skill")]
        counts = Counter(skills)
        if len(items) > MAX_TASKS_PER_WAVE:
            findings.append(
                finding(
                    "warning",
                    "plan.wave_too_large",
                    f"第 {wave} 波有 {len(items)} 个任务，超过 {MAX_TASKS_PER_WAVE} 个上限。",
                    f"wave:{wave}",
                )
            )
        if len(skills) >= 2 and len(counts) < 2:
            findings.append(
                finding(
                    "warning",
                    "plan.single_skill_wave",
                    f"第 {wave} 波包含 {len(skills)} 个任务，但只使用了 1 个技能；"
                    "请确认其他候选确实缺少入口，或补充换视角任务。",
                    f"wave:{wave}",
                )
            )
        for skill, count in counts.items():
            if count > MAX_TASKS_PER_SKILL_PER_WAVE:
                findings.append(
                    finding(
                        "warning",
                        "plan.skill_overused",
                        f"第 {wave} 波中技能 {skill} 出现 {count} 次，超过建议上限"
                        f" {MAX_TASKS_PER_SKILL_PER_WAVE} 次。",
                        f"wave:{wave}",
                    )
                )

    dominant = {}
    for wave in sorted(waves):
        skills = [str(item.get("skill", "")) for item in waves[wave] if item.get("skill")]
        if not skills:
            continue
        counts = Counter(skills)
        dominant[wave] = counts.most_common(1)[0][0]
    ordered_waves = sorted(dominant)
    for previous, current in zip(ordered_waves, ordered_waves[1:]):
        if dominant[previous] == dominant[current]:
            findings.append(
                finding(
                    "warning",
                    "plan.consecutive_skill",
                    f"第 {previous} 波和第 {current} 波都以技能 {dominant[current]} 为主；"
                    "请确认这是有新证据，而不是沿着同一视角重复。",
                    f"wave:{current}",
                )
            )
    return findings


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(
    orchestrator_text: str | None = None,
    profile: Any = None,
    plan: Any = None,
) -> dict[str, Any]:
    findings = []
    if orchestrator_text is not None:
        findings.extend(check_orchestrator(orchestrator_text))
    if profile is not None:
        if isinstance(profile, dict):
            findings.extend(check_profile(profile))
        else:
            findings.append(finding("error", "profile.invalid", "项目画像必须是 JSON 对象。"))
    if plan is not None:
        findings.extend(check_plan(plan))
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "ok": not errors,
        "findings": findings,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "checks": sum(
                value is not None for value in (orchestrator_text, profile, plan)
            ),
        },
    }


def render_text(report: dict[str, Any]) -> str:
    findings = report["findings"]
    if not findings:
        return "编排检查通过：未发现需要人工确认的收窄信号。"
    lines = [f"编排检查发现 {len(findings)} 条提示："]
    for item in findings:
        where = f" ({item['where']})" if item.get("where") else ""
        lines.append(f"- [{item['severity']}] {item['code']}{where}: {item['message']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="离线检查审计编排说明、项目画像和波次计划，不参与真实审计。"
    )
    parser.add_argument(
        "--orchestrator",
        default=".claude/agents/security-orchestrator.md",
        help="编排说明文件；传空字符串可跳过。",
    )
    parser.add_argument("--profile", help="project-profile.json 路径。")
    parser.add_argument("--plan", help="包含 wave、skill、coverage_id 的任务计划 JSON。")
    parser.add_argument("--json", action="store_true", help="输出机器可读结果。")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="存在 warning 或 error 时返回非零；默认只报告，不阻断。",
    )
    args = parser.parse_args()

    try:
        orchestrator_text = None
        if args.orchestrator:
            orchestrator_text = Path(args.orchestrator).read_text(encoding="utf-8")
        profile = load_json(Path(args.profile)) if args.profile else None
        plan = load_json(Path(args.plan)) if args.plan else None
    except (OSError, ValueError) as exc:
        print(f"无法读取输入: {exc}", file=sys.stderr)
        return 2

    report = audit(orchestrator_text, profile, plan)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    if args.strict and report["findings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
