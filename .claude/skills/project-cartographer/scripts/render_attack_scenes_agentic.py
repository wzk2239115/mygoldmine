#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AGENT = "attack-scene-director"


def attack_id(attack):
    return str(attack.get("finding_id") or attack.get("id", "finding").split(":")[-1])


def verify_reports(project, finding_id):
    matches = []
    wanted = finding_id.lower()
    for path in sorted((ROOT / "runs" / project).glob("*/verify/**/verify-report.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        ids = [data.get("finding_id"), data.get("id")]
        if isinstance(data.get("results"), list):
            ids += [item.get("id") or item.get("finding_id") for item in data["results"] if isinstance(item, dict)]
        if isinstance(data.get("findings"), list):
            ids += [item.get("finding_id") or item.get("id") for item in data["findings"] if isinstance(item, dict)]
        if any(str(item or "").lower() == wanted for item in ids):
            matches.append(str(path.relative_to(ROOT)))
    return matches


def task_prompt(task_path: Path, task: dict):
    return (
        "Read the task file at "
        f"{task_path} and follow the attack-scene-director instructions. "
        f"Generate the attack scene for finding {task['finding_id']} from "
        f"{task['report_json']}. Write {task['director_out']}, {task['prompt_out']}, "
        f"and {task['image_out']}. Use image2.py through Bash. "
        "Do not modify source or report files. Do not show secrets. "
        "When done, print the paths you wrote."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="visual-model.json")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max", type=int, default=3)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--finding", action="append", default=[], metavar="ID")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--claude-model", default=os.environ.get("VISUAL_AGENT_MODEL", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    model_path = Path(args.model).resolve()
    model = json.loads(model_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir).resolve() if args.out_dir else model_path.parent.parent / "visual-rendered"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_root = model_path.parent / "agentic"
    work_root.mkdir(parents=True, exist_ok=True)
    prompt_dir = model_path.parent / "prompts"
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
        work_dir = work_root / fid
        work_dir.mkdir(parents=True, exist_ok=True)
        task_path = work_dir / "task.json"
        director_out = out_dir / f"scene-{fid}.director.json"
        prompt_out = prompt_dir / f"scene-{fid}.txt"
        image_out = out_dir / f"scene-{fid}.webp"
        task = {
            "project": model.get("project"),
            "project_name": model.get("project_name"),
            "run_dir": model.get("run_dir"),
            "run_id": model.get("run_id"),
            "finding_id": fid,
            "visual_model": str(model_path),
            "report_json": str(Path(model.get("run_dir") or "") / "audit-report.json"),
            "verify_reports": verify_reports(model.get("project"), fid),
            "out_dir": str(out_dir),
            "prompt_out": str(prompt_out),
            "image_out": str(image_out),
            "director_out": str(director_out),
            "max_attempts": args.max_attempts,
            "attack": attack,
        }
        task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        record = {"finding_id": fid, "task": str(task_path), "image": str(image_out), "director": str(director_out)}
        if args.dry_run:
            record["dry_run"] = True
            results.append(record)
            continue
        if image_out.exists() and director_out.exists() and not args.force:
            record["skipped"] = True
            results.append(record)
            continue
        command = [args.claude]
        if args.claude_model:
            command += ["--model", args.claude_model]
        command += ["--agent", AGENT, "--permission-mode=bypassPermissions", "-p", task_prompt(task_path, task)]
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
        (work_dir / "agent.log").write_text(
            f"# returncode\n{process.returncode}\n\n# timeout\n{timed_out}\n\n# stdout\n{stdout}\n\n# stderr\n{stderr}\n",
            encoding="utf-8",
        )
        record.update({"returncode": process.returncode, "timed_out": timed_out, "log": str(work_dir / "agent.log")})
        if not image_out.exists() or not director_out.exists():
            failed += 1
            record["error"] = "agent did not produce image and director json"
        elif timed_out:
            record["warning"] = "agent timed out after producing outputs"
        results.append(record)
    print(json.dumps({"selected": len(selected), "failed": failed, "results": results}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
