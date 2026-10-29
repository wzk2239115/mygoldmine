#!/usr/bin/env python3
import argparse
import html
import json
import shutil
from pathlib import Path

COLORS = {
    "root": "#1c1b16", "scope": "#e4dccb", "covered": "#4b654d", "unknown": "#b9af99",
    "critical": "#b23a2b", "high": "#c05d2c", "medium": "#a66a18", "low": "#3e596f",
    "info": "#746c5b", "closed": "#8f8674", "gate": "#a66a18", "sink": "#b23a2b",
    "impact": "#8e2b20", "goal": "#1c1b16", "entry": "#3e596f", "precondition": "#a66a18",
}


def esc(value):
    return html.escape(str(value or ""), quote=True)


def fit(value, length=30):
    text = str(value or "")
    return text if len(text) <= length else text[: length - 1] + "…"


def collect(root, depth=0, max_depth=8, max_nodes=500, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > max_nodes or depth > max_depth:
        return []
    rows = [(root, depth)]
    for child in root.get("children") or []:
        rows.extend(collect(child, depth + 1, max_depth, max_nodes, counter))
    return rows


def layout(root, max_depth=8, max_nodes=500):
    nodes = collect(root, max_depth=max_depth, max_nodes=max_nodes)
    leaf_index = [0]
    positions = {}
    by_id = {node["id"]: (node, depth) for node, depth in nodes}

    def walk(node, depth):
        children = [child for child in node.get("children") or [] if child["id"] in by_id]
        if not children or depth >= max_depth:
            y = leaf_index[0]
            leaf_index[0] += 1
        else:
            ys = [walk(child, depth + 1) for child in children]
            y = sum(ys) / len(ys)
        positions[node["id"]] = (depth, y)
        return y

    walk(root, 0)
    return nodes, positions, by_id


def svg_tree(root, title, out, max_depth=8, max_nodes=500):
    nodes, positions, by_id = layout(root, max_depth, max_nodes)
    leaf_count = max(1, len([1 for node, _ in nodes if not [c for c in node.get("children") or [] if c["id"] in by_id]]))
    width = 260 + max((depth for depth, _ in positions.values()), default=0) * 220
    height = 110 + leaf_count * 38
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#eee8da"/>',
        '<style>text{font-family:Inter,"Noto Sans CJK SC","Microsoft YaHei",sans-serif;fill:#1c1b16} .edge{fill:none;stroke:#746c5b;stroke-width:1.2;opacity:.55}.node{stroke:#403c32;stroke-width:1}.label{font-size:11px}.sub{font-size:8px;fill:#746c5b}.title{font-size:18px;font-weight:700;letter-spacing:-.02em}</style>',
        f'<text x="28" y="34" class="title">{esc(title)}</text>',
    ]
    for parent in nodes:
        pnode, pdepth = parent
        for child in pnode.get("children") or []:
            if child["id"] not in positions:
                continue
            x1, y1 = positions[pnode["id"]]
            x2, y2 = positions[child["id"]]
            parts.append(f'<path class="edge" d="M{x1+190:.1f},{y1*38+68:.1f} C{x1+205:.1f},{y1*38+68:.1f} {x2-18:.1f},{y2*38+68:.1f} {x2:.1f},{y2*38+68:.1f}"/>')
    for node, depth in nodes:
        x, y = positions[node["id"]]
        px = 28 + x * 220
        py = y * 38 + 58
        status = node.get("status") or "scope"
        color = COLORS.get(status, COLORS["scope"])
        if node.get("kind") == "finding":
            color = COLORS.get(str(node.get("severity") or status).lower(), COLORS["info"])
        fill = color if node.get("kind") in ("finding", "goal", "impact") else "#fbf7ed"
        text_color = "#fff8ec" if fill != "#fbf7ed" else "#1c1b16"
        parts.append(f'<rect class="node" x="{px}" y="{py}" width="190" height="28" rx="1" fill="{fill}"/>')
        parts.append(f'<text x="{px+7}" y="{py+14}" class="label" fill="{text_color}">{esc(fit(node.get("label"), 29))}</text>')
        kind = node.get("kind") or ""
        extra = node.get("path") or node.get("finding_id") or node.get("files") or ""
        if extra:
            parts.append(f'<text x="{px+7}" y="{py+24}" class="sub" fill="{text_color}" opacity=".72">{esc(fit(extra, 34))}</text>')
    parts.append(f'<text x="28" y="{height-18}" class="sub">nodes={len(nodes)} · status colors: critical/high/medium/low · grey=scope</text>')
    parts.append('</svg>')
    Path(out).write_text("\n".join(parts), encoding="utf-8")


