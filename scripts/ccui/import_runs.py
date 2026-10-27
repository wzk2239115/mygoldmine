#!/usr/bin/env python3
"""Convert mygoldmine run transcripts into Claude Code session JSONL.

CloudCLI / claudecodeui discovers sessions under $HOME/.claude/projects.
Each run's raw.jsonl is already Claude stream-json, so we normalize it into
the on-disk transcript shape and keep the original message/tool blocks.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _run_dirs(
    runs_root: Path,
    projects: set[str] | None,
    latest: bool,
    include_smoke: bool = False,
) -> list[Path]:
    by_project: dict[str, Path] = {}
    for project_dir in sorted(runs_root.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        if not include_smoke and project_dir.name.startswith("smoke"):
            continue
        if projects and project_dir.name not in projects:
            continue
        for run_dir in sorted(project_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            if not (run_dir / "raw.jsonl").is_file():
                continue
            by_project[run_dir.parent.name] = run_dir
    if latest:
        return sorted(by_project.values())
    return [
        run_dir
        for project_dir in sorted(runs_root.iterdir())
        if project_dir.is_dir() and not project_dir.name.startswith(".")
        and (include_smoke or not project_dir.name.startswith("smoke"))
        and (not projects or project_dir.name in projects)
        for run_dir in sorted(project_dir.iterdir())
        if run_dir.is_dir() and (run_dir / "raw.jsonl").is_file()
    ]


def _det_uuid(session_id: str, suffix: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mygoldmine:{session_id}:{suffix}"))


def _ts(value: str | None, fallback: datetime) -> str:
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return fallback.astimezone(timezone.utc).isoformat()


def _project_cwd(run_dir: Path, project: str) -> str:
    target = REPO_ROOT / "targets" / project
    return str(target if target.exists() else run_dir)


def _session_id(events: list[dict[str, Any]]) -> str:
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "init":
            value = event.get("session_id") or event.get("sessionId")
            if value:
                return str(value)
        value = event.get("session_id") or event.get("sessionId")
        if value:
            return str(value)
    return str(uuid.uuid4())


def _header_text(meta: dict[str, Any], run_id: str, project: str) -> str:
    return (
        f"mygoldmine audit · {project} · {run_id}\n\n"
        f"target: {meta.get('target_url') or project}\n"
        f"commit: {meta.get('commit') or 'unknown'}\n"
        f"model: {meta.get('model') or 'unknown'}\n"
        f"agent: {meta.get('agent') or 'security-orchestrator'}\n\n"
        "This is a read-only replay of the audit session. "
        "The assistant/tool rows below are the recorded Claude Code stream."
    )


def convert_run(run_dir: Path, home: Path, project: str) -> tuple[str, Path] | None:
    raw_path = run_dir / "raw.jsonl"
    meta = _load_json(run_dir / "run-meta.json", {})
    events: list[dict[str, Any]] = []
    for line in raw_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    if not events:
        return None

    session_id = _session_id(events)
    cwd = _project_cwd(run_dir, project)
    started_raw = str(meta.get("started_at") or "")
    try:
        started = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
    except ValueError:
        started = datetime.now(timezone.utc)
    title = f"mygoldmine · {project} · {run_dir.name}"
    commit = str(meta.get("commit") or "")
    model = str(meta.get("model") or "")

    header_uuid = _det_uuid(session_id, "header")
    rows: list[dict[str, Any]] = [
        {
            "type": "user",
            "message": {"role": "user", "content": _header_text(meta, run_dir.name, project)},
            "uuid": header_uuid,
            "parentUuid": None,
            "sessionId": session_id,
            "cwd": cwd,
            "timestamp": _ts(started_raw, started),
            "isSidechain": False,
            "isMeta": False,
            "userType": "external",
            "entrypoint": "cli",
            "version": "mygoldmine",
            "gitBranch": commit[:12],
        },
        {
            "type": "custom-title",
            "customTitle": title,
            "sessionId": session_id,
            "uuid": _det_uuid(session_id, "title"),
            "timestamp": _ts(started_raw, started),
        },
    ]
    used_uuids = {header_uuid}
    parent = header_uuid
    index = 0
    for event in events:
        event_type = event.get("type")
        if event_type not in {"assistant", "user", "result"}:
            continue
        index += 1
        fallback = started + timedelta(seconds=index)
        row_uuid = str(event.get("uuid") or _det_uuid(session_id, f"event-{index}"))
        if row_uuid in used_uuids:
            row_uuid = _det_uuid(session_id, f"event-{index}-{len(used_uuids)}")
        used_uuids.add(row_uuid)
        if event_type == "result":
            text = str(event.get("result") or "").strip()
            if not text:
                continue
            row = {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": text}],
                    "model": model,
                },
                "uuid": row_uuid,
                "parentUuid": parent,
                "sessionId": session_id,
                "cwd": cwd,
                "timestamp": _ts(event.get("timestamp"), fallback),
                "isSidechain": False,
            }
        else:
            row = dict(event)
            row["type"] = event_type
            row["sessionId"] = session_id
            row["cwd"] = cwd
            row["uuid"] = row_uuid
            row["parentUuid"] = parent
            row["timestamp"] = _ts(event.get("timestamp"), fallback)
            row["isSidechain"] = False
            if event_type == "user":
                row.setdefault("isMeta", False)
                row["userType"] = "external"
                row["entrypoint"] = "cli"
            row.pop("session_id", None)
        rows.append(row)
        parent = row_uuid

    slug = cwd.replace("/", "-")
    out_dir = home / ".claude" / "projects" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_id}.jsonl"
    out_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    history_path = home / ".claude" / "history.jsonl"
    history: list[dict[str, Any]] = []
    if history_path.is_file():
        for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and item.get("sessionId") != session_id:
                history.append(item)
    history.append(
        {
            "display": title,
            "pastedContents": {},
            "timestamp": int(started.timestamp() * 1000),
            "project": cwd,
            "sessionId": session_id,
        }
    )
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in history),
        encoding="utf-8",
    )
    return session_id, out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"))
    parser.add_argument("--home", default=str(REPO_ROOT / "runs" / "ccui-home"))
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="include smoke/smoke-real/smoke-target runs",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="import every run, not just the latest per project",
    )
    args = parser.parse_args()

    runs_root = Path(args.runs).resolve()
    home = Path(args.home).resolve()
    projects = set(args.project) if args.project else None
    run_dirs = _run_dirs(runs_root, projects, not args.all, args.include_smoke)
    imported = 0
    for run_dir in run_dirs:
        project = run_dir.parent.name
        result = convert_run(run_dir, home, project)
        if result:
            session_id, out_path = result
            imported += 1
            print(f"{project}/{run_dir.name} -> {session_id} ({out_path})")
    print(f"imported {imported} run(s) into {home}")
    return 0 if imported else 1


if __name__ == "__main__":
    raise SystemExit(main())
