"""Stage-specific producer APIs. Identity and serialization belong to the host."""

import copy
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from producer_contract import task_context
from skill_bank import infer_project

TEXT = {"type": "string", "minLength": 1}
STRINGS = {"type": "array", "items": {"type": "string"}}
OBJECT = {"type": "object"}
ROWS = {"type": "array", "items": OBJECT}


def enum(*values):
    return {"type": "string", "enum": list(values)}


# Separate contracts, not an unrestricted document argument.
SPECS = {
    "environment": (
        "submit_environment",
        "提交环境构建及实际验收结果",
        "env-manifest.json",
        {
            "env_status": enum("ready", "partial", "blocked"),
            "reason": TEXT,
            "image": TEXT,
            "image_id": TEXT,
            "build_exit_code": {"type": "integer"},
            "acceptance": ROWS,
            "capabilities": OBJECT,
        },
        ["env_status"],
    ),
    "orchestrator": (
        "submit_audit_report",
        "提交本轮全部候选与审计摘要，不得丢弃候选规避检查",
        "audit-report.json",
        {
            "project_name": TEXT,
            "findings": ROWS,
            "metadata": OBJECT,
            "overview": OBJECT,
            "coverage": OBJECT,
            "report_file": {
                "type": "string",
                "minLength": 1,
                "description": "工具返回的本次审计报告草稿路径；修正时复用全部候选，无需重传 findings",
            },
            "finding_updates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": TEXT, "changes": OBJECT},
                    "required": ["id", "changes"],
                    "additionalProperties": False,
                },
            },
        },
        [],
    ),
    "visual": (
        "submit_attack_design",
        "提交攻击机制设计及已有文生图图片引用",
        None,
        {"design": OBJECT, "image": TEXT},
        ["design"],
    ),
    "verify": (
        "submit_verification",
        "提交单个候选的验证结论及实际证据文件",
        "verify-report.json",
        {
            "verdict": enum("confirmed", "rejected", "blocked", "inconclusive"),
            "reason": TEXT,
            "evidence": STRINGS,
            "harness": TEXT,
            "finding_file": TEXT,
            "artifacts": {"type": "object", "additionalProperties": TEXT},
        },
        ["verdict", "reason", "evidence"],
    ),
    "redteam-lab": (
        "submit_attack_lab",
        "提交隔离场景配置或真实受阻说明；身份和源码绑定由工具补充",
        None,
        {
            "scenario": OBJECT,
            "blocked": OBJECT,
        },
        [],
    ),
    "redteam-agent": (
        "submit_execution_result",
        "提交执行说明；捕获状态与证据来源由真实执行器读取",
        "stage-result.json",
        {},
        [],
    ),
    "judge": (
        "submit_review",
        "提交证据审核结论；工具独立核对证据来源",
        "judge.json",
        {
            "verdict": enum("approved", "rejected", "needs_review"),
            **{
                key: {"type": "boolean"}
                for key in (
                    "intended_vulnerability",
                    "flag_provenance",
                    "no_cheat",
                    "environment_plausible",
                    "reproducible",
                    "minimal",
                )
            },
            "confidence": enum("high", "medium", "low"),
            "reason": TEXT,
            "concerns": STRINGS,
            "recommended_status": enum("runtime-validated", "needs-rerun", "rejected"),
        },
        [
            "verdict",
            "intended_vulnerability",
            "flag_provenance",
            "no_cheat",
            "environment_plausible",
            "reproducible",
            "minimal",
            "confidence",
            "reason",
            "concerns",
            "recommended_status",
        ],
    ),
    "learner": (
        "submit_learning",
        "提交学习归因及已登记的优化候选；不直接发布技能",
        "rsi/learning-result.json",
        {
            "status": enum("completed", "no_changes", "blocked"),
            "conclusions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "stage": enum(
                            "environment",
                            "orchestrator",
                            "visual",
                            "verify",
                            "redteam-lab",
                            "redteam-agent",
                            "judge",
                            "learner",
                        ),
                        "category": enum(
                            "method_gap",
                            "project_knowledge",
                            "framework_bug",
                            "insufficient_evidence",
                            "no_change",
                        ),
                        "reason": TEXT,
                        "next_action": TEXT,
                        "evidence": STRINGS,
                    },
                    "required": ["stage", "category", "reason", "next_action", "evidence"],
                    "additionalProperties": False,
                },
            },
            "proposal_ids": STRINGS,
        },
        ["status", "conclusions", "proposal_ids"],
    ),
}


def tool(stage):
    name, description, _, properties, required = SPECS[stage]
    return {
        "name": name,
        "description": description + "。检查 success、decision；"
        "未通过时依据 errors 和 repair 修正参数再次调用，遵守阶段时限。",
        "inputSchema": {
            "type": "object",
            "properties": {
                **copy.deepcopy(properties),
                "summary": TEXT,
                "limitations": STRINGS,
                "attachments": STRINGS,
            },
            "required": [*required, "summary", "limitations"],
            "additionalProperties": False,
        },
    }


