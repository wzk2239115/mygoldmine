"""Stage-specific producer APIs. Identity and serialization belong to the host."""

import copy
import json
import os
import uuid
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
        },
        ["findings"],
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
        if k not in {"summary", "limitations", "attachments", "report_markdown"}
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
    if stage != "judge":
        for key in ("project", "finding_id"):
            if task.get(key):
                if key in document and document[key] != task[key]:
                    raise ValueError("提交内容与当前任务身份不一致：" + key)
                document[key] = task[key]
        document["limitations"] = args["limitations"]
    return root / filename, document


def submit_structured(stage, root, args, task=None):
    from producer_contract import validate_bound_inputs
    from submission import submit

    root = Path(root).resolve()
    task = task if task is not None else task_context(stage, root, infer_project(root))
    schema = tool(stage)
    target = None
    prior = None
    try:
        validate(args, schema["inputSchema"])
        validate_bound_inputs(task)
        target, document = materialize(stage, root, args, task)
        # Validate the entire path before any write; rejected revisions preserve old bytes.
        cursor = root
        for part in target.relative_to(root).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("交付路径不能包含符号链接")
        prior = target.read_bytes() if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, target)
        result = submit(
            stage,
            root,
            {
                "artifact": str(target),
                "artifacts": args.get("attachments", []),
                "summary": args["summary"],
                "limitations": args["limitations"],
            },
            task=task,
        )
        if not result["success"]:
            if prior is None:
                target.unlink()
            else:
                target.write_bytes(prior)
        else:
            result["delivery_id"] = result["id"]
            result["artifact_path"] = str(target)
            # Persist the normalized tool response, not just the in-memory result.
            receipt = root / ".stage-submissions" / stage / (result["id"] + ".json")
            receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {"success": False, "decision": "needs_revision", "errors": [str(exc)]}
    result["tool"] = schema["name"]
    if not result["success"]:
        from submission_feedback import submission_feedback

        sample = submission_feedback(stage, root, target, ["格式示例"])["repair"][
            "artifact_example"
        ]
        if stage == "redteam-lab":
            sample = {"blocked": sample}
        elif stage == "visual":
            sample = {"design": sample, "image": "<实际文生图文件路径>"}
        elif stage == "redteam-agent":
            sample = {}
        sample = {k: v for k, v in sample.items() if k in schema["inputSchema"]["properties"]}
        sample.update(summary="<真实说明>", limitations=["<实际限制>"])
        result["repair"] = {
            "input_schema": schema["inputSchema"],
            "arguments_example": sample,
            "errors_to_fix": result["errors"],
            "instruction": "按字段错误修正参数并再次调用此工具；缺少真实证据时如实受阻。",
        }
        result["next_action"] = "修正后再次调用 " + schema["name"]
    return result
