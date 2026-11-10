"""Apply accepted learning-agent audit skills directly, with pinned versions and rollback."""

import hashlib
import re
import uuid
from pathlib import Path

from skill_bank import candidate_digest, now, read, write

SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {"type": "string", "enum": ["general", "project"]},
        "skill_name": {"type": "string", "pattern": "^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$"},
        "content": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "minItems": 1, "maxItems": 5, "items": {"type": "string"}},
    },
    "required": ["scope", "skill_name", "content", "evidence"],
    "additionalProperties": False,
}


def request_update(stage, root, args):
    from skill_bank import spool_proposal
    from stage_tools import validate

    validate(args, SCHEMA)
    if stage != "learner":
        raise ValueError("只有学习智能体可以安排下一轮审计技能更新")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args["skill_name"]):
        raise ValueError("技能名称只能使用字母、数字、横线和下划线")
    proposal = spool_proposal(
        "orchestrator",
        root,
        args["scope"],
        args["content"],
        args["evidence"],
        provenance={
            "change_kind": "method",
            "skill_name": args["skill_name"],
            "adoption": "next_round_direct",
        },
    )
    return {
        "success": True,
        "id": proposal["id"],
        "status": "queued_for_learning_delivery",
        "next_action": (
            "在 submit_learning 的 proposal_ids 中包含此编号；"
            "学习交付通过后下一轮直接使用，不等待评估或试用。"
        ),
    }


def apply_updates(bank, root, project):
    from submission import accepted_submissions

    root = Path(root).resolve()
    result = read(root / "rsi/learning-result.json")
    if not result:
        return {"status": "no_learning_result", "published": [], "results": []}
    delivery = accepted_submissions("learner", root)
    target = root / "rsi/learning-result.json"
    if not any(row["artifact"] == str(target) for row in delivery["deliveries"]):
        raise ValueError("正式学习结果没有通过交付工具验收")
    if result.get("project") != project:
        raise ValueError("学习结果不属于当前项目")
    if result.get("status") == "blocked":
        return {"status": "learning_blocked", "published": [], "results": []}
    ids = result.get("proposal_ids", [])
    requests = []
    for identifier in ids:
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", identifier):
            raise ValueError("学习更新编号无效")
        file = root / ".stage-skill-proposals" / (identifier + ".json")
        if file.is_symlink():
            raise ValueError("技能请求不能是符号链接")
        request = read(file)
        if not request or request.get("project") != project:
            raise ValueError("技能更新缺少本次项目的提交记录")
        requests.append(request)
    rows, published, adopted = [], [], []
    with bank.lock():
        active = bank.active()
        for request in requests:
            request_id = request["id"]
            if request.get("stage") != "orchestrator":
                rows.append(
                    {
                        "request": request_id,
                        "status": "recorded_other_stage",
                        "reason": "本次直接更新仅用于第二阶段审计技能；其他阶段建议保留记录",
                    }
                )
                continue
            publication = (
                bank.root
                / "publications"
                / (hashlib.sha256((str(root) + ":" + request_id).encode()).hexdigest() + ".json")
            )
            previous_record = read(publication)
            if previous_record:
                adopted.append(previous_record["candidate"])
                rows.append(
                    {
                        "request": request_id,
                        "candidate": previous_record["candidate"],
                        "status": "already_applied",
                    }
                )
                continue
            refs = []
            for name in request.get("evidence", []):
                file = Path(name)
                if (
                    file.is_symlink()
                    or not file.is_relative_to(root)
                    or not file.is_file()
                    or file.stat().st_size > 2 * 1024 * 1024
                ):
                    raise ValueError("技能更新证据必须属于本次学习目录")
                refs.append(
                    {
                        "path": str(file.relative_to(bank.repo)),
                        "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                    }
                )
            if not refs:
                raise ValueError("技能更新缺少证据")
            scope = request.get("scope")
            key = bank.key("orchestrator", scope, project)
            parent_id = active.get(key)
            parent = bank.candidate(parent_id) if parent_id else {}
            sections = dict(parent.get("provenance", {}).get("sections", {}))
            if not sections and parent.get("content"):
                sections["previous-audit-rules"] = parent["content"]
            provenance = request.get("provenance") or {}
            name = provenance.get("skill_name") or ("update-" + request_id)
            content = request.get("content", "").strip()
            if not content or len(content) > 12000:
                raise ValueError("技能内容需要 1—12000 个字符")
            sections[name] = content
            merged = "\n\n".join("## " + title + "\n\n" + body for title, body in sections.items())
            candidate = {
                "schema_version": 2,
                "stage": "orchestrator",
                "project": project,
                "scope": scope,
                "key": key,
                "content": merged,
                "evidence": refs,
                "conditions": request.get("conditions") or {},
                "parent": parent_id,
                "created_at": now(),
                "training_projects": sorted(set(parent.get("training_projects", [])) | {project}),
                "provenance": {
                    "adoption": "next_round_direct",
                    "change_kind": "method",
                    "sections": sections,
                    "request": request_id,
                },
            }
            candidate["id"] = candidate_digest(candidate)
            cid = candidate["id"]
            write(bank.root / "candidates" / (cid + ".json"), candidate)
            version = bank.root / "versions" / cid
            version.mkdir(parents=True, exist_ok=True)
            (version / "SKILL.md").write_text(merged + "\n")
            write(version / "manifest.json", candidate)
            previous = dict(active)
            active[key] = cid
            write(bank.root / "active.json", active)
            write(
                publication,
                {
                    "candidate": cid,
                    "previous": previous,
                    "mode": "next_round_direct",
                    "request": request_id,
                    "source_run": str(root),
                    "created_at": now(),
                },
            )
            write(
                bank.root / "imported" / (request_id + ".json"),
                {"candidate": cid, "request": request_id},
            )
            published.append(cid)
            adopted.append(cid)
            rows.append(
                {
                    "request": request_id,
                    "candidate": cid,
                    "status": "applied_next_round",
                    "scope": scope,
                    "skill_name": name,
                }
            )
        # Retire the old trial pointer; persisted workflow snapshots are not rewritten.
        trial = bank.repo / "rsi/exploration" / project / "trial.json"
        if trial.exists() and published:
            old = read(trial, {})
            write(trial.parent / "retired-direct" / (uuid.uuid4().hex + ".json"), old)
            write(trial, {})
            state_file = trial.parent / "state.json"
            state = read(state_file, {})
            if state:
                state["trial"] = None
                write(state_file, state)
    report = {
        "status": "updated_for_next_round" if adopted else "no_audit_updates",
        "adoption_mode": "next_round_direct",
        "published": published,
        "adopted": adopted,
        "results": rows,
    }
    write(root / "rsi/audit-skill-updates.json", report)
    return report
