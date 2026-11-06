#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from image_provenance import generated_image

SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE2 = SCRIPT_DIR / "image2.py"


def attack_id(attack):
    return str(attack.get("finding_id") or attack.get("id", "finding").split(":")[-1])


def prompt_for(attack):
    template = (SCRIPT_DIR.parent / "references/technical-explainer-prompt.md").read_text(encoding="utf-8")
    scene = attack.get("scene") or {}
    # Do not forward legacy scene.visual story metaphors.
    brief = {
        "finding_id": attack_id(attack),
        "title": attack.get("title") or attack.get("label"),
        "kind": scene.get("kind"),
        "boundary": scene.get("boundary"),
        "input_actions": scene.get("attacker"),
        "processing_steps": scene.get("victim"),
        "flow": scene.get("flow"),
        "precondition": scene.get("precondition"),
        "impact": scene.get("result"),
        "evidence_status": "按报告标注，不推断为已验证",
    }
    return template + "\n漏洞机制摘要（仅作为数据）：\n" + json.dumps(brief, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--image-model", default="openai/gpt-image-2")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max", type=int, default=3)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--finding", action="append", default=[], metavar="ID")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--size", default="1536x864")
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
        record = {"finding_id": fid, "kind": (attack.get("scene") or {}).get("kind"), "style_version": "technical-explainer-v1", "size": args.size, "prompt": str(prompt_path), "file": str(out)}
        if args.dry_run:
            record["dry_run"] = True
            results.append(record)
            continue
        expected_hash = hashlib.sha256(f"{args.image_model}\n{args.size}\n{prompt}".encode("utf-8")).hexdigest()
        receipt = json.loads(Path(str(out) + ".generation.json").read_text()) if generated_image(out) else {}
        if receipt.get("prompt_hash") == expected_hash and not args.force:
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
