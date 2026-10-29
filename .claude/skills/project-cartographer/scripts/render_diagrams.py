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


def load_director(out_dir, fid):
    path = Path(out_dir) / f"scene-{fid}.director.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def director_storyboard(director):
    story = (director or {}).get("storyboard") or {}
    attacker = story.get("attacker") or {}
    victim = story.get("victim") or {}
    return {
        "trust_boundary": story.get("trust_boundary") or "",
        "attacker": attacker.get("steps") or [],
        "victim": victim.get("steps") or [],
        "caption": story.get("caption") or "",
        "visual_metaphor": story.get("visual_metaphor") or "",
    }


def wrap_text(value, width=28, max_lines=4):
    text = str(value or "").strip()
    if not text:
        return ["—"]
    lines = []
    current = ""
    for char in text:
        current += char
        if len(current) >= width:
            lines.append(current)
            current = ""
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) >= max_lines and len("".join(lines)) < len(text):
        lines[-1] = lines[-1][: max(1, width - 1)] + "…"
    return lines


def svg_scene(attack, out):
    fid = attack.get("finding_id") or attack.get("id", "finding").split(":")[-1]
    scene = attack.get("scene") or {}
    title = fit(attack.get("label") or fid, 78)
    severity = str(attack.get("status") or "high")
    color = COLORS.get(severity, COLORS["high"])
    kind = str(scene.get("kind") or "generic")
    attacker = scene.get("attacker") or ["构造输入"]
    victim = scene.get("victim") or ["处理输入"]
    entry = fit(scene.get("entry") or "未标注入口", 54)
    result = fit(scene.get("result") or "影响以报告为准", 62)
    width, height = 1160, 720
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#eee8da"/>',
        '<style>text{font-family:Inter,"Noto Sans CJK SC","Microsoft YaHei",sans-serif;fill:#1c1b16}.title{font-size:22px;font-weight:700;letter-spacing:-.02em}.kicker{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.08em;fill:#746c5b}.h{font-size:13px;font-weight:700}.step{font-size:12px}.sub{font-size:10px;fill:#746c5b}.num{font-family:ui-monospace,monospace;font-size:11px;font-weight:700;fill:#fff8ec}.box{stroke:#403c32;stroke-width:1}.dash{fill:none;stroke:#a66a18;stroke-width:1.5;stroke-dasharray:5 5}.arrow{fill:none;stroke:#b23a2b;stroke-width:1.6}</style>',
        f'<rect x="26" y="22" width="8" height="62" fill="{color}"/>',
        f'<text x="48" y="43" class="kicker">ATTACK SCENE / {esc(fid)} / {esc(kind)}</text>',
        f'<text x="48" y="70" class="title">{esc(title)}</text>',
        f'<text x="48" y="94" class="sub">入口：{esc(entry)} · 图示由 finding 字段生成，作为解释层，不是新结论</text>',
        '<rect x="48" y="126" width="300" height="456" fill="#fbf7ed" class="box"/>',
        '<rect x="812" y="126" width="300" height="456" fill="#fbf7ed" class="box"/>',
        '<rect x="388" y="126" width="384" height="456" fill="none" stroke="#a66a18" stroke-width="1.5" stroke-dasharray="7 6"/>',
        '<text x="66" y="154" class="h">攻击者 / ATTACKER</text>',
        '<text x="830" y="154" class="h">受害者 / VICTIM</text>',
        '<text x="548" y="154" class="h">信任边界</text>',
        f'<text x="548" y="174" class="sub">entry · {esc(entry)}</text>',
    ]
    for index, step in enumerate(attacker[:4]):
        y = 192 + index * 92
        parts.append(f'<rect x="66" y="{y}" width="22" height="22" fill="{color}"/>')
        parts.append(f'<text x="72" y="{y+15}" class="num">{index+1}</text>')
        for line_index, line in enumerate(wrap_text(step, 30, 3)):
            parts.append(f'<text x="98" y="{y+13+line_index*16}" class="step">{esc(line)}</text>')
    for index, step in enumerate(victim[:4]):
        y = 192 + index * 92
        parts.append(f'<rect x="830" y="{y}" width="22" height="22" fill="{color}"/>')
        parts.append(f'<text x="836" y="{y+15}" class="num">{index+1}</text>')
        for line_index, line in enumerate(wrap_text(step, 30, 3)):
            parts.append(f'<text x="862" y="{y+13+line_index*16}" class="step">{esc(line)}</text>')
    for index in range(min(len(attacker), len(victim), 4)):
        y1 = 227 + index * 92
        y2 = 227 + index * 92
        parts.append(f'<path class="arrow" d="M348,{y1} C430,{y1} 500,{y2} 388,{y2}"/>')
        parts.append(f'<path class="arrow" d="M772,{y2} C690,{y2} 620,{y1} 812,{y1}"/>')
    parts += [
        '<rect x="48" y="602" width="1064" height="72" fill="#fbf7ed" class="box"/>',
        '<text x="66" y="626" class="kicker">IMPACT / RESULT</text>',
        f'<text x="66" y="651" class="step">{esc(result)}</text>',
        f'<text x="48" y="700" class="sub">kind={esc(kind)} · 状态色={esc(severity)} · 证据/入口以 finding 报告为准</text>',
        '</svg>',
    ]
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
        scene = attack.get("scene") or {}
        director = load_director(out_dir, fid)
        story = director_storyboard(director)
        attacker = story["attacker"] or scene.get("attacker") or []
        victim = story["victim"] or scene.get("victim") or []
        lines += [f"### {fid} — {attack.get('label', '')}", ""]
        if (out_dir / f"scene-{fid}.webp").exists():
            lines += [f"![attack scene](scene-{fid}.webp)", ""]
        if scene or story["attacker"]:
            lines += [
                "**攻击场景（AI 插图，非证据）**" if (out_dir / f"scene-{fid}.webp").exists() else "**攻击场景**",
                "",
                f"![scene sequence](scene-{fid}.svg)",
                "",
                "| 攻击者执行 | 受害者执行 |",
                "|---|---|",
            ]
            for index in range(max(len(attacker), len(victim))):
                left = attacker[index] if index < len(attacker) else ""
                right = victim[index] if index < len(victim) else ""
                lines.append(f"| {left} | {right} |")
            lines += ["", f"> {story.get('caption') or scene.get('disclaimer', '')}", ""]
        lines += [f"![attack path](attack-{fid}.svg)", ""]
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
        story = director_storyboard(load_director(out_dir, fid))
        scene = dict(attack.get("scene") or {})
        if story["attacker"] or story["victim"]:
            scene.update({
                "attacker": story["attacker"],
                "victim": story["victim"],
                "boundary": story["trust_boundary"] or scene.get("boundary"),
            })
        if scene:
            enriched = dict(attack)
            enriched["scene"] = scene
            svg_scene(enriched, out_dir / f"scene-{fid}.svg")
        svg_tree(attack, f"Attack path / {fid}", out_dir / f"attack-{fid}.svg", 8, 80)
    render_report(model, model_path.parent, out_dir)
    print(json.dumps({"out_dir": str(out_dir), "diagrams": 2 + min(12, len(trees.get('attacks', []))) + min(12, len([a for a in trees.get('attacks', []) if a.get('scene')])), "report": str(out_dir / "report-illustrated.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
