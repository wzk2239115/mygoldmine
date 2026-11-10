#!/usr/bin/env python3
"""按原始会话/请求去重汇总词元；缺失数据不推断为零。"""

import argparse
import fcntl
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def scope(path, repo):
    parts = path.relative_to(repo).parts
    project = parts[1] if len(parts) > 1 else "unknown"
    run = parts[2].removesuffix(".meta") if parts[0] == "runs" and len(parts) > 2 else None
    text = str(path)
    stage = "orchestrator"
    for marker, value in [
        ("env-build", "environment"),
        ("/env/", "environment"),
        ("visual", "visual"),
        ("/verify/", "verify"),
        ("/redteam/", "redteam"),
        ("/judge/", "judge"),
        ("/rsi/", "learner"),
        ("/workflows/", "coordinator"),
    ]:
        if marker in text:
            stage = value
    return dict(project=project, run_id=run, stage=stage)


def normalize(event, path, repo, offset):
    message = event.get("message") or {}
    if not isinstance(message, dict):
        message = {}
    usage = event.get("usage") or message.get("usage")
    direct = event.get("type") == "model_usage"
    result = event.get("type") == "result" or ("session_id" in event and "duration_api_ms" in event)
    if not direct and not result and event.get("type") != "assistant":
        return None
    if not isinstance(usage, dict) and not direct and not result:
        return None
    session = event.get("session_id") or event.get("sessionId")
    identifier = event.get("request_key") if direct else session
    if not identifier:
        # No stable identity means unknown, never invent a deduplication key.
        return None
    kind = "request" if direct else "result" if result else "message"
    key = str(identifier)
    if kind == "message":
        if not message.get("id"):
            return None
        key += "/" + message["id"]
    row = {
        **scope(path, repo),
        "key": key,
        "kind": kind,
        "session": session,
        "source": str(path.relative_to(repo)),
        "offset": offset,
        "timestamp": event.get("timestamp"),
        "usage_known": isinstance(usage, dict),
        "model": event.get("model") or message.get("model"),
    }
    if direct:
        row.update({k: event[k] for k in ("project", "stage") if event.get(k)})
    usage = usage or {}
    values = {
        "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens")),
        "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
    }
    details = usage.get("prompt_tokens_details") or {}
    if "prompt_tokens" in usage:
        row["provider_convention"] = "openai_prompt_includes_cache"
        values["cache_read_input_tokens"] = details.get("cached_tokens")
    else:
        row["provider_convention"] = "claude_reported_categories"
    row["tokens"] = {k: v if type(v) is int and v >= 0 else None for k, v in values.items()}
    return row


def summarize(rows):
    # Final session summaries replace message-level usage, never add both.
    sessions = {r["session"] for r in rows if r["kind"] == "result"}
    selected = [r for r in rows if r["kind"] != "message" or r["session"] not in sessions]
    groups = {}
    for row in selected:
        key = (
            row["project"],
            row["run_id"],
            row["stage"],
            row.get("model"),
            row.get("provider_convention"),
        )
        group = groups.setdefault(
            key,
            dict(
                project=key[0],
                run_id=key[1],
                stage=key[2],
                records=0,
                unknown_usage=0,
                totals={k: 0 for k in FIELDS},
                missing_fields={k: 0 for k in FIELDS},
            ),
        )
        group["model"] = key[3]
        group["provider_convention"] = key[4]
        group["records"] += 1
        group["unknown_usage"] += not row["usage_known"]
        for name, value in row["tokens"].items():
            if value is None:
                group["missing_fields"][name] += 1
            else:
                group["totals"][name] += value
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": list(groups.values()),
        "records": len(selected),
        "limitations": [
            "仅统计可识别的用量记录，未记录的历史调用不能回填。",
            "各提供方缓存计数语义不同，分类展示，不直接跨类别相加。",
            "会话总量优先于逐消息记录；记录时间缺失时不推断请求发生时间。",
        ],
    }


def refresh(repo):
    repo = Path(repo).resolve()
    output = repo / ".runtime/state/token-usage"
    output.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output / "usage.sqlite", timeout=60)
    db.execute(
        "create table if not exists sources(path text primary key, offset integer, inode integer)"
    )
    db.execute(
        "create table if not exists events(kind text,key text,data text,primary key(kind,key))"
    )
    paths = []
    for folder in (repo / "runs", repo / "env"):
        if not folder.exists():
            continue
        for directory, dirs, files in os.walk(folder):
            dirs[:] = [
                d
                for d in dirs
                if d
                not in {
                    ".git",
                    "node_modules",
                    "harness",
                    "evidence",
                    "site-packages",
                    "build-context",
                    ".workspace",
                }
            ]
            for name in files:
                p = Path(directory) / name
                if not p.is_symlink() and (
                    name in {"raw.jsonl", "model-usage.jsonl", "jev-infra.json"}
                    or name.endswith(".agent.log")
                    or name.startswith("env-build-agent-")
                    and name.endswith(".log")
                ):
                    paths.append(p)

    for path in paths:
        stat = path.stat()
        previous = db.execute(
            "select offset,inode from sources where path=?", (str(path),)
        ).fetchone()
        if path.name == "jev-infra.json":
            try:
                value = json.loads(path.read_text())
                meta = scope(path, repo)
                event = {
                    "type": "model_usage",
                    "request_key": "jev:" + meta["project"] + "/" + str(meta["run_id"]),
                    "usage": value.get("stats"),
                    "stage": "triage",
                    "timestamp": value.get("generated_at"),
                    "model": value.get("model_returned"),
                }
                row = normalize(event, path, repo, 0)
                db.execute(
                    "insert or replace into events values(?,?,?)",
                    (row["kind"], row["key"], json.dumps(row)),
                )
                db.commit()
            except (ValueError, OSError):
                pass
            continue
        offset = (
            previous[0]
            if previous and previous[1] == stat.st_ino and previous[0] <= stat.st_size
            else 0
        )
        with path.open("rb") as stream:
            stream.seek(offset)
            while True:
                position = stream.tell()
                line = stream.readline()
                if not line or not line.endswith(b"\n"):
                    offset = position
                    break
                try:
                    event = json.loads(line)
                    row = (
                        normalize(event, path, repo, position) if isinstance(event, dict) else None
                    )
                except (ValueError, TypeError):
                    continue
                if row:
                    db.execute(
                        "insert or replace into events values(?,?,?)",
                        (row["kind"], row["key"], json.dumps(row, ensure_ascii=False)),
                    )
        db.execute("insert or replace into sources values(?,?,?)", (str(path), offset, stat.st_ino))
        db.commit()
    rows = [json.loads(row[0]) for row in db.execute("select data from events")]
    result = summarize(rows)
    result["source_files"] = len(paths)
    tmp = output / "summary.tmp"
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    tmp.replace(output / "summary.json")
    db.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    if args.watch:
        folder = Path(args.repo) / ".runtime/state/token-usage"
        folder.mkdir(parents=True, exist_ok=True)
        lock = (folder / "collector.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(0)
        while True:
            try:
                refresh(args.repo)
            except Exception as exc:
                (folder / "collector-error.json").write_text(
                    json.dumps({"error": str(exc), "time": time.time()})
                )
            time.sleep(60)
    else:
        print(json.dumps({"records": refresh(args.repo)["records"]}))