def validate(value, schema, field="$"):
    kind = schema.get("type")
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": type(value) is bool,
        "integer": type(value) is int,
    }.get(kind, True)
    if not valid:
        raise ValueError(f"{field} 必须为 {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{field} 合法取值：{schema['enum']}")
    if isinstance(value, str) and len(value.strip()) < schema.get("minLength", 0):
        raise ValueError(f"{field} 不能为空")
    if kind == "object":
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{field}.{key} 缺失")
        for key, child in value.items():
            if key in properties:
                validate(child, properties[key], field + "." + key)
            elif schema.get("additionalProperties") is False:
                raise ValueError(f"{field}.{key} 不允许；身份与真实执行状态由框架绑定")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate(child, schema["additionalProperties"], field + "." + key)
    if kind == "array":
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{field} 条目不足")
        for i, child in enumerate(value):
            validate(child, schema.get("items", {}), f"{field}[{i}]")


def materialize(stage, root, args, task):
    """Each branch translates its own domain inputs to the existing downstream contract."""
    document = {
        k: copy.deepcopy(v)
        for k, v in args.items()
        if k not in {"summary", "limitations", "attachments", "report_markdown",
                     "report_file", "finding_updates"}
    }
    filename = SPECS[stage][2]
    if stage == "environment":
        # Keep build-generated operational metadata; the producer submits its assessment.
        existing = root / "env-manifest.json"
        if existing.is_file() and not existing.is_symlink():
            built = json.loads(existing.read_text())
            if not isinstance(built, dict):
                raise ValueError("环境构建清单必须为对象")
            document = {**built, **document}
    elif stage == "orchestrator":
        from producer_contract import package_file

        source = args.get("report_file")
        updates = args.get("finding_updates", [])
        if source:
            if "findings" in args:
                raise ValueError("复用报告草稿时不能同时重传 findings；使用 finding_updates 修正已有候选")
            source_path, payload = package_file(root, source)
            try:
                document = json.loads(payload)
            except (ValueError, UnicodeError) as exc:
                raise ValueError("报告草稿必须是 UTF-8 JSON 对象：" + source_path) from exc
            if not isinstance(document, dict):
                raise ValueError("报告草稿必须是 JSON 对象")
            for key in ("project_name", "metadata", "overview", "coverage"):
                if key in args:
                    document[key] = copy.deepcopy(args[key])
        else:
            if "findings" not in args:
                raise ValueError("首次提交需要 findings；修正已有报告请传 report_file")
            if updates:
                raise ValueError("finding_updates 只能与 report_file 一同使用")
        if updates:
            findings = document.get("findings")
            if not isinstance(findings, list):
                raise ValueError("报告草稿缺少 findings 数组，无法按编号修正")
            seen = set()
            for update in updates:
                identifier = update["id"]
                changes = update["changes"]
                if identifier in seen:
                    raise ValueError("同一次提交中候选编号重复：" + identifier)
                seen.add(identifier)
                if {"id", "finding_id", "project"} & changes.keys():
                    raise ValueError("finding_updates 不允许修改候选编号或项目身份")
                matches = [row for row in findings
                           if isinstance(row, dict) and row.get("id") == identifier]
                if len(matches) != 1:
                    raise ValueError("候选编号不存在或重复：" + identifier)
                matches[0].update(copy.deepcopy(changes))
    elif stage == "visual":
        from producer_contract import package_file

        document = args["design"]
        identifier = task.get("finding_id") or document.get("finding_id")
        if (
            not isinstance(identifier, str)
            or not identifier
            or any(
                c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
                for c in identifier
            )
        ):
            raise ValueError("缺少当前设计候选编号")
        if args.get("image"):
            image, _ = package_file(root, args["image"])
            image = Path(image)
            if image.suffix not in {".webp", ".png", ".jpg"}:
                raise ValueError("需要文生图位图文件")
            filename = str(image.relative_to(root).with_suffix(".director.json"))
        else:
            filename = "scene-" + identifier + ".director.json"
        document = copy.deepcopy(args["design"])
    elif stage == "redteam-lab":
        if ("scenario" in args) == ("blocked" in args):
            raise ValueError("scenario 与 blocked 必须且只能提交一个")
        blocked = "blocked" in args
        document = copy.deepcopy(args["blocked"] if blocked else args["scenario"])
        filename = "blocked.json" if blocked else "scenario.json"
        document["finding_sha256"] = task.get("finding_sha256")
        document["source"] = task.get("source_binding")
        if blocked:
            document["status"] = "blocked"
    elif stage == "redteam-agent":
        raw = json.loads((root / "result.json").read_text())
        document = copy.deepcopy(raw.get("result", raw))
    elif stage == "learner":
        document["schema_version"] = 1
        from producer_contract import learning_evidence_path
        for row in document.get("conclusions", []):
            row["evidence"] = [str(learning_evidence_path(root, value))
                               for value in row.get("evidence", [])]
    if stage != "judge":
        for key in ("project", "finding_id"):
            if task.get(key):
                if key in document and document[key] != task[key]:
                    raise ValueError("提交内容与当前任务身份不一致：" + key)
                document[key] = task[key]
        document["limitations"] = args["limitations"]
    return root / filename, document


