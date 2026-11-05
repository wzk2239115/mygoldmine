#!/usr/bin/env python3
"""校验并排序审计覆盖记录；不访问网络，不调用模型。"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATUSES = {
    "unchecked": "尚未检查",
    "analyzed": "已分析但未确认",
    "needs_evidence": "待补证据",
    "blocked": "执行受阻",
    "counterevidence": "已有反证",
    "runtime_confirmed": "运行确认",
}
VIEWS = {
    "coverage",
    "entry",
    "dataflow",
    "reachability",
    "guard",
    "permission",
    "config",
    "review",
    "validation",
}
RISKS = {"critical": 4, "high": 3, "medium": 2, "low": 1}
STATUS_WEIGHT = {
    "unchecked": 3,
    "needs_evidence": 2,
    "analyzed": 1,
    "blocked": 1,
    "counterevidence": 0,
    "runtime_confirmed": 0,
}
SCOPE_NOTE = (
    "没有完整分母时只报告已识别范围；没有可信标签时不计算召回率。"
    "读过的文件不计为已覆盖，未发现漏洞不等于安全。"
)


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"无法读取覆盖记录: {exc}") from exc


def validate_ledger(data):
    errors = []
    if not isinstance(data, dict):
        return ["覆盖记录必须是 JSON 对象"]
    if data.get("schema_version") != 1:
        errors.append("schema_version 必须为 1")
    for field in ("project", "source_version"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"缺少 {field}")
    if not isinstance(data.get("limitations"), list):
        errors.append("limitations 必须是数组")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries 必须是非空数组")
        return errors
    seen = set()
    for index, entry in enumerate(entries):
        where = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} 必须是对象")
            continue
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{where} 缺少 id")
        elif identifier in seen:
            errors.append(f"{where} id 重复: {identifier}")
        else:
            seen.add(identifier)
        for field in ("area", "view", "hypothesis", "status", "next_action"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"{where} 缺少 {field}")
        if entry.get("view") not in VIEWS:
            errors.append(f"{where} view 不受支持: {entry.get('view')}")
        if entry.get("status") not in STATUSES:
            errors.append(f"{where} status 不受支持: {entry.get('status')}")
        for field in ("evidence", "missing_evidence", "limitations", "skill_versions", "history"):
            if field in entry and not isinstance(entry[field], list):
                errors.append(f"{where} {field} 必须是数组")
        if entry.get("status") in {
            "analyzed",
            "needs_evidence",
            "counterevidence",
            "runtime_confirmed",
        }:
            if not entry.get("evidence"):
                errors.append(f"{where} 状态 {entry.get('status')} 需要至少一条证据")
        if entry.get("status") == "needs_evidence" and not entry.get("missing_evidence"):
            errors.append(f"{where} 待补证据状态需要 missing_evidence")
        if entry.get("status") == "blocked" and not entry.get("limitations"):
            errors.append(f"{where} 受阻状态需要 limitations")
        versions = entry.get("skill_versions", [])
        for version in versions:
            if not isinstance(version, dict) or not version.get("name"):
                errors.append(f"{where} skill_versions 条目缺少 name")
            elif (
                not isinstance(version.get("sha256", ""), str)
                or len(version.get("sha256", "")) != 64
            ):
                errors.append(f"{where} skill_versions 条目需要 sha256")
    return errors


def priority(entry):
    risk = RISKS.get(str(entry.get("risk", "medium")).lower(), RISKS["medium"])
    status = STATUS_WEIGHT.get(entry.get("status"), 1)
    missing = len(entry.get("missing_evidence", []))
    history = min(len(entry.get("history", [])), 3)
    review = 1 if entry.get("review_conditions") else 0
    return round(risk * 10 + status * 3 + missing + history * 0.5 + review, 3)


def signals(data):
    entries = data.get("entries", [])
    return {
        "identified_entries": len(entries),
        "unchecked": sum(entry.get("status") == "unchecked" for entry in entries),
        "uncovered_high_risk": sum(
            entry.get("status") == "unchecked"
            and str(entry.get("risk", "")).lower() in {"critical", "high"}
            for entry in entries
        ),
        "needs_evidence": sum(entry.get("status") == "needs_evidence" for entry in entries),
        "blocked": sum(entry.get("status") == "blocked" for entry in entries),
        "counterevidence": sum(entry.get("status") == "counterevidence" for entry in entries),
        "runtime_confirmed": sum(entry.get("status") == "runtime_confirmed" for entry in entries),
        "reviewed": sum(len(entry.get("history", [])) > 1 for entry in entries),
        "scope_note": SCOPE_NOTE,
    }


def plan(data):
    errors = validate_ledger(data)
    if errors:
        raise ValueError("；".join(errors))
    tasks = []
    for entry in sorted(data["entries"], key=lambda item: (-priority(item), item.get("id", ""))):
        if entry.get("status") in {"runtime_confirmed", "counterevidence"}:
            continue
        reason = (
            f"风险={entry.get('risk', 'medium')}，"
            f"状态={STATUSES[entry['status']]}，"
            f"缺证据={len(entry.get('missing_evidence', []))}"
        )
        tasks.append(
            {
                "coverage_id": entry["id"],
                "priority": priority(entry),
                "skill": "audit-hypothesis-tracer",
                "artifact": f".workspace/findings/hypotheses/{entry['id']}.md",
                "reason": reason,
                "status": entry["status"],
            }
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": data["project"],
        "source_version": data["source_version"],
        "signals": signals(data),
        "tasks": tasks,
        "limitations": data.get("limitations", []),
    }


def review(data, budget=3, seed=""):
    errors = validate_ledger(data)
    if errors:
        raise ValueError("；".join(errors))
    entries = [entry for entry in data["entries"] if entry.get("status") != "runtime_confirmed"]
    conditioned = [entry for entry in entries if entry.get("review_conditions")]
    conditioned.sort(key=lambda item: (-priority(item), item.get("id", "")))
    selected = conditioned[:budget]
    remaining = [entry for entry in entries if entry not in selected]
    if len(selected) < budget and remaining:
        digest = hashlib.sha256((seed or data.get("project", "")).encode()).hexdigest()
        start = int(digest[:8], 16) % len(remaining)
        ordered = remaining[start:] + remaining[:start]
        selected.extend(ordered[: budget - len(selected)])
    tasks = []
    for entry in selected:
        reason = (
            "新条件触发复审" if entry.get("review_conditions") else "预算内随机复查，避免长期盲区"
        )
        tasks.append(
            {
                "coverage_id": entry["id"],
                "priority": priority(entry),
                "skill": "audit-hypothesis-tracer",
                "artifact": f".workspace/findings/hypotheses/{entry['id']}.md",
                "reason": reason,
                "status": entry["status"],
            }
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": data["project"],
        "source_version": data["source_version"],
        "budget": budget,
        "selected": [entry["id"] for entry in selected],
        "tasks": tasks,
        "scope_note": SCOPE_NOTE,
    }


def markdown(document):
    lines = [
        f"# 覆盖计划：{document.get('project')}",
        "",
        f"源码版本：`{document.get('source_version')}`",
        "",
    ]
    signals_data = document.get("signals", {})
    if signals_data:
        lines += ["## 信号", ""]
        for key in (
            "identified_entries",
            "uncovered_high_risk",
            "needs_evidence",
            "blocked",
            "counterevidence",
            "runtime_confirmed",
            "reviewed",
        ):
            lines.append(f"- {key}: {signals_data.get(key, 0)}")
        lines += ["", f"> {signals_data.get('scope_note', SCOPE_NOTE)}", ""]
    lines += ["## 建议任务", ""]
    for task in document.get("tasks", []):
        lines.append(f"- `{task['coverage_id']}` priority={task['priority']}：{task['reason']}")
    if not document.get("tasks"):
        lines.append("- 当前没有需要继续追踪的条目；不要据此声称全仓库已覆盖。")
    return "\n".join(lines) + "\n"


def write_outputs(base, document):
    base = Path(base)
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    base.with_suffix(".md").write_text(markdown(document), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="校验和排序审计覆盖记录")
    parser.add_argument("action", choices=["validate", "plan", "review"])
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--out")
    parser.add_argument("--budget", type=int, default=3)
    parser.add_argument("--seed", default="")
    args = parser.parse_args()
    try:
        data = read(args.ledger)
        if args.action == "validate":
            errors = validate_ledger(data)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 2
            print("覆盖记录有效")
            return 0
        if args.action == "plan":
            document = plan(data)
        else:
            if not 1 <= args.budget <= 20:
                raise ValueError("复审预算必须在 1 到 20 之间")
            document = review(data, args.budget, args.seed)
        out = (
            Path(args.out)
            if args.out
            else Path(args.ledger).with_name(
                "coverage-plan.json" if args.action == "plan" else "review-plan.json"
            )
        )
        write_outputs(out, document)
        print(json.dumps({"out": str(out), "tasks": len(document["tasks"])}, ensure_ascii=False))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
