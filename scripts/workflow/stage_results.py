# Bind latest stage results to the exact audit occurrence.
import hashlib
import json
from pathlib import Path
import sys


def read(file):
    try:
        return json.loads(Path(file).read_text())
    except (OSError, ValueError):
        return {}


def inside(file, root):
    file = Path(file)
    if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
        raise ValueError("阶段产物缺失、越界或使用符号链接")
    return file.resolve()


def batch(run, project, node):
    folder = Path(str(run) + ".meta/node-retries") / node
    attempts = sorted((item for f in folder.glob("*/attempt.json")
                       if isinstance(item := read(f), dict) and item),
                      key=lambda x: str(x.get("startedAt") or ""))
    if not attempts:
        return None, {"status": "not_run", "reason": "本候选尚无阶段记录"}
    job = attempts[-1]
    if job.get("project") != project or job.get("runId") != run.name:
        return None, {"status": "invalid", "reason": "阶段批次与项目或运行不一致"}
    if job.get("status") != "completed":
        return None, {"status": job.get("status") or "failed",
                      "reason": job.get("error") or "最新批次未完成，不使用旧结果"}
    try:
        workspace = Path(job["workspace"]).resolve()
        if not workspace.is_relative_to(folder.resolve()):
            raise ValueError("阶段输出目录越界")
        report = inside(workspace / "audit-report.json", workspace)
        if report.read_bytes() != (run / "audit-report.json").read_bytes():
            raise ValueError("阶段使用的审计报告版本已过期")
    except (KeyError, OSError, ValueError) as exc:
        return None, {"status": "stale", "reason": str(exc)}
    return workspace, {"status": "not_selected", "reason": "本候选未进入当前阶段",
                       "attemptId": job.get("id")}


def build_stage_results(latest, root, runs):
    root, runs = Path(root), Path(runs)
    sys.path.insert(0, str(root / "scripts/redteam"))
    from contracts import ContractError, recompute_flag_provenance, validate_verdict

    states, groups = {}, {}
    for key, item in latest.items():
        groups.setdefault((item["project"], item["run_id"]), {}).setdefault(
            str(item["finding_id"]).upper(), []).append(key)
    for (project, run_id), candidates in groups.items():
        identities = {identifier: keys[0] for identifier, keys in candidates.items()
                      if len(keys) == 1}
        for keys in candidates.values():
            if len(keys) <= 1:
                continue
            for key in keys:
                states[key] = {"stageResults": {
                    stage: {"status": "identity_ambiguous",
                            "reason": "当前报告中候选编号不唯一，不猜测关联"}
                    for stage in ("blue", "red", "judge")}}

        run, contexts = runs / project / run_id, {}
        for node, name, relative in [
            ("verify", "blue", "verify/agent/summary.json"),
            ("redteam-agent", "red", "redteam/summary.json"),
            ("judge", "judge", "judge/summary.json"),
        ]:
            workspace, default = batch(run, project, node)
            contexts[name] = (workspace, relative)
            for key in identities.values():
                states.setdefault(key, {"stageResults": {}})["stageResults"][name] = dict(default)
            if workspace is None:
                continue
            summary_file = workspace / relative
            try:
                summary = read(inside(summary_file, workspace))
            except ValueError:
                continue
            rows = summary.get("findings" if name == "blue" else "results") or []
            seen = set()
            for row in rows:
                identifier = str(row.get("finding_id") or row.get("id") or "").upper()
                key = identities.get(identifier)
                if not key:
                    continue
                if identifier in seen:
                    states[key]["stageResults"][name] = {
                        "status": "evidence_invalid", "reason": "阶段汇总存在重复候选编号"}
                    continue
                seen.add(identifier)
                result = {"status": row.get("verdict") if name == "blue" else row.get("status"),
                          "reason": row.get("reason") or row.get("error") or "",
                          "attemptId": default.get("attemptId"),
                          "artifact": summary_file.relative_to(root).as_posix()}
                try:
                    if name == "blue" and result["status"] == "confirmed":
                        document = inside(row.get("report_path") or "", workspace)
                        report = read(document)
                        if (report.get("project") != project
                                or str(report.get("finding_id") or "").upper() != identifier
                                or report.get("verdict") != "confirmed"
                                or report.get("evidence_class") != "runtime"
                                or report.get("synthesized")):
                            raise ValueError("蓝队确认缺少匹配的运行时报告")
                        result["artifact"] = document.relative_to(root).as_posix()
                    elif name == "red" and result["status"] == "flag_captured":
                        if states[key]["stageResults"]["blue"].get("status") != "confirmed":
                            raise ValueError("当前蓝队批次尚未确认，旧红队结果不用于当前候选")
                        document = inside(Path(row.get("run_dir") or "") / "result.json", workspace)
                        data = read(document)
                        finding = read(document.parent / "finding.json")
                        if (data.get("project") != project
                                or str(finding.get("id") or finding.get("finding_id")).upper()
                                != identifier):
                            raise ValueError("红队结果的项目或候选编号不匹配")
                        proof = recompute_flag_provenance(document.parent, data)
                        result.update(provenanceVerified=True, evidenceHash=proof["flag_sha256"],
                                      artifact=document.relative_to(root).as_posix())
                    elif name == "judge":
                        document = inside(Path(row.get("run_dir") or "") / "result.json", workspace)
                        data = read(document)
                        finding = read(document.parent / "finding.json")
                        if (data.get("project") != project
                                or str(finding.get("id") or finding.get("finding_id")).upper()
                                != identifier):
                            raise ValueError("审核结果的项目或候选编号不匹配")
                        verdict = data.get("judge") or {}
                        validate_verdict(verdict)
                        actual = "judge_" + str(verdict.get("verdict") or "")
                        if actual != result["status"]:
                            raise ValueError("审核汇总与独立审核报告不一致")
                        result.update(reason=verdict.get("reason") or result["reason"],
                                      artifact=document.relative_to(root).as_posix())
                        if actual == "judge_approved":
                            proof = recompute_flag_provenance(document.parent, data)
                            red = states[key]["stageResults"]["red"]
                            if (data.get("flag_provenance_verified") != proof
                                    or not red.get("provenanceVerified")
                                    or red.get("evidenceHash") != proof["flag_sha256"]):
                                raise ValueError("独立审核与当前红队批次的证据不一致")
                            result["provenanceVerified"] = True
                    inputs = read(workspace / "workflow-inputs.json")
                    upstreams = ["blue"] if name == "red" else (
                        ["blue", "red"] if name == "judge" else [])
                    for upstream in upstreams:
                        source, source_relative = contexts[upstream]
                        if not inputs:
                            continue
                        if source is None:
                            raise ValueError("最新上游阶段未完成，旧结果不用于当前候选")
                        source_file = source / source_relative
                        entry = next((item for item in inputs.get("artifacts") or []
                                      if Path(item.get("file") or "").resolve()
                                      == source_file.resolve()), None)
                        actual_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
                        if not entry or entry.get("sha256") != actual_hash:
                            raise ValueError("上游阶段批次已变化，旧结果不用于当前候选")
                except (OSError, ValueError, ContractError) as exc:
                    result.update(status="evidence_invalid", reason=str(exc),
                                  provenanceVerified=False)
                states[key]["stageResults"][name] = result
    return states
