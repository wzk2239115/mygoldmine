#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from contracts import ContractError, finding_id, scenario_path, sha256_bytes, validate_scenario

ROOT = Path(__file__).resolve().parents[2]


def language_directive():
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "config" / "language.py"), "--prompt"],
            capture_output=True, text=True, timeout=10,
        )
        return completed.stdout.strip()
    except Exception:
        return ""


def resolve_source(explicit, project, manifest):
    if explicit:
        return Path(explicit).resolve()
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("source"):
                return Path(data["source"]).resolve()
        except Exception:
            pass
    for candidate in (ROOT / "targets" / project, ROOT / "targets" / "catalog" / project):
        if candidate.is_dir():
            return candidate.resolve()
    return (ROOT / "targets" / project).resolve()


def hash_source(source):
    digest = hashlib.sha256()
    paths = sorted(source.rglob("*"), key=lambda path: path.relative_to(source).as_posix())
    for path in paths:
        relative = path.relative_to(source)
        if ".git" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        if path.is_symlink():
            digest.update(b"link\0" + os.readlink(path).encode("utf-8") + b"\0")
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def source_binding(source, manifest):
    try:
        data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    except (OSError, ValueError):
        data = {}
    manifest_source = data.get("source")
    if data.get("commit") and manifest_source and Path(manifest_source).resolve() == source:
        return {"commit": str(data["commit"])}
    try:
        completed = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return {"commit": completed.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"content_sha256": hash_source(source)}


def run(args):
    finding = Path(args.finding).resolve()
    finding_bytes = finding.read_bytes()
    finding_data = json.loads(finding_bytes.decode("utf-8"))
    identifier = finding_id(finding_data)
    expected_finding_sha256 = sha256_bytes(finding_bytes)
    lab_dir = Path(args.lab_dir).resolve() if args.lab_dir else scenario_path(
        ROOT, args.project, identifier
    ).parent
    manifest = ROOT / "env" / args.project / "env-manifest.json"
    source = resolve_source(args.source, args.project, manifest)
    lab_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_dir():
        blocker = (
            f"# BLOCKED: source not found\n\n"
            f"project: {args.project}\n"
            f"expected_source: {source}\n"
            f"looked_in: {ROOT / 'targets' / args.project}, "
            f"{ROOT / 'targets' / 'catalog' / args.project}\n\n"
            "The lab builder cannot inspect the target. Clone the repository under targets/ "
            "or pass --source.\n"
        )
        (lab_dir / "BLOCKED.md").write_text(blocker, encoding="utf-8")
        print(json.dumps({
            "status": "build_failed", "project": args.project, "finding": str(finding),
            "scenario": "", "scenario_valid": False,
            "blocked": str(lab_dir / "BLOCKED.md"), "returncode": 2,
            "error": f"source not found: {source}",
        }, ensure_ascii=False, indent=2))
        return 2
    expected_source = source_binding(source, manifest)
    scenario = lab_dir / "scenario.json"
    task = {
        "project": args.project,
        "finding": str(finding),
        "finding_id": identifier,
        "finding_sha256": expected_finding_sha256,
        "source": str(source),
        "source_binding": expected_source,
        "env_manifest": str(manifest),
        "lab_dir": str(lab_dir),
        "scenario_out": str(scenario),
        "report_out": str(lab_dir / "lab-report.md"),
        "blocked_out": str(lab_dir / "BLOCKED.md"),
        "scenario_schema_version": 1,
        "supported_modes": ["http"],
    }
    task_path = lab_dir / "lab-task.json"
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run", "task": str(task_path), "dry_run": True,
            "finding_sha256": expected_finding_sha256, "source_binding": expected_source,
        }, ensure_ascii=False, indent=2))
        return 0

    prompt = (
        f"{language_directive()}\n\n"
        f"Read {task_path} and follow the redteam-lab-builder skill. "
        "Build and validate the lab, then write the scenario and report. "
        "Copy finding_id, finding_sha256, source_binding and schema_version into the scenario "
        "as finding_id, finding_sha256, source and schema_version. Use only a supported mode "
        "and do not declare mounts. If impossible, write BLOCKED.md with the concrete blocker. "
        "Do not modify the finding or the source tree. Print the scenario path when done."
    )
    command = [args.claude]
    if args.claude_model:
        command += ["--model", args.claude_model]
    command += ["--agent", "redteam-lab-builder", "--permission-mode=bypassPermissions", "-p", prompt]
    started = time.monotonic()
    timed_out = False
    returncode = 0
    log_path = lab_dir / "builder.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# timeout\n{args.timeout}s\n\n# output\n")
        log.flush()
        try:
            completed = subprocess.run(
                command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                text=True, timeout=args.timeout,
            )
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = 124
            log.write(f"\n# TIMEOUT after {args.timeout}s\n")
    if timed_out and not scenario.exists():
        (lab_dir / "BLOCKED.md").write_text(
            f"# BLOCKED: lab builder timed out\n\n"
            f"project: {args.project}\n"
            f"timeout_seconds: {args.timeout}\n"
            f"builder_log: {log_path}\n\n"
            "The builder was still working when the deadline hit. Inspect builder.log "
            "for the last action; raise --timeout or narrow the lab scope.\n",
            encoding="utf-8",
        )
    scenario_valid = False
    error = ""
    if returncode != 0:
        error = f"lab builder exited {returncode}"
    elif not scenario.exists():
        error = "lab builder did not write scenario.json"
    else:
        try:
            scenario_data = json.loads(scenario.read_text(encoding="utf-8"))
            validate_scenario(
                scenario_data,
                expected_finding_id=identifier,
                expected_finding_sha256=expected_finding_sha256,
                expected_source=expected_source,
            )
            scenario_valid = True
        except (OSError, ValueError, ContractError) as exc:
            error = f"scenario validation failed: {exc}"
    result = {
        "status": "built" if scenario_valid else "build_failed",
        "project": args.project,
        "finding": str(finding),
        "finding_id": identifier,
        "finding_sha256": expected_finding_sha256,
        "source_binding": expected_source,
        "scenario": str(scenario) if scenario.exists() else "",
        "scenario_valid": scenario_valid,
        "blocked": str(lab_dir / "BLOCKED.md") if (lab_dir / "BLOCKED.md").exists() else "",
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 1),
        "error": error,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if scenario_valid else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--finding", required=True)
    parser.add_argument("--source", default="")
    parser.add_argument("--lab-dir", default="")
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--claude-model", default="")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, ContractError) as exc:
        status = exc.status if isinstance(exc, ContractError) else "build_failed"
        print(json.dumps({"status": status, "scenario_valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
