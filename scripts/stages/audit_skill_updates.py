"""Apply accepted learning-agent audit skills directly, with pinned versions and rollback."""

import hashlib
import os
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
    provenance = {
        "change_kind": "method",
        "skill_name": args["skill_name"],
        "adoption": "next_round_direct",
    }
    if os.environ.get("STAGE_SKILL_BASELINE"):
        from skill_bank import SkillBank, infer_project
        bank = SkillBank()
        key = bank.key("orchestrator", args["scope"], infer_project(root))
        provenance["base_version"] = _visible_versions(bank).get(key)
    proposal = spool_proposal(
        "orchestrator", root, args["scope"], args["content"], args["evidence"],
        provenance=provenance,
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



def _visible_versions(bank):
    """Use the workflow's immutable baseline, just as SkillBank.render does."""
    baseline = os.environ.get("STAGE_SKILL_BASELINE")
    if not baseline:
        return bank.active()
    path = Path(baseline)
    if not path.exists() and "/rsi/" in baseline:
        path = bank.repo / "rsi" / baseline.split("/rsi/", 1)[1]
    versions = read(path)
    if not isinstance(versions, dict):
        raise ValueError("本轮技能版本快照不存在或格式无效")
    return versions


def _active_sections(bank, project, scope, versions):
    if scope not in ("general", "project"):
        raise ValueError("技能层级只能是 general 或 project")
    key = bank.key("orchestrator", scope, project)
    cid = versions.get(key)
    if not cid:
        return None
    current = bank.candidate(cid)
    sections = current.get("provenance", {}).get("sections")
    if not isinstance(sections, dict) or not sections:
        sections = {"previous-audit-rules": current["content"]}
    return cid, sections


def audit_skill_index(bank, project):
    """Return names and sizes; the agent requests only the relevant body."""
    skills = []
    versions = _visible_versions(bank)
    for scope in ("general", "project"):
        current = _active_sections(bank, project, scope, versions)
        if not current:
            continue
        cid, sections = current
        skills.append({
            "id": cid,
            "scope": scope,
            "skills": [{"name": name, "characters": len(body)}
                       for name, body in sections.items()],
        })
    return {"skills": skills, "next_action": "用 read_audit_skill 按名称读取需要优化的技能正文。"}


def read_named_audit_skill(bank, project, args):
    """Bounded reads also handle legacy single-section skills."""
    if not isinstance(args, dict):
        raise ValueError("读取参数必须是对象")
    if set(args) - {"scope", "skill_name", "offset", "length"}:
        raise ValueError("读取参数包含未知字段")
    scope, name = args.get("scope"), args.get("skill_name")
    if not isinstance(name, str) or not name:
        raise ValueError("请提供技能名称")
    offset, length = args.get("offset", 0), args.get("length", 8000)
    if type(offset) is not int or offset < 0:
        raise ValueError("读取起点必须是非负整数")
    if type(length) is not int or not 1 <= length <= 8000:
        raise ValueError("单次最多读取 8000 个字符")
    current = _active_sections(bank, project, scope, _visible_versions(bank))
    if not current:
        raise ValueError("本轮该层级没有生效的审计技能")
    cid, sections = current
    if name not in sections:
        raise ValueError("技能名称不存在，请先读取技能目录")
    body = sections[name]
    if not isinstance(body, str):
        raise ValueError("技能正文格式无效")
    end = min(len(body), offset + length)
    return {
        "id": cid, "scope": scope, "skill_name": name,
        "offset": offset, "total_characters": len(body),
        "content": body[offset:end],
        "next_offset": end if end < len(body) else None,
    }


def _write_version_text(file, body):
    """Create the immutable version before changing the active pointer."""
    temp = file.with_name(file.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(body + "\n", encoding="utf-8")
    temp.replace(file)


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
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError("学习更新编号格式无效")
    if len(ids) != len(set(ids)):
        raise ValueError("学习更新编号不能重复")
    requests = []
    for identifier in ids:
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", identifier):
            raise ValueError("学习更新编号无效")
        file = root / ".stage-skill-proposals" / (identifier + ".json")
        if file.is_symlink():
            raise ValueError("技能请求不能是符号链接")
        request = read(file)
        if not request or request.get("project") != project or request.get("id") != identifier:
            raise ValueError("技能更新缺少本次项目的提交记录")
        requests.append(request)
    rows, published, adopted, conflicts = [], [], [], []
    with bank.lock():
        active = bank.active()
        workflow_versions = _visible_versions(bank) if os.environ.get("STAGE_SKILL_BASELINE") else None
        pending_active = dict(active)
        staged = {}
        plan = []
        # All requests, evidence and final versions are validated in memory first.
        # A bad proposal cannot publish an earlier proposal from the same delivery.
        for request in requests:
            request_id = request["id"]
            if request.get("stage") != "orchestrator":
                rows.append({
                    "request": request_id,
                    "status": "recorded_other_stage",
                    "reason": "本次直接更新仅用于第二阶段审计技能；其他阶段建议保留记录",
                })
                continue
            publication = (
                bank.root / "publications" /
                (hashlib.sha256((str(root) + ":" + request_id).encode()).hexdigest() + ".json")
            )
            previous_record = read(publication)
            if previous_record:
                bank.candidate(previous_record["candidate"])
                adopted.append(previous_record["candidate"])
                rows.append({
                    "request": request_id,
                    "candidate": previous_record["candidate"],
                    "status": "already_applied",
                })
                continue
            evidence = request.get("evidence", [])
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 5:
                raise ValueError("技能更新需要 1—5 份证据")
            refs = []
            for path in evidence:
                if not isinstance(path, str):
                    raise ValueError("技能证据路径格式无效")
                file = Path(path)
                if (
                    file.is_symlink()
                    or not file.is_relative_to(root)
                    or not file.is_file()
                    or file.stat().st_size > 2 * 1024 * 1024
                ):
                    raise ValueError("技能更新证据必须属于本次学习目录")
                refs.append({
                    "path": str(file.relative_to(bank.repo)),
                    "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                })
            scope = request.get("scope")
            key = bank.key("orchestrator", scope, project)
            parent_id = pending_active.get(key)
            parent = staged.get(parent_id) or (bank.candidate(parent_id) if parent_id else {})
            sections = dict(parent.get("provenance", {}).get("sections", {}))
            if not sections and parent.get("content"):
                sections["previous-audit-rules"] = parent["content"]
            provenance = request.get("provenance") or {}
            if not isinstance(provenance, dict):
                raise ValueError("技能来源格式无效")
            name = provenance.get("skill_name") or ("update-" + request_id)
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name):
                raise ValueError("技能名称只能使用字母、数字、横线和下划线")
            content = request.get("content")
            if not isinstance(content, str):
                raise ValueError("技能正文格式无效")
            content = content.strip()
            if not content or len(content) > 12000:
                raise ValueError("技能内容需要 1—12000 个字符")
            has_baseline = "base_version" in provenance or workflow_versions is not None
            if has_baseline:
                base_id = provenance.get("base_version") if "base_version" in provenance else workflow_versions.get(key)
                if base_id is not None and (not isinstance(base_id, str) or not re.fullmatch(r"[a-f0-9]{64}", base_id)):
                    raise ValueError("审计技能基线版本无效")
                current_id = active.get(key)
                if base_id != current_id:
                    base = bank.candidate(base_id) if base_id else {}
                    current = bank.candidate(current_id) if current_id else {}
                    base_sections = base.get("provenance", {}).get("sections")
                    if not isinstance(base_sections, dict):
                        base_sections = {"previous-audit-rules": base["content"]} if base.get("content") else {}
                    current_sections = current.get("provenance", {}).get("sections")
                    if not isinstance(current_sections, dict):
                        current_sections = {"previous-audit-rules": current["content"]} if current.get("content") else {}
                    if base_sections.get(name) != current_sections.get(name):
                        conflict = {
                            "request": request_id,
                            "status": "concurrent_skill_conflict",
                            "scope": scope,
                            "skill_name": name,
                            "baseline_version": base_id,
                            "current_version": current_id,
                            "reason": "同名技能已被其他工作流更新；本次未覆盖现行版本",
                        }
                        conflicts.append(conflict)
                        rows.append(conflict)
                        continue
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
            existing = bank.root / "candidates" / (cid + ".json")
            if existing.exists() and bank.candidate(cid)["content"] != merged:
                raise ValueError("技能版本内容摘要冲突")
            previous = dict(pending_active)
            pending_active[key] = cid
            staged[cid] = candidate
            plan.append((request_id, candidate, publication, previous, name, scope))
            published.append(cid)
            adopted.append(cid)
            rows.append({
                "request": request_id, "candidate": cid,
                "status": "applied_next_round", "scope": scope, "skill_name": name,
            })
        # Prepare every immutable version before one atomic active.json replacement.
        for request_id, candidate, publication, previous, name, scope in plan:
            cid = candidate["id"]
            write(bank.root / "candidates" / (cid + ".json"), candidate)
            version = bank.root / "versions" / cid
            version.mkdir(parents=True, exist_ok=True)
            _write_version_text(version / "SKILL.md", candidate["content"])
            write(version / "manifest.json", candidate)
        if plan:
            write(bank.root / "active.json", pending_active)
        for request_id, candidate, publication, previous, name, scope in plan:
            cid = candidate["id"]
            write(publication, {
                "candidate": cid, "previous": previous,
                "mode": "next_round_direct", "request": request_id,
                "source_run": str(root), "created_at": now(),
            })
            write(bank.root / "imported" / (request_id + ".json"),
                  {"candidate": cid, "request": request_id})
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
        "published": published, "adopted": adopted,
        "conflicts": conflicts, "results": rows,
    }
    write(root / "rsi/audit-skill-updates.json", report)
    return report
