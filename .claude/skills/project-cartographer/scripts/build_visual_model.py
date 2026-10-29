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
