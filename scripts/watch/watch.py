#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diffaudit  # noqa: E402
import store  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WATCH_ROOT = ROOT / "runs" / "watch"
QUEUE_DIR = WATCH_ROOT / "queue"
STATE_OUT = ROOT / "ui" / "data" / "watch-state.json"


def language_directive():
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "config" / "language.py"), "--prompt"],
            capture_output=True, text=True, timeout=10,
        )
        return completed.stdout.strip()
    except Exception:
        return ""


def log(message):
    print(f"[watch] {message}", file=sys.stderr)


def require_git(path):
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def repo_url(path):
    completed = subprocess.run(
        ["git", "-C", str(path), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def enqueue(conn, event_id, event):
    if event["verdict"] not in {"critical", "high"}:
        return ""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"{event['project']}-{event['sha'][:12]}.json"
    payload = {
        "event_id": event_id,
        "project": event["project"],
        "sha": event["sha"],
        "verdict": event["verdict"],
        "score": event["score"],
        "subject": event["subject"],
        "report_json": event["report_json"],
        "recommended_action": "inspect diff, then run focused audit or lab validation",
        "queued_at": store.now(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def process_commit(conn, project, repo, sha):
    report = diffaudit.analyze(repo, sha)
    report["project"] = project
    report["repo_path"] = str(repo)
    out_dir = WATCH_ROOT / project
    json_path, md_path = diffaudit.write_report(report, out_dir)
    event = {
        **report,
        "report_json": str(json_path),
        "report_md": str(md_path),
        "recommended_action": "inspect diff, then run focused audit or lab validation"
        if report["verdict"] in {"critical", "high"}
        else "normal review",
    }
    event_id = store.insert_event(conn, event)
    queued = enqueue(conn, event_id, event)
    flags = f"queued={queued}" if queued else ""
    log(f"{project} {sha[:12]} {report['verdict']} score={report['score']} {flags}".strip())
    return event_id


def poll_repo(conn, row, fetch=False, limit=50, initial_scan=False):
    project, path = row["project"], Path(row["path"])
    if not path.is_dir():
        log(f"{project}: path missing: {path}")
        return 0
    if fetch:
        completed = subprocess.run(
            ["git", "-C", str(path), "fetch", "--prune", "--quiet"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            log(f"{project}: fetch failed: {completed.stderr.strip()[:200]}")
    head = diffaudit.head_sha(path)
    last = row["last_sha"]
    if not last:
        store.set_last_sha(conn, project, head)
        log(f"{project}: baseline {head[:12]}")
        return 0
    if head == last:
        store.set_last_sha(conn, project, head)
        return 0

    if not diffaudit.is_ancestor(path, last, head):
        report = {
            "project": project,
            "sha": head,
            "parent": last,
            "subject": "history rewrite or non-fast-forward update",
            "author": "",
            "committed_at": store.now(),
            "kind": "history-rewrite",
            "score": 70,
            "verdict": "critical",
            "summary": "last watched commit is not an ancestor of HEAD",
            "findings": [
                {
                    "rule": "history-rewrite",
                    "severity": "critical",
                    "path": "",
                    "why": "观察点之后的提交历史被重写，无法用普通 diff 追溯全部变化",
                    "evidence": [{"line": 0, "text": f"{last} -> {head}"}],
                }
            ],
            "stat": {"files": [], "added": 0, "removed": 0},
            "truncated": False,
            "analyzed_at": store.now(),
        }
        json_path, md_path = diffaudit.write_report(report, WATCH_ROOT / project)
        event = {
            **report,
            "report_json": str(json_path),
            "report_md": str(md_path),
            "recommended_action": "inspect rewritten history and run a full audit",
        }
        event_id = store.insert_event(conn, event)
        queued = enqueue(conn, event_id, event)
        log(f"{project}: history rewrite {last[:12]} -> {head[:12]} queued={queued}")
        commits = diffaudit.git(
            path, ["rev-list", "--reverse", f"--max-count={limit}", "HEAD"]
        ).stdout.split()
        last = commits[0] if commits else head
        store.set_last_sha(conn, project, last)
        row = store.get_repo(conn, project)

    commits = diffaudit.git(path, ["rev-list", "--reverse", f"{last}..{head}"]).stdout.split()
    if len(commits) > limit:
        commits = commits[-limit:]
    if not commits and initial_scan:
        commits = [head]
    count = 0
    for sha in commits:
        try:
            process_commit(conn, project, path, sha)
            count += 1
        except Exception as exc:
            log(f"{project}: failed to analyze {sha[:12]}: {exc}")
    store.set_last_sha(conn, project, head)
    return count


def cmd_add(args):
    path = Path(args.path).resolve()
    if not require_git(path):
        print(json.dumps({"ok": False, "error": f"not a git repo: {path}"}, ensure_ascii=False))
        return 2
    project = args.project or path.name
    conn = store.connect()
    row = store.upsert_repo(conn, project, path, repo_url(path))
    head = diffaudit.head_sha(path)
    if not row["last_sha"] or args.reset:
        store.set_last_sha(conn, project, head, deep=args.deep)
    if args.deep:
        store.set_last_sha(conn, project, "", deep=True)
        store.set_last_sha(conn, project, head, deep=True)
        deep_dir = WATCH_ROOT / project
        deep_dir.mkdir(parents=True, exist_ok=True)
        (deep_dir / "DEEP-SCAN.md").write_text(
            f"# Deep scan requested: {project}\n\n"
            f"- path: {path}\n- baseline: {head}\n\n"
            "Run the existing mining pipeline for the initial deep scan:\n\n"
            f"```bash\nbash run.sh {path} --project {project}\n```\n\n"
            "After it completes, commit-level provenance continues with `watch.py poll`.\n",
            encoding="utf-8",
        )
    conn.close()
    print(
        json.dumps(
            {"ok": True, "project": project, "path": str(path), "head": head},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_poll(args):
    conn = store.connect()
    rows = [store.get_repo(conn, args.project)] if args.project else store.list_repos(conn)
    total = 0
    for row in rows:
        if not row:
            continue
        total += poll_repo(
            conn, row, fetch=args.fetch, limit=args.limit, initial_scan=args.initial_scan
        )
    write_state(conn)
    conn.close()
    print(
        json.dumps(
            {"ok": True, "new_events": total, "state": str(STATE_OUT)}, ensure_ascii=False, indent=2
        )
    )
    return 0


def build_brief(conn, limit=10):
    events = [store.event_dict(row) for row in store.list_events(conn, limit=200)]
    ranked = sorted(
        events,
        key=lambda e: (
            {"critical": 4, "high": 3, "review": 2, "low": 1}.get(e["verdict"], 0),
            e["created_at"],
        ),
        reverse=True,
    )
    top = ranked[:limit]
    return {
        "generated_at": store.now(),
        "counts": store.counts(conn),
        "top": [
            {
                "id": e["id"],
                "project": e["project"],
                "sha": e["sha"],
                "verdict": e["verdict"],
                "score": e["score"],
                "subject": e["subject"],
                "summary": e["summary"],
                "report_md": e["report_md"],
                "seen": bool(e["seen"]),
            }
            for e in top
        ],
    }


def write_state(conn):
    repos = []
    for row in store.list_repos(conn):
        recent = store.list_events(conn, project=row["project"], limit=5)
        repos.append(
            {
                "project": row["project"],
                "path": row["path"],
                "url": row["url"],
                "last_sha": row["last_sha"],
                "last_checked": row["last_checked"],
                "deep_scan_at": row["deep_scan_at"],
                "recent": [
                    {
                        "sha": e["sha"],
                        "verdict": e["verdict"],
                        "score": e["score"],
                        "subject": e["subject"],
                        "report_md": e["report_md"],
                    }
                    for e in recent
                ],
            }
        )
    payload = {
        "generated_at": store.now(),
        "counts": store.counts(conn),
        "repos": repos,
        "brief": build_brief(conn),
    }
    store.dump_json(STATE_OUT, payload)
    return payload


def cmd_status(args):
    conn = store.connect()
    payload = write_state(conn)
    conn.close()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"repos={len(payload['repos'])} counts={payload['counts']}")
        for repo in payload["repos"]:
            print(f"{repo['project']:26} {repo['last_sha'][:12]:12} {repo['last_checked'] or '-'}")
    return 0


def cmd_brief(args):
    conn = store.connect()
    write_state(conn)
    brief = build_brief(conn, limit=args.limit)
    conn.close()
    if args.json:
        print(json.dumps(brief, ensure_ascii=False, indent=2))
        return 0
    print(f"watch brief: {brief['generated_at']}")
    print(f"counts: {brief['counts']}")
    if not brief["top"]:
        print("nothing needs attention")
    for item in brief["top"]:
        print(f"[{item['verdict']}] {item['project']} {item['sha'][:12]} {item['subject']}")
        print(f"  {item['summary']}")
        print(f"  {item['report_md']}")
    return 0


def cmd_watch(args):
    conn = store.connect()
    try:
        while True:
            rows = store.list_repos(conn)
            total = 0
            for row in rows:
                try:
                    total += poll_repo(conn, row, fetch=args.fetch, limit=args.limit)
                except Exception as exc:
                    log(f"{row['project']}: poll failed: {exc}")
            write_state(conn)
            log(f"cycle complete new_events={total} sleep={args.interval}s")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        conn.close()


def cmd_seen(args):
    conn = store.connect()
    store.mark_seen(conn, args.id)
    write_state(conn)
    conn.close()
    print(json.dumps({"ok": True, "id": args.id}, ensure_ascii=False))
    return 0


def llm_audit(project, sha, timeout=300):
    report_path = WATCH_ROOT / project / f"{sha[:12]}.json"
    if not report_path.exists():
        raise RuntimeError(f"missing static report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    task_path = WATCH_ROOT / project / f"{sha[:12]}.llm-task.json"
    out_path = WATCH_ROOT / project / f"{sha[:12]}.llm-audit.json"
    task = {
        "project": project,
        "sha": sha,
        "repo_path": str(report.get("repo_path") or ""),
        "static_report": str(report_path),
        "output": str(out_path),
    }
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prompt = (
        f"{language_directive()}\n\n"
        f"Read {task_path} and follow the diff-auditor instructions. "
        f"Review commit {sha} and write {out_path}. "
        "Do not execute repository code or fetch anything."
    )
    log_path = WATCH_ROOT / project / f"{sha[:12]}.llm.log"
    try:
        completed = subprocess.run(
            [
                "claude",
                "--agent",
                "diff-auditor",
                "--permission-mode=bypassPermissions",
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=ROOT,
        )
        log_text = (
            f"# returncode\n{completed.returncode}\n\n"
            f"# stdout\n{completed.stdout}\n\n"
            f"# stderr\n{completed.stderr}\n"
        )
    except subprocess.TimeoutExpired as exc:
        log_path.write_text(
            f"# TIMEOUT after {timeout}s\n\n"
            f"# stdout\n{exc.stdout or ''}\n\n"
            f"# stderr\n{exc.stderr or ''}\n",
            encoding="utf-8",
        )
        raise RuntimeError(f"diff-auditor timed out after {timeout}s") from exc
    log_path.write_text(log_text, encoding="utf-8")
    if not out_path.exists():
        raise RuntimeError(f"diff-auditor did not write {out_path}")
    audit = json.loads(out_path.read_text(encoding="utf-8"))
    report["llm"] = audit
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def cmd_llm(args):
    db = store.connect()
    try:
        row = store.get_repo(db, args.project)
    finally:
        db.close()
    if not row:
        print(json.dumps({"ok": False, "error": "unknown project"}, ensure_ascii=False))
        return 2
    try:
        audit = llm_audit(args.project, args.sha, timeout=args.timeout)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(WATCH_ROOT / args.project / f"{args.sha[:12]}.llm-audit.json"),
                "audit": audit,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_remove(args):
    conn = store.connect()
    conn.execute("DELETE FROM events WHERE project = ?", (args.project,))
    conn.execute("DELETE FROM repos WHERE project = ?", (args.project,))
    conn.commit()
    conn.close()
    if args.purge:
        import shutil

        shutil.rmtree(WATCH_ROOT / args.project, ignore_errors=True)
        for path in QUEUE_DIR.glob(f"{args.project}-*"):
            path.unlink(missing_ok=True)
    print(json.dumps({"ok": True, "removed": args.project}, ensure_ascii=False))
    return 0


def cmd_queue(args):
    items = sorted(QUEUE_DIR.glob("*.json")) if QUEUE_DIR.exists() else []
    payload = []
    for path in items:
        try:
            payload.append({"path": str(path), **json.loads(path.read_text(encoding="utf-8"))})
        except Exception:
            continue
    print(json.dumps(payload[-args.limit :], ensure_ascii=False, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Continuous repo watch and per-commit provenance audit"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("--project", default="")
    add.add_argument("--path", required=True)
    add.add_argument("--deep", action="store_true")
    add.add_argument("--reset", action="store_true")
    add.set_defaults(func=cmd_add)

    poll = sub.add_parser("poll")
    poll.add_argument("--project", default="")
    poll.add_argument("--fetch", action="store_true")
    poll.add_argument("--limit", type=int, default=50)
    poll.add_argument("--initial-scan", action="store_true")
    poll.set_defaults(func=cmd_poll)

    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    brief = sub.add_parser("brief")
    brief.add_argument("--limit", type=int, default=10)
    brief.add_argument("--json", action="store_true")
    brief.set_defaults(func=cmd_brief)

    watch = sub.add_parser("watch")
    watch.add_argument("--interval", type=int, default=300)
    watch.add_argument("--fetch", action="store_true")
    watch.add_argument("--limit", type=int, default=50)
    watch.set_defaults(func=cmd_watch)

    seen = sub.add_parser("seen")
    seen.add_argument("--id", type=int, required=True)
    seen.set_defaults(func=cmd_seen)

    queue = sub.add_parser("queue")
    queue.add_argument("--limit", type=int, default=20)
    queue.set_defaults(func=cmd_queue)

    llm = sub.add_parser("llm-audit")
    llm.add_argument("--project", required=True)
    llm.add_argument("--sha", required=True)
    llm.add_argument("--timeout", type=int, default=300)
    llm.set_defaults(func=cmd_llm)

    remove = sub.add_parser("remove")
    remove.add_argument("--project", required=True)
    remove.add_argument("--purge", action="store_true")
    remove.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
