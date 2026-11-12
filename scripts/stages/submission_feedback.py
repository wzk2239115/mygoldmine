"""Actionable producer feedback; examples never substitute for actual evidence."""
from pathlib import Path

def submission_feedback(stage, root, artifact, errors, *, tool_name=None, input_schema=None, draft_file=None, attachments=None):
    paths = {
        "environment": ("env-manifest.json", "scripts/stages/submission.py"),
        "orchestrator": ("audit-report.json", "scripts/mine/check_report.py"),
        "visual": ("scene-FINDING.director.json", ".claude/skills/project-cartographer/SKILL.md"),
        "verify": ("verify-report.json", "scripts/workflow/delivery_contract.py"),
        "redteam-lab": ("blocked.json", ".claude/skills/redteam-lab-builder/SKILL.md"),
        "redteam-agent": ("stage-result.json", ".claude/agents/redteam-agent.md"),
        "judge": ("judge.json", "scripts/redteam/contracts.py"),
        "learner": ("rsi/learning-result.json", ".claude/skills/stage-skill-learning/SKILL.md"),
    }
    filename, contract = paths.get(stage, ("result.json", "scripts/stages/submission.py"))
    examples = {
        "learner": {
            "schema_version": 1, "project": "<本次项目编号>", "status": "no_changes",
            "conclusions": [{"stage": "orchestrator", "category": "no_change",
                "reason": "<依据真实反馈说明无需修改的原因>",
                "evidence": ["rsi/stage-feedback/index.json"],
                "next_action": "<下一轮行动或无需修改的理由>"}],
            "proposal_ids": [], "limitations": ["<实际限制，没有则移除此项>"],
        },
        "redteam-lab": {
            "schema_version": 1, "status": "blocked",
            "finding_id": "<任务中的候选编号>", "finding_sha256": "<候选文件真实SHA-256>",
            "source": {"commit": "<任务中的真实提交编号>"}, "mode": "unknown",
            "attacked_surface": "<真实攻击入口>", "reason": "<真实受阻原因>",
            "checked_entries": ["<实际检查过的入口>"],
            "missing_capabilities": ["<实际缺少的能力>"],
            "evidence": ["<实际证据>"], "attempted": ["<实际尝试>"],
            "next_conditions": ["<恢复所需条件>"], "claims_dynamic_validation": False,
        },
        "verify": {"project": "<项目编号>", "finding_id": "<候选编号>",
            "verdict": "blocked", "reason": "<真实受阻原因>",
            "evidence": [], "limitations": ["<尚未取得运行时证据的原因>"]},
        "orchestrator": {"project": "<项目编号>", "project_name": "<显示名称>",
            "findings": ["<按完整报告契约填写全部真实候选，不能清空或丢弃候选以通过验收>"]},
        "environment": {"env_status": "partial", "build_exit_code": 0,
            "image": "<实际镜像标签>", "image_id": "<Docker实际镜像编号>",
            "acceptance": [{"exit_code": 0, "description": "<实际通过的检查>"}]},
        "visual": {"finding_id": "<候选编号>", "mechanism": {"missing_check": "<实际缺失检查与触发机制>"}},
        "redteam-agent": {"finding_id": "<候选编号>", "status": "<实际执行结论>"},
        "judge": {"verdict": "needs_review", "intended_vulnerability": False,
            "flag_provenance": False, "no_cheat": False, "environment_plausible": False,
            "reproducible": False, "minimal": False, "confidence": "low",
            "reason": "<尚未满足的审核条件>", "concerns": ["<实际疑点>"],
            "recommended_status": "needs-rerun"},
    }
    if stage == "redteam-lab" and artifact and Path(artifact).name == "scenario.json":
        examples[stage] = {
            "schema_version": 1, "finding_id": "<任务中的候选编号>",
            "finding_sha256": "<候选文件真实SHA-256>",
            "source": {"commit": "<真实提交编号>"}, "mode": "<http、cli 或 library>",
            "victim_image": "<实际可运行的受害端镜像>",
            "attacker_image": "<实际隔离攻击端镜像>",
            "launch": {"command": ["<真实受害程序>", "<固定参数>"]},
        }
    if stage == "environment" and artifact:
        import json
        try:
            data = json.loads(Path(artifact).read_text())
            if data.get("env_status") == "blocked":
                examples[stage] = {"env_status": "blocked", "reason": "<真实受阻原因>"}
        except (OSError, ValueError, AttributeError):
            pass
    if not errors:
        return {"success": True, "next_action": "交付已接受；不要再修改已提交文件。可完成本次分析，后续调度由框架处理。"}
    if tool_name:
        if stage == "orchestrator":
            if draft_file is not None:
                sample = {"report_file": str(Path(draft_file).relative_to(root))}
            else:
                sample = {"findings": [{
                    "id": "<真实候选编号>", "title": "<真实标题>",
                    "severity": "medium", "root_cause": "<实际根因>",
                    "impact": "<实际影响>", "reproduction": "<实际复现步骤或限制>",
                    "remediation": "<修复建议>", "evidence": ["<真实证据>"],
                    "verification": {"status": "unverified"},
                }]}
        elif stage == "redteam-lab":
            sample = {"blocked": examples[stage]}
        elif stage == "visual":
            sample = {"design": examples[stage]}
        elif stage == "redteam-agent":
            sample = {}
        else:
            sample = examples.get(stage, {})
        properties = (input_schema or {}).get("properties", {})
        sample = {key: value for key, value in sample.items() if key in properties}
        sample.update(summary="<真实交付说明>", limitations=["<实际限制；没有则使用空数组>"])
        if stage == "orchestrator" and attachments:
            sample["attachments"] = attachments
        instruction = (
            "修正草稿和错误指出的全部附件后，传 report_file 再次调用本工具；"
            "保留全部真实候选，可用 finding_updates 按编号修正候选字段。"
            if stage == "orchestrator" and draft_file is not None else
            "根据字段错误补齐真实内容，再次调用本阶段专用工具；缺少证据时如实说明受阻。"
        )
        return {
            "success": False,
            "next_action": "修正后再次调用 " + tool_name,
            "repair": {
                "errors_to_fix": errors,
                "input_schema": input_schema,
                "arguments_example": sample,
                "contract_reference": contract,
                "instruction": instruction,
                "example_notice": "示例含占位符，仅用于说明字段；不得清空或删除真实候选、伪造证据、降低实际结论。",
            },
        }
    return {
        "success": False, "next_action": "读取 errors，修正实际产物及引用附件，再调用 submit_stage_result；普通回复不算提交。",
        "repair": {
            "errors_to_fix": errors,
            "steps": ["先修正 errors 指出的字段、路径或附件；缺证据如实受阻，不生成虚假证据。",
                      "保存修正后的文件，使用下方工具参数再次提交；仍被拒绝时继续依据新错误修正。",
                      "遵守本次执行时限；无法修正时如实报告，不无限重复相同调用。"],
            "resubmit_example": {"artifact": str(artifact or Path(root) / filename),
                                 "artifacts": [], "summary": "<真实交付说明>",
                                 "limitations": ["<实际限制，没有则使用空数组>"]},
            "artifact_example": examples.get(stage, {}),
            "contract_reference": contract,
            "mode_specific_requirements": "场景示例仅列通用字段；必须按所选模式的契约补齐网络、输入、入口和负向控制。此说明不写入正式产物。" if stage == "redteam-lab" else None,
            "example_notice": "仅为格式参考，含占位符；必须填写真实数据并保留本次完整结果和必需附件。受阻示例不是建议改变结论，不能将 confirmed、已构建或通过审核降级以规避检查。",
        },
    }
