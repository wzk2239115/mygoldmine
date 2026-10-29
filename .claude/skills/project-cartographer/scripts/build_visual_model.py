#!/usr/bin/env python3
import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target", ".next", ".turbo", "coverage"}
DEFAULT_STAGES = [
    "workspace_scan", "project_profile", "route_auth", "access_control",
    "ssrf_analysis", "general_code_security", "model_loading", "deserialization",
    "path_traversal", "sensitive_info", "agent_config", "combination_analysis", "final_crosscheck",
]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def latest_run(project):
    runs = []
    for rd in (ROOT / "runs" / project).glob("*"):
        if not (rd / "audit-report.json").exists():
            continue
        meta = load_json(rd / "run-meta.json", {}) or {}
        if meta.get("reports_complete") is True and meta.get("exit_code") == 0:
            runs.append((meta.get("ended_at") or "", rd))
    return sorted(runs)[-1][1] if runs else None


def project_meta(project):
    manifest = load_json(ROOT / "catalog" / "manifest.json", {}) or {}
    item = (manifest.get("projects") or {}).get(project) or {}
    return {
        "name": item.get("name") or project,
        "audit_id": item.get("audit_id") or "",
        "direction": item.get("direction") or "",
        "source": str(ROOT / (item.get("path") or f"targets/{project}")),
        "url": item.get("url") or "",
        "commit": item.get("commit") or "",
    }


def source_top_dirs(source):
    root = Path(source)
    result = []
    if not root.is_dir():
        return result
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        count = 0
        for current, dirs, files in os.walk(entry):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            count += len(files)
            if count > 20000:
                break
        result.append((entry.name, count))
    return result


def finding_paths(finding):
    values = []
    for key in ("evidence", "files", "location"):
        value = finding.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    result = []
    for item in values:
        if isinstance(item, dict):
            item = item.get("path") or item.get("file") or item.get("location") or ""
        text = str(item).split(":")[0].strip().replace("\\", "/").strip("/")
        if text:
            result.append(text)
    return result


def finding_status(finding):
    severity = str(finding.get("severity") or finding.get("severity_raw") or "unknown").lower().split()[0]
    verdict = str(finding.get("verdict") or finding.get("status") or "").lower()
    if verdict in ("fp", "false-positive", "duplicate"):
        return "closed"
    if severity in ("critical", "high"):
        return severity
    return severity


def make_node(node_id, label, kind, status="scope", **extra):
    node = {"id": node_id, "label": label, "kind": kind, "status": status, "children": []}
    node.update(extra)
    return node


def add_child(parent, node):
    for child in parent["children"]:
        if child["id"] == node["id"]:
            return child
    parent["children"].append(node)
    return node


def build_project_tree(project, meta, findings, source):
    root = make_node(f"project:{project}", meta["name"], "root", "root", project=project)
    domains = {}
    for name, count in source_top_dirs(source):
        node = make_node(f"dir:{name}", name, "domain", "scope", files=count, path=name)
        domains[name] = node
        add_child(root, node)
    findings_branch = make_node("dir:findings", "findings", "domain", "scope", files=0, path="findings")
    for finding in findings:
        paths = finding_paths(finding)
        parts = [part for part in (paths[0].split("/") if paths else []) if part]
        top = parts[0] if parts else "findings"
        parent = domains.get(top) or findings_branch
        path_parts = parts[1:3]
        cursor = parent
        for part in path_parts:
            cursor = add_child(cursor, make_node(f"dir:{top}/{part}", part, "module", "scope", path="/".join([top, part])))
        fid = str(finding.get("id") or "finding")
        node = make_node(
            f"finding:{fid}", str(finding.get("title") or fid)[:110], "finding",
            finding_status(finding), finding_id=fid,
            severity=str(finding.get("severity") or "unknown").lower(),
            cve_tier=finding.get("cveTier"),
            note=str(finding.get("verdict") or ""),
            path=paths[0] if paths else "",
        )
        add_child(cursor, node)
    if findings_branch["children"] and not any(child["id"] == "dir:findings" for child in root["children"]):
        add_child(root, findings_branch)
    return root


def stage_for(category):
    text = str(category or "").lower()
    if "ssrf" in text or "egress" in text:
        return "ssrf_analysis"
    if "deserial" in text or "pickle" in text or "model" in text:
        return "model_loading"
    if "path" in text or "traversal" in text:
        return "path_traversal"
    if "auth" in text or "access" in text or "permission" in text:
        return "access_control"
    if "secret" in text or "credential" in text or "sensitive" in text:
        return "sensitive_info"
    if "agent" in text or "mcp" in text or "config" in text:
        return "agent_config"
    return "general_code_security"


