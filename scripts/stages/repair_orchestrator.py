#!/usr/bin/env python3
"""Repair and resubmit stage-II deliverables through the producer agent."""

import argparse
import json
import os
import shutil
from pathlib import Path

from claude_connection import claude_connection
from owned_process import run_session
from skill_bank import ROOT
from submission import INSTRUCTION, accepted_submissions, config


def repair(run, archive, project, model="", repo=ROOT, invoke=run_session):
    run, archive, repo = Path(run).resolve(), Path(archive).resolve(), Path(repo).resolve()
    if not run.is_relative_to(repo / "runs" / project):
        raise ValueError("修复输入不属于指定项目")
    if not archive.is_relative_to(Path(str(run) + ".meta") / "node-retries/orchestrator"):
        raise ValueError("修复归档目录无效")
    if not (run / "audit-report.json").is_file():
        raise ValueError("缺少现有报告，无法补正；请使用完整重新审计")
    receipts = run / ".stage-submissions/orchestrator"
    previous = {str(p) for p in receipts.glob("*.json")}
    archive.mkdir(parents=True, exist_ok=False)
    for name in (
        "audit-report.json",
        "audit-report.md",
        "task-artifacts",
        "findings",
        ".stage-submissions",
        "raw.jsonl",
    ):
        source, destination = run / name, archive / name
        if source.is_symlink():
            destination.symlink_to(os.readlink(source))
        elif source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        elif source.is_file():
            shutil.copy2(source, destination)
    model, env = claude_connection(model)
    prompt = (
        f"项目编号：{project}。修复第二阶段现有交付，输出根目录：{run}。"
        f"历史只读快照：{archive}，不得修改。"
        "这不是重新扫描任务：若报告来自恢复汇总，coverage.analysis_mode 必须标为 assembly-only；优先保留现有候选及静态验证状态，仅修正字段、格式、"
        "覆盖记录副本、附件及路径问题，不删除候选或编造证据以通过验收。"
        "读取既有 audit-report.json、正式 task-artifacts 和声明的 findings 附件，"
        "逐一运行现有契约检查；覆盖记录 view 只能使用覆盖技能列出的取值，"
        "归并校准使用 review。不要只修工作区而遗漏已声明副本。"
        "完成后调用 mcp__stage_delivery__submit_audit_report，以 report_file 引用本目录 audit-report.json，补充真实摘要与限制；单个候选字段可用 finding_updates 修正，由工具重新验收完整报告，"
        "保留全部必需附件；needs_revision 时依据 errors 和 repair 修正重交，accepted 后结束。"
        "不得自行运行后续阶段，交接由原生工作流调度。无法恢复真实缺失证据时如实报告。"
    )
    command = [
        os.environ.get("CLAUDE_BIN", "claude"),
        "--setting-sources",
        "project,local",
        "--agent",
        "security-orchestrator",
        "--model",
        model,
        "--mcp-config",
        json.dumps(config("orchestrator", run)),
        "--append-system-prompt",
        INSTRUCTION,
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "stream-json",
        "--verbose",
        "-p",
        prompt,
    ]
    log = archive.parent / "repair-agent.jsonl"
    with log.open("w") as output:
        child = invoke(
            command,
            cwd=repo,
            env=env,
            stdout=output,
            stderr=output,
            text=True,
            timeout=int(os.environ.get("ORCHESTRATOR_REPAIR_TIMEOUT", "1800")),
        )
    if child.returncode:
        raise ValueError("编排修复智能体未正常结束；历史快照及日志已保留")
    delivery = accepted_submissions("orchestrator", run)
    main = str(run / "audit-report.json")
    if not any(
        row["artifact"] == main and row["receipt"] not in previous for row in delivery["deliveries"]
    ):
        raise ValueError("修复智能体未通过工具重新提交主报告")
    return delivery


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    print(
        json.dumps(repair(args.run_dir, args.archive, args.project, args.model), ensure_ascii=False)
    )
