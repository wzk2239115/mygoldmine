#!/usr/bin/env python3
"""跨进程项目名额与持久队列；只限制项目，不改变项目内并发。"""

import argparse
import fcntl
import json
import os
import time
from pathlib import Path


def read(file, default=None):
    try:
        return json.loads(Path(file).read_text())
    except (OSError, ValueError):
        return default


def process_token(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().split(") ")[1].split()
        return fields[19] if fields[0] != "Z" else None
    except (OSError, IndexError):
        return None


def update(repo, action, identifier, project, file, pid):
    directory = Path(repo) / ".state/project-admission"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "queue.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = read(directory / "queue.json", {"schema_version": 1, "tickets": []})
        rows = data["tickets"]
        limit = read(Path(repo) / "config/system.json", {}).get("projectConcurrency", 5)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("项目并发上限必须在 1 到 100 之间")
        def alive(row):
            return bool(row.get("token") and process_token(row["pid"]) == row["token"])

        if action == "release":
            rows[:] = [r for r in rows if not (r["id"] == identifier and r["pid"] == pid)]
            result = {"status": "released"}
        else:
            row = next((r for r in rows if r["id"] == identifier), None)
            if row and alive(row) and row["pid"] != pid:
                raise ValueError("同一任务已有调度进程")
            if row is None:
                row = {
                    "id": identifier,
                    "project": project,
                    "file": file,
                    "queuedAt": time.time_ns(),
                    "status": "queued",
                }
                rows.append(row)
            if row.get("pid") and not alive(row):
                row["status"] = "queued"
            row.update(pid=pid, token=process_token(pid))
            # 部署前已启动的工作流也占名额，不中断它们，不让新任务绕过。
            active = {r["project"] for r in rows if r["status"] == "active" and alive(r)}
            for owner in (Path(repo) / "runs").glob(".node-retry-*.lock/workflow-owner.json"):
                claim = read(owner, {})
                state = read(claim.get("file", ""), {})
                if state.get("admission", {}).get("status") == "queued":
                    continue
                if state.get("status") == "running" and process_token(state.get("coordinatorPid")):
                    active.add(state["project"])
            pending = sorted(
                (r for r in rows if r["status"] == "queued" and alive(r)),
                key=lambda r: r["queuedAt"],
            )
            position = next((i + 1 for i, r in enumerate(pending) if r is row), 0)
            if row["status"] == "active" or (pending and pending[0] is row and len(active) < limit):
                row["status"] = "active"
                active.add(project)
            result = {
                "status": row["status"],
                "position": position if row["status"] == "queued" else 0,
                "limit": limit,
                "activeProjects": len(active),
            }
        temporary = directory / f"queue.{os.getpid()}.tmp"
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        temporary.replace(directory / "queue.json")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("repo", "action", "id", "project", "file", "pid"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(
        json.dumps(update(args.repo, args.action, args.id, args.project, args.file, int(args.pid)))
    )