def build_coverage_tree(project, report, findings):
    coverage = report.get("coverage") if isinstance(report.get("coverage"), dict) else {}
    stages = coverage.get("stages") if isinstance(coverage.get("stages"), dict) else {}
    names = list(stages) or DEFAULT_STAGES
    root = make_node(f"coverage:{project}", "Audit coverage", "root", "root", project=project)
    nodes = {}
    for name in names:
        raw = stages.get(name)
        status = "covered" if raw not in (None, "", "unknown", False) else "unknown"
        node = make_node(f"stage:{name}", name.replace("_", " "), "stage", status, raw=raw)
        nodes[name] = node
        add_child(root, node)
    for finding in findings:
        name = stage_for(finding.get("category") or finding.get("title"))
        parent = nodes.get(name) or nodes.get(DEFAULT_STAGES[5])
        fid = str(finding.get("id") or "finding")
        node = make_node(
            f"coverage-finding:{fid}", str(finding.get("title") or fid)[:110], "finding",
            finding_status(finding), finding_id=fid,
            severity=str(finding.get("severity") or "unknown").lower(),
            category=str(finding.get("category") or ""),
            note=str(finding.get("verdict") or ""),
        )
        add_child(parent, node)
    return root


def compact(value, limit=120):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def scene_kind(finding):
    title = str(finding.get("title") or "").lower()
    text = " ".join(
        str(finding.get(key) or "")
        for key in ("title", "category", "root_cause", "impact", "reproduction", "reproduction_idea")
    ).lower()
    if re.search(r"pickle|deserial|torch\.load|weights_only|trust_remote_code|checkpoint", text):
        return "deserialization"
    if re.search(r"command execution|code execution|rce|remote code|nsenter", title):
        return "rce"
    if re.search(r"unauthenticated|authentication|auth bypass|api[-_ ]?key|credential", title):
        return "auth"
    if re.search(r"ssrf|server-side request|fetch|redirect|egress", text):
        return "ssrf"
    if re.search(r"path traversal|arbitrary file|file read|file write|workspace confine", text):
        return "path"
    if re.search(r"rce|command|shell|exec\(|spawn|code execution|nsenter", text):
        return "rce"
    if re.search(r"auth|unauthenticated|api[-_ ]?key|bearer|token|bypass|permission", text):
        return "auth"
    if re.search(r"plugin|mcp|agent|hook|skill|config|environment", text):
        return "agent"
    if re.search(r"secret|credential|sensitive|disclos|exfiltrat|leak", text):
        return "secret"
    return "generic"


def scene_variant(finding, kind):
    text = " ".join(str(finding.get(key) or "") for key in ("title", "impact", "root_cause")).lower()
    if re.search(r"credential|api[-_ ]?key|token|takeover", text):
        return "credential takeover"
    if re.search(r"reset|restart|stop.*process|denial", text):
        return "runtime reset"
    if re.search(r"cross-tenant|cross-sandbox|workspace escape|host file", text):
        return "cross-boundary access"
    if re.search(r"plugin|mcp|agent|hook", text):
        return "agent tool execution"
    if re.search(r"secret|exfiltrat|disclos|leak", text):
        return "data exposure"
    if kind == "ssrf":
        return "internal network access"
    if kind == "deserialization":
        return "malicious model loading"
    if kind == "auth":
        return "authentication bypass"
    return "privileged sink reachability"


def scene_visual(kind):
    return {
        "rce": "left attacker supplies a crafted command or configuration, right service executes it inside a sandbox runtime",
        "auth": "left attacker sends a request without valid credentials, right gateway accepts and forwards it to a privileged API",
        "ssrf": "left attacker supplies a URL, right service fetches an internal resource and returns it",
        "deserialization": "left attacker supplies a malicious model or checkpoint, right loader deserializes it and runs code",
        "path": "left attacker supplies a path, right service reads or writes outside the intended workspace",
        "agent": "left attacker plants a plugin or configuration, right agent loads it and executes a tool",
        "secret": "left attacker reads a response, right service leaks a token or sensitive record",
        "generic": "left attacker sends crafted input across a trust boundary, right service processes it at a privileged sink",
    }[kind]