def render_report(model, run_dir, out_dir):
    out_dir = Path(out_dir)
    project = model.get("project_name") or model.get("project")
    cover = model.get("cover") or ""
    cover_path = Path(cover) if cover else None
    local_cover = ""
    if cover_path and cover_path.exists():
        target = out_dir / "cover.webp"
        shutil.copyfile(cover_path, target)
        local_cover = "cover.webp"
    lines = [
        f"# {project} — Audit Illustrated",
        "",
        f"- project: `{model.get('project')}`",
        f"- audit id: `{model.get('audit_id')}`",
        f"- direction: `{model.get('direction')}`",
        f"- run: `{model.get('run_id')}`",
        f"- commit: `{model.get('commit')}`",
        f"- source: `{model.get('source')}`",
        f"- findings: {model.get('counts', {}).get('findings', 0)}",
        "",
    ]
    if local_cover:
        lines += [f"![{project} cover]({local_cover})", ""]
    lines += [
        "## 1. 项目结构",
        "",
        "![project map](project-map.svg)",
        "",
        "这张树按源码目录与 finding 证据路径生成。节点越大，代表该目录承载的文件越多；红色叶子是 finding。",
        "",
        "## 2. AI 审计覆盖",
        "",
        "![coverage tree](coverage-tree.svg)",
        "",
        "覆盖树按审计阶段和 finding 类别生成；灰色节点表示报告没有给出明确覆盖状态。",
        "",
        "## 3. 攻击路径",
        "",
    ]
    for attack in model.get("trees", {}).get("attacks", [])[:8]:
        fid = attack.get("finding_id") or attack.get("id", "finding").split(":")[-1]
        svg = f"attack-{fid}.svg"
        lines += [f"### {fid} — {attack.get('label', '')}", "", f"![attack path]({svg})", ""]
    lines += ["## 4. 结果表", "", "| Finding | Severity | Status | Path |", "|---|---|---|---|"]
    leaves = []

    def walk(node):
        if node.get("kind") == "finding":
            leaves.append(node)
        for child in node.get("children") or []:
            walk(child)

    walk(model.get("trees", {}).get("project", {}))
    for node in leaves:
        lines.append(f"| `{node.get('finding_id')}` | {node.get('severity')} | {node.get('status')} | `{node.get('path')}` |")
    lines += ["", "> 本报告中的结构/覆盖/攻击路径图由数据和代码生成；封面为 image2 生成插图，不作为漏洞证据。", ""]
    (out_dir / "report-illustrated.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max-depth", type=int, default=8)
    args = parser.parse_args()
    model_path = Path(args.model)
    model = json.loads(model_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir) if args.out_dir else model_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    trees = model.get("trees") or {}
    svg_tree(trees.get("project", {}), f"{model.get('project_name', 'project')} / structure", out_dir / "project-map.svg", args.max_depth)
    svg_tree(trees.get("coverage", {}), "Audit coverage", out_dir / "coverage-tree.svg", args.max_depth)
    for attack in trees.get("attacks", [])[:12]:
        fid = attack.get("finding_id") or attack.get("id", "finding").split(":")[-1]
        svg_tree(attack, f"Attack path / {fid}", out_dir / f"attack-{fid}.svg", 8, 80)
    render_report(model, model_path.parent, out_dir)
    print(json.dumps({"out_dir": str(out_dir), "diagrams": 2 + min(12, len(trees.get('attacks', []))), "report": str(out_dir / "report-illustrated.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
