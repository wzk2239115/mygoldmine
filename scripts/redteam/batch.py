#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))
import build_state as base  # noqa: E402

CANDIDATES = ROOT / "docs" / "redteam-candidates.json"
BATCH_ROOT = ROOT / "runs" / "redteam" / "batch"


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default=str(CANDIDATES))
    parser.add_argument("--model", default="flint")
    parser.add_argument("--base-url", default="http://100.81.81.75:8081/v1")
    parser.add_argument("--api-key", default="local")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--build-labs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidates = load(Path(args.candidates), {}).get("candidates", [])
    latest = base.latest_findings()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_dir = BATCH_ROOT / stamp
    batch_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for index, candidate in enumerate(candidates, 1):
        project = candidate.get("project", "")
        finding_id = candidate.get("id", "")
        key = base.canon(project, finding_id)
        item = latest.get(key)
        entry = {"project": project, "id": finding_id, "key": key, "status": "blocked_no_finding"}
        if item:
            finding_path = batch_dir / f"{index:02d}-{project}-{finding_id}.json"
            finding = item.get("raw") or {}
            finding.setdefault("id", finding_id)
            finding_path.write_text(json.dumps(finding, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            entry["finding"] = str(finding_path)
            scenario_path = ROOT / "labs" / project / "scenario.json"
            if not scenario_path.exists() and args.build_labs and not args.dry_run:
                builder = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "redteam" / "build_lab.py"),
                     "--project", project, "--finding", str(finding_path)],
                    capture_output=True, text=True, cwd=ROOT,
                )
                entry["builder_returncode"] = builder.returncode
                entry["builder_stdout"] = builder.stdout[-1200:]
                entry["builder_stderr"] = builder.stderr[-1200:]
            if not scenario_path.exists():
                entry.update({"status": "blocked_no_lab", "scenario": str(scenario_path)})
            else:
                scenario = load(scenario_path, {})
                entry["scenario"] = str(scenario_path)
                if args.dry_run:
                    entry["status"] = "ready"
                else:
                    run_id = f"batch-{stamp}-{index:02d}"
                    agent = [
                        sys.executable, str(ROOT / "scripts" / "redteam" / "agent.py"),
                        "--finding", str(finding_path),
                        "--project", project,
                        "--run-id", run_id,
                        "--model", args.model,
                        "--base-url", args.base_url,
                        "--api-key", args.api_key,
                        "--max-steps", str(args.max_steps),
                    ]
                    if scenario.get("victim_image"):
                        agent += ["--victim-image", scenario["victim_image"]]
                    if scenario.get("attacker_image"):
                        agent += ["--attacker-image", scenario["attacker_image"]]
                    if scenario.get("target_url"):
                        agent += ["--target-url", scenario["target_url"]]
                    if scenario.get("health_path"):
                        agent += ["--health-path", scenario["health_path"]]
                    completed = subprocess.run(agent, capture_output=True, text=True, cwd=ROOT)
                    entry["agent_returncode"] = completed.returncode
                    run_dir = ROOT / "runs" / "redteam" / project / run_id
                    if completed.returncode == 0:
                        judge = subprocess.run(
                            [sys.executable, str(ROOT / "scripts" / "redteam" / "judge.py"), "--run-dir", str(run_dir)],
                            capture_output=True, text=True, cwd=ROOT,
                        )
                        entry["judge_returncode"] = judge.returncode
                        entry["status"] = "judge_approved" if judge.returncode == 0 else "judge_rejected"
                    else:
                        entry["status"] = "not_captured"
                    entry["run_dir"] = str(run_dir)
                    entry["stdout"] = completed.stdout[-1000:]
                    entry["stderr"] = completed.stderr[-1000:]
        summary.append(entry)
        print(json.dumps(entry, ensure_ascii=False))
    output = {"generated_at": datetime.now(timezone.utc).isoformat(), "model": args.model, "results": summary}
    (batch_dir / "summary.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for item in summary:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"batch": str(batch_dir), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