def build_scene(finding, kind):
    paths = finding_paths(finding)
    evidence_paths = []
    for item in finding.get("evidence") or []:
        if isinstance(item, dict):
            value = item.get("path") or item.get("file") or ""
        else:
            value = str(item or "")
        value = value.split(":")[0].strip()
        if value:
            evidence_paths.append(value)
    paths = list(dict.fromkeys(paths + evidence_paths))
    boundary = compact(finding.get("boundary") or (paths[0] if paths else "未标注边界"), 100)
    preconditions = finding.get("preconditions") or []
    if isinstance(preconditions, str):
        preconditions = [preconditions]
    precondition = compact(preconditions[0], 100) if preconditions else compact(finding.get("reachability") or "默认可达", 100)
    flow_text = finding.get("source_to_sink") or finding.get("reproduction_idea") or finding.get("repro_idea") or finding.get("root_cause") or ""
    flow = [compact(part, 150) for part in re.split(r"\s*->\s*", str(flow_text)) if str(part).strip()]
    root = compact(finding.get("root_cause") or finding.get("title") or "处理不可信输入", 120)
    impact = compact(finding.get("impact") or finding.get("title") or "影响以报告为准", 120)
    repro = compact(finding.get("repro_idea") or finding.get("reproduction_idea") or "", 150)
    attacker = [
        f"向 {boundary} 发送构造请求",
        f"输入：{repro}" if repro else f"满足前置条件：{precondition}",
        f"读取结果：{impact}",
    ]
    if flow:
        victim = [
            flow[0],
            " -> ".join(flow[1:3]) if len(flow) > 1 else root,
            " -> ".join(flow[3:]) if len(flow) > 3 else flow[-1],
        ]
    else:
        victim = [
            f"在 {boundary} 接收并解析输入",
            f"沿 {root} 进入敏感路径",
            f"到达 sink，造成 {impact}",
        ]
    return {
        "kind": kind,
        "variant": scene_variant(finding, kind),
        "entry": boundary,
        "boundary": boundary,
        "precondition": precondition,
        "reachability": compact(finding.get("reachability") or "unknown", 40),
        "result": impact,
        "attacker": attacker,
        "victim": victim,
        "flow": flow[:5],
        "visual": scene_visual(kind),
        "evidence": paths[:6],
        "disclaimer": "场景由 finding 字段生成，用于解释；不是新的漏洞结论",
    }


def build_attack_tree(project, finding, index):
    fid = str(finding.get("id") or f"finding-{index}")
    title = str(finding.get("title") or fid)
    root = make_node(f"attack:{fid}", title[:100], "goal", "critical" if str(finding.get("severity", "")).lower() == "critical" else "high", finding_id=fid)
    entry_label = "entry / attacker"
    paths = finding_paths(finding)
    if paths:
        entry_label = paths[0]
    entry = make_node(f"attack:{fid}:entry", entry_label, "entry", "scope", path=paths[0] if paths else "")
    add_child(root, entry)
    preconditions = finding.get("preconditions") or []
    if isinstance(preconditions, str):
        preconditions = [preconditions]
    gate = make_node(f"attack:{fid}:gate", "auth / preconditions", "precondition", "gate")
    add_child(entry, gate)
    for precondition in preconditions[:4]:
        add_child(gate, make_node(f"attack:{fid}:pre:{len(gate['children'])}", str(precondition)[:100], "precondition", "gate"))
    sink = make_node(f"attack:{fid}:sink", str(finding.get("root_cause") or "sink")[:120], "sink", "sink", path=paths[-1] if paths else "")
    add_child(gate, sink)
    impact = make_node(f"attack:{fid}:impact", str(finding.get("impact") or "impact")[:120], "impact", "impact")
    add_child(sink, impact)
    kind = scene_kind(finding)
    root["scene"] = build_scene(finding, kind)
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--cover", default="")
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else latest_run(args.project)
    if not run_dir or not (run_dir / "audit-report.json").exists():
        raise SystemExit(f"no report for project: {args.project}")
    report = load_json(run_dir / "audit-report.json", {}) or {}
    meta = project_meta(args.project)
    findings = report.get("findings") or report.get("vulnerabilities") or []
    project_tree = build_project_tree(args.project, meta, findings, meta["source"])
    coverage_tree = build_coverage_tree(args.project, report, findings)
    attack_trees = [
        build_attack_tree(args.project, finding, index)
        for index, finding in enumerate(findings)
        if str(finding.get("severity") or "").lower() in ("critical", "high")
    ][:12]
    cover = args.cover or ""
    if not cover:
        local_cover = run_dir / "visual" / "cover.webp"
        if local_cover.exists():
            cover = str(local_cover)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": args.project,
        "project_name": meta["name"],
        "audit_id": meta["audit_id"],
        "direction": meta["direction"],
        "run_dir": str(run_dir),
        "run_id": run_dir.name,
        "source": meta["source"],
        "url": meta["url"],
        "commit": meta["commit"],
        "cover": cover,
        "trees": {
            "project": project_tree,
            "coverage": coverage_tree,
            "attacks": attack_trees,
        },
        "counts": {
            "findings": len(findings),
            "critical": sum(1 for f in findings if str(f.get("severity", "")).lower() == "critical"),
            "high": sum(1 for f in findings if str(f.get("severity", "")).lower() == "high"),
        },
    }
    out = Path(args.out) if args.out else run_dir / "visual" / "visual-model.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "project": args.project, "run_id": run_dir.name, "findings": len(findings), "attacks": len(attack_trees)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
