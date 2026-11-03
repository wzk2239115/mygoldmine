#!/usr/bin/env python3
"""Convert mygoldmine run transcripts into Claude Code session JSONL.

CloudCLI / claudecodeui discovers sessions under $HOME/.claude/projects.
Each run's raw.jsonl is already Claude stream-json, so we normalize it into
the on-disk transcript shape and keep the original message/tool blocks.
"""

from __future__ import annotations

import argparse
import json
import os
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
    wanted_runs: set[str] | None = None,
) -> list[Path]:
    if wanted_runs:
        picked: list[Path] = []
        for key in sorted(wanted_runs):
            run_dir = runs_root / key
            if (run_dir / "raw.jsonl").is_file():
                picked.append(run_dir)
        return picked
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
        if project_dir.is_dir()
        and not project_dir.name.startswith(".")
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


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    temp.replace(path)


def convert_run(
    run_dir: Path,
    home: Path,
    project: str,
    *,
    raw_path: Path | None = None,
    sidecar_path: Path | None = None,
    title_suffix: str = "",
    agent_name: str = "",
) -> tuple[str, Path] | None:
    raw_path = raw_path or run_dir / "raw.jsonl"
    sidecar_path = sidecar_path or run_dir / "ccui-session.json"
    meta = {
        **_load_json(run_dir.with_name(run_dir.name + ".meta") / "status.json", {}),
        **_load_json(run_dir / "run-meta.json", {}),
    }
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
        try:
            started = datetime.strptime(run_dir.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            # Persisted for unstructured run names so periodic import remains stable.
            previous = _load_json(sidecar_path, {})
            started = datetime.fromisoformat(
                previous.get("startedAt") or datetime.now(timezone.utc).isoformat()
            )
    title = f"mygoldmine · {project} · {run_dir.name}{title_suffix}"
    if agent_name:
        meta["agent"] = agent_name
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
    tasks: dict[str, dict[str, str]] = {}
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "task_started":
            call = str(event.get("tool_use_id") or "")
            if call:
                tasks[call] = {
                    "id": str(event.get("task_id") or _det_uuid(session_id, call)),
                    "description": str(event.get("description") or ""),
                }
        result = event.get("tool_use_result")
        if isinstance(result, dict) and result.get("agentId"):
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("tool_use_id"):
                    call = str(block["tool_use_id"])
                    tasks.setdefault(call, {})["id"] = str(result["agentId"])
                    tasks[call]["type"] = str(result.get("agentType") or "")
    children: dict[str, list[dict[str, Any]]] = {}
    used_uuids = {header_uuid}
    seen_events: set[str] = set()
    parents: dict[str, str] = {"": header_uuid}
    index = 0
    for event in events:
        event_type = event.get("type")
        if event_type not in {"assistant", "user", "result"}:
            continue
        # A streamed child turn is not another human message in the main conversation.
        branch = str(event.get("parent_tool_use_id") or "")
        fingerprint = json.dumps(event, ensure_ascii=False, sort_keys=True)
        if event.get("uuid") and fingerprint in seen_events:
            continue
        seen_events.add(fingerprint)
        index += 1
        parent = parents.get(branch)
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
            row["isSidechain"] = bool(branch)
            if event_type == "user":
                row.setdefault("isMeta", False)
                row["userType"] = "external"
                row["entrypoint"] = "cli"
            row.pop("session_id", None)
        if branch:
            task = tasks.setdefault(branch, {"id": _det_uuid(session_id, branch)})
            row["isSidechain"] = True
            row["agentId"] = task["id"]
            children.setdefault(branch, []).append(row)
        else:
            rows.append(row)
        parents[branch] = row_uuid

    slug = cwd.replace("/", "-")
    out_dir = home / ".claude" / "projects" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_id}.jsonl"
    for branch, child_rows in children.items():
        task = tasks[branch]
        # Encode untrusted external IDs into a safe filename and keep native IDs for normal runs.
        agent_id = task["id"]
        if not agent_id or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in agent_id
        ):
            agent_id = _det_uuid(session_id, agent_id)
        child_path = out_dir / session_id / "subagents" / f"agent-{agent_id}.jsonl"
        _write_rows(child_path, child_rows)
        metadata = {
            "agentType": task.get("type") or "agent",
            "description": task.get("description") or "",
            "toolUseId": branch,
            "spawnDepth": 1,
        }
        child_path.with_suffix(".meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
        )
    _write_rows(out_path, rows)
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
    sidecar = {
        "sessionId": session_id,
        "project": project,
        "runId": run_dir.name,
        "title": title,
        "cwd": cwd,
        "sessionFile": str(out_path),
        "messages": sum(1 for row in rows if row.get("type") in {"user", "assistant"}),
        "importedAt": datetime.now(timezone.utc).isoformat(),
        "startedAt": started.isoformat(),
        "importVersion": 2,
        "subagents": len(children),
        "subagentMessages": sum(len(items) for items in children.values()),
    }
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return session_id, out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default=str(REPO_ROOT / "runs"))
    parser.add_argument("--home", default=str(REPO_ROOT / "runs" / "ccui-home"))
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        metavar="PROJECT/RUN_ID",
        help="import only these runs (relative to the runs root)",
    )
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
    wanted_runs = {item.strip("/") for item in args.run if item.strip("/")} or None
    run_dirs = _run_dirs(runs_root, projects, not args.all, args.include_smoke, wanted_runs)
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