def _save_revision_draft(root, stage, receipt_id, document, attachments):
    """Retain a rejected report and its explicit attachments outside the accepted package."""
    folder = root / ".stage-submissions" / stage / "drafts"
    cursor = root
    for part in folder.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("报告草稿目录不能包含符号链接")
    folder.mkdir(parents=True, exist_ok=True)
    draft = folder / (receipt_id + ".json")
    temporary = draft.with_name(draft.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.replace(temporary, draft)
    sidecar = draft.with_name(draft.stem + ".attachments.json")
    temporary = sidecar.with_name(sidecar.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(attachments, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.replace(temporary, sidecar)
    return draft


def _revision_attachments(root, report_file):
    """Reuse explicit attachments unless the next call overrides the attachments field."""
    from producer_contract import package_file

    source = Path(report_file)
    source = source if source.is_absolute() else root / source
    drafts = root / ".stage-submissions" / "orchestrator" / "drafts"
    if source.parent != drafts or source.suffix != ".json":
        return []
    sidecar = source.with_name(source.stem + ".attachments.json")
    if not sidecar.exists():
        return []
    _, payload = package_file(root, sidecar)
    try:
        attachments = json.loads(payload)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("报告草稿的附件清单无效") from exc
    if not isinstance(attachments, list) or any(not isinstance(x, str) for x in attachments):
        raise ValueError("报告草稿的附件清单必须为路径数组")
    return attachments


def submit_structured(stage, root, args, task=None):
    from producer_contract import validate_bound_inputs
    from submission import submit
    from submission_feedback import submission_feedback

    root = Path(root).resolve()
    task = task if task is not None else task_context(stage, root, infer_project(root))
    schema = tool(stage)
    target = None
    prior = None
    document = None
    draft = None
    written = False
    attachments = []
    try:
        validate(args, schema["inputSchema"])
        validate_bound_inputs(task)
        target, document = materialize(stage, root, args, task)
        attachments = args.get("attachments")
        if attachments is None:
            attachments = (
                _revision_attachments(root, args["report_file"])
                if stage == "orchestrator" and args.get("report_file") else []
            )
        # Validate the entire path before any write; rejected revisions preserve old bytes.
        cursor = root
        for part in target.relative_to(root).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("交付路径不能包含符号链接")
        prior = target.read_bytes() if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        os.replace(temporary, target)
        written = True
        result = submit(
            stage,
            root,
            {
                "artifact": str(target),
                "artifacts": attachments,
                "summary": args["summary"],
                "limitations": args["limitations"],
            },
            task=task,
        )
        if not result["success"]:
            if stage == "orchestrator":
                draft = _save_revision_draft(root, stage, result["id"], document, attachments)
            if prior is None:
                target.unlink()
            else:
                target.write_bytes(prior)
            written = False
        else:
            result["delivery_id"] = result["id"]
            result["artifact_path"] = str(target)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        if written and target is not None:
            if prior is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(prior)
        result = {
            "id": str(uuid.uuid4()),
            "stage": stage,
            "success": False,
            "decision": "needs_revision",
            "validation_scope": "artifact_contract",
            "artifact": str(target) if target else None,
            "sha256": None,
            "files": [],
            "summary": args.get("summary") if isinstance(args, dict) else None,
            "limitations": args.get("limitations") if isinstance(args, dict) else None,
            "errors": [str(exc)],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        if stage == "orchestrator" and isinstance(document, dict):
            try:
                draft = _save_revision_draft(root, stage, result["id"], document, attachments)
            except (OSError, ValueError):
                pass
    result["tool"] = schema["name"]
    if not result["success"]:
        feedback = submission_feedback(
            stage, root, target, result["errors"], tool_name=schema["name"],
            input_schema=schema["inputSchema"], draft_file=draft,
            attachments=attachments if stage == "orchestrator" else None,
        )
        result.update(feedback)
        if draft is not None:
            result["report_draft_path"] = str(draft.relative_to(root))
    # The producer and any resumed agent read the same specialized advice.
    receipt = root / ".stage-submissions" / stage / (result["id"] + ".json")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return result
