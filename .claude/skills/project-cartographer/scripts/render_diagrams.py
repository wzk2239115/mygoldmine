#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from image_provenance import generated_image

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


def render_report(model, run_dir, out_dir):
    out_dir = Path(out_dir)
    project = model.get("project_name") or model.get("project")
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
    lines += [
        "## 1. 项目结构",
        "",
        "项目范围与证据路径以本次审计报告和结构化数据为准。",
        "",
        "不使用程序绘制结构图。",
        "",
        "## 2. AI 审计覆盖",
        "",
        "覆盖范围以审计报告的覆盖记录为准，未记录的范围保持未知。",
        "",
        "覆盖记录保留为文字与结构化数据，不生成 SVG。",
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
        if generated_image(out_dir / f"scene-{fid}.webp"):
            lines += [f"![attack scene](scene-{fid}.webp)", ""]
        if scene or story["attacker"]:
            lines += [
                "**攻击场景（AI 插图，非证据）**" if generated_image(out_dir / f"scene-{fid}.webp") else "**攻击场景**",
                "",
                "",
                "| 攻击者执行 | 受害者执行 |",
                "|---|---|",
            ]
            for index in range(max(len(attacker), len(victim))):
                left = attacker[index] if index < len(attacker) else ""
                right = victim[index] if index < len(victim) else ""
                lines.append(f"| {left} | {right} |")
            lines += ["", f"> {story.get('caption') or scene.get('disclaimer', '')}", ""]
        if not generated_image(out_dir / f"scene-{fid}.webp"):
            lines += ["> 本候选尚无可用的文生图模型插图；未以代码绘图替代。", ""]
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
    lines += ["", "> 本报告的插图仅由文生图模型生成，不作为漏洞证据；代码只整理文字、表格和已有模型图片，不绘制图片。", ""]
    (out_dir / "report-illustrated.md").write_text("\n".join(lines), encoding="utf-8")



def main():
    parser = argparse.ArgumentParser(description="整理文字、表格及文生图模型插图；不绘制 SVG 或其他图片")
    parser.add_argument("--model", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max-depth", type=int, default=8, help="兼容旧参数，不再绘制结构图")
    args = parser.parse_args()
    model_path = Path(args.model)
    model = json.loads(model_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir) if args.out_dir else model_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    render_report(model, model_path.parent, out_dir)
    print(json.dumps({"out_dir": str(out_dir), "diagrams": 0, "image_source": "text-to-image-only",
                      "report": str(out_dir / "report-illustrated.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
