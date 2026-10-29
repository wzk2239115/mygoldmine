#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import build_state as base  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--finding", required=True)
    parser.add_argument("--source", default="")
    parser.add_argument("--lab-dir", default="")
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--claude-model", default="")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    finding = Path(args.finding).resolve()
    lab_dir = Path(args.lab_dir).resolve() if args.lab_dir else ROOT / "labs" / args.project
    source = Path(args.source).resolve() if args.source else ROOT / "targets" / args.project
    manifest = ROOT / "env" / args.project / "env-manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            source = Path(data.get("source") or source).resolve()
        except Exception:
            pass
    lab_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "project": args.project,
        "finding": str(finding),
        "source": str(source),
        "env_manifest": str(manifest),
        "lab_dir": str(lab_dir),
        "scenario_out": str(lab_dir / "scenario.json"),
        "report_out": str(lab_dir / "lab-report.md"),
        "blocked_out": str(lab_dir / "BLOCKED.md"),
    }
    task_path = lab_dir / "lab-task.json"
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        print(json.dumps({"task": str(task_path), "dry_run": True}, ensure_ascii=False, indent=2))
        return 0

    prompt = (
        f"Read {task_path} and follow the redteam-lab-builder skill. "
        "Build and validate the lab, then write the scenario and report. "
        "If impossible, write BLOCKED.md with the concrete blocker. "
        "Do not modify the finding or the source tree. Print the scenario path when done."
    )
    command = [args.claude]
    if args.claude_model:
        command += ["--model", args.claude_model]
    command += ["--agent", "redteam-lab-builder", "--permission-mode=bypassPermissions", "-p", prompt]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=args.timeout)
    (lab_dir / "builder.log").write_text(
        f"# returncode\n{completed.returncode}\n\n# stdout\n{completed.stdout}\n\n# stderr\n{completed.stderr}\n",
        encoding="utf-8",
    )
    scenario = lab_dir / "scenario.json"
    result = {
        "project": args.project,
        "finding": str(finding),
        "scenario": str(scenario) if scenario.exists() else "",
        "blocked": str(lab_dir / "BLOCKED.md") if (lab_dir / "BLOCKED.md").exists() else "",
        "returncode": completed.returncode,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if scenario.exists() else 2


if __name__ == "__main__":
    sys.exit(main())
