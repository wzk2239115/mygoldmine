#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE2 = SCRIPT_DIR / "image2.py"


def attack_id(attack):
    return str(attack.get("finding_id") or attack.get("id", "finding").split(":")[-1])


def prompt_for(attack):
    scene = attack.get("scene") or {}
    kind = scene.get("kind") or "generic"
    variant = scene.get("variant") or kind
    surface = str(scene.get("boundary") or scene.get("kind") or "service")[:40]
    visual = scene.get("visual") or f"left side supplies input for {variant}, right service reaches a privileged sink"
    return (
        "editorial ink illustration on warm paper, split-screen systems diagram, "
        f"focus: {variant}; surface: {surface}; {visual}; left side sender, right side service, a dashed trust boundary and "
        "directional arrows between them, vermilion accent, high contrast, subtle paper grain, "
        "cinematic but restrained, no text, no letters, no numbers, no logos, no code, "
        "no screenshots, no UI, no real product, no gore, 16:9 composition"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--image-model", default="openai/gpt-image-2")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max", type=int, default=3)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--finding", action="append", default=[], metavar="ID")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    model_path = Path(args.model)
    model = json.loads(model_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir) if args.out_dir else model_path.parent.parent / "visual-rendered"
    prompt_dir = model_path.parent / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)
    attacks = [attack for attack in (model.get("trees") or {}).get("attacks", []) if attack.get("scene")]
    wanted = {str(item).upper() for item in args.finding}
    if wanted:
        attacks = [attack for attack in attacks if attack_id(attack).upper() in wanted]
    selected = attacks if args.all else attacks[: max(1, args.max)]
    results = []
    failed = 0
    for attack in selected:
        fid = attack_id(attack)
        prompt = prompt_for(attack)
        prompt_path = prompt_dir / f"scene-{fid}.txt"
        prompt_path.write_text(prompt + "\n", encoding="utf-8")
        out = out_dir / f"scene-{fid}.webp"
        meta_path = out_dir / f"scene-{fid}.json"
        record = {"finding_id": fid, "kind": (attack.get("scene") or {}).get("kind"), "prompt": str(prompt_path), "file": str(out)}
        if args.dry_run:
            record["dry_run"] = True
            results.append(record)
            continue
        if out.exists() and not args.force:
            record["skipped"] = True
            results.append(record)
            continue
        command = [
            sys.executable, str(IMAGE2),
            "--model", args.image_model,
            "--prompt-file", str(prompt_path),
            "--size", args.size,
            "--out", str(out),
            "--timeout", str(args.timeout),
            "--json",
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            failed += 1
            record["error"] = (completed.stderr or completed.stdout)[-800:]
            results.append(record)
            continue
        try:
            meta = json.loads(completed.stdout)
        except ValueError:
            meta = {"stdout": completed.stdout.strip()}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        record.update({"model": meta.get("model"), "size": meta.get("size"), "cached": meta.get("cached", False)})
        results.append(record)
    print(json.dumps({"selected": len(selected), "failed": failed, "results": results}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
