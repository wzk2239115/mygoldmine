#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diffaudit  # noqa: E402
import store  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WATCH_ROOT = ROOT / "runs" / "watch"
QUEUE_DIR = WATCH_ROOT / "queue"
STATE_OUT = ROOT / "ui" / "data" / "watch-state.json"
DISPATCH_STATE = WATCH_ROOT / "dispatch-state.json"
DISPATCH_LOCK = WATCH_ROOT / ".dispatch.lock"
WORKTREE_ROOT = WATCH_ROOT / "worktrees"
DISPATCH_LOG_DIR = WATCH_ROOT / "dispatch"
DEFAULT_WINDOW_HOURS = 24
DEFAULT_FETCH_DEPTH = 50


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


def current_branch(path):
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value and value != "HEAD" else "detached"


def enqueue(conn, event_id, event):
    if event["verdict"] not in {"critical", "high"}:
        return ""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"{event['project']}-{event['sha'][:12]}.json"
    payload = {
        "event_id": event_id,
        "project": event["project"],
        "sha": event["sha"],
        "branch": event.get("branch") or "",
        "repo_path": event.get("repo_path") or "",
        "verdict": event["verdict"],
        "score": event["score"],
        "subject": event["subject"],
        "report_json": event["report_json"],
        "recommended_action": "自动派发到 run.sh；如失败可在队列中重试",
        "queued_at": store.now(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def process_commit(conn, project, repo, sha):
    report = diffaudit.analyze(repo, sha)
    report["project"] = project
    report["repo_path"] = str(repo)
    report["branch"] = current_branch(repo)
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



def _load_dispatch_state():
    try:
        payload = json.loads(DISPATCH_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(payload.get("items"), dict):
        payload["items"] = {}
    return payload


def _write_dispatch_state(payload):
    payload["updated_at"] = store.now()
    store.dump_json(DISPATCH_STATE, payload)


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def _live_runs(project=""):
    runs_root = ROOT / "runs"
    if not runs_root.is_dir():
        return []
    live = []
    for status_path in runs_root.glob("*/*.meta/status.json"):
        if project and status_path.parent.parent.name != project:
            continue
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        state = str(status.get("state") or "")
        if state not in {"starting", "running", "stopping"}:
            continue
        meta = status_path.parent
        supervisor = ""
        try:
            supervisor = (meta / "supervisor.pid").read_text(encoding="utf-8").strip()
        except OSError:
            pass
        if supervisor and not _pid_alive(supervisor):
            continue
        if not supervisor:
            updated = str(status.get("updated_at") or status.get("started_at") or "")
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(
                    updated.replace("Z", "+00:00")
                )
            except ValueError:
                age = timedelta(days=1)
            if age > timedelta(minutes=30):
                continue
        live.append({
            "project": status.get("project") or status_path.parent.parent.name,
            "run_dir": str(meta.with_suffix("")) if str(meta).endswith(".meta") else str(meta),
            "state": state,
            "supervisor_pid": supervisor,
            "commit": status.get("commit") or "",
            "branch": status.get("branch") or "",
        })
    return live


def _existing_run(project, sha):
    project_dir = ROOT / "runs" / project
    if not project_dir.is_dir():
        return ""
    for meta_path in sorted(project_dir.glob("*/run-meta.json"), reverse=True):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        commit = str(meta.get("commit") or "")
        if commit and (commit == sha or commit.startswith(sha) or sha.startswith(commit)):
            return str(meta_path.parent)
    return ""


def _prepare_source(repo_path, project, sha):
    repo = Path(repo_path)
    if not repo.is_dir():
        return "", "missing_repo"
    target = WORKTREE_ROOT / project / sha[:12]
    if (target / ".git").exists():
        return str(target), "worktree"
    target.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(target), sha],
        capture_output=True, text=True, timeout=300,
    )
    if completed.returncode != 0:
        fetched = subprocess.run(
            ["git", "-C", str(repo), "fetch", "--quiet", "origin", sha],
            capture_output=True, text=True, timeout=300,
        )
        if fetched.returncode == 0:
            completed = subprocess.run(
                ["git", "-C", str(repo), "worktree", "add", "--detach", str(target), sha],
                capture_output=True, text=True, timeout=300,
            )
    if completed.returncode == 0:
        return str(target), "worktree"
    log(f"{project}: worktree unavailable for {sha[:12]}, fallback to {repo}")
    return str(repo), "repo"


def dispatch_once(limit=1):
    DISPATCH_LOCK.parent.mkdir(parents=True, exist_ok=True)
    lock = open(DISPATCH_LOCK, "w", encoding="utf-8")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"ok": True, "busy": True, "reason": "another dispatcher is running"}
    try:
        state = _load_dispatch_state()
        active = state.get("active") if isinstance(state.get("active"), dict) else None
        if active:
            live = _live_runs(str(active.get("project") or ""))
            if _pid_alive(active.get("pid")) or live:
                if live:
                    active = {**active, "run": live[0]}
                    state["active"] = active
                return {"ok": True, "busy": True, "active": active}
            exit_file = Path(str(active.get("exit_file") or ""))
            try:
                code = int(exit_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                code = None
            key = active.get("key") or ""
            if key:
                state["items"][key] = {
                    **state["items"].get(key, {}),
                    "status": "completed" if code == 0 else "failed",
                    "exit_code": code,
                    "finished_at": store.now(),
                }
            state["active"] = None

        live = _live_runs()
        live_projects = {item.get("project") for item in live}
        for key, item in list(state["items"].items()):
            if not isinstance(item, dict) or item.get("status") != "running":
                continue
            if item.get("project") in live_projects:
                continue
            existing = _existing_run(str(item.get("project") or ""), str(item.get("sha") or ""))
            finished = "completed" if existing else "failed"
            state["items"][key] = {
                **item,
                "status": finished,
                "run_dir": existing or item.get("run_dir", ""),
                "finished_at": store.now(),
            }
        if live:
            _write_dispatch_state(state)
            return {"ok": True, "busy": True, "active": None, "live": live[0]}

        queue_paths = sorted(QUEUE_DIR.glob("*.json")) if QUEUE_DIR.exists() else []
        queue = []
        for path in queue_paths:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            item["queue_path"] = str(path)
            queue.append(item)
        queue.sort(
            key=lambda item: (
                {"critical": 2, "high": 1}.get(item.get("verdict"), 0),
                int(item.get("score") or 0),
                item.get("queued_at", ""),
            ),
            reverse=True,
        )
        try:
            db = store.connect()
            repo_paths = {row["project"]: row["path"] for row in store.list_repos(db)}
            db.close()
        except Exception:
            repo_paths = {}

        started = 0
        for item in queue:
            if started >= max(1, limit):
                break
            project = str(item.get("project") or "")
            sha = str(item.get("sha") or "")
            if not project or not sha:
                continue
            key = f"{project}:{sha}"
            previous = state["items"].get(key) if isinstance(state["items"].get(key), dict) else {}
            if previous.get("status") in {"running", "completed", "reused"}:
                continue
            existing = _existing_run(project, sha)
            if existing:
                state["items"][key] = {
                    "project": project,
                    "sha": sha,
                    "branch": item.get("branch", ""),
                    "status": "reused",
                    "run_dir": existing,
                    "updated_at": store.now(),
                }
                continue
            repo_path = str(item.get("repo_path") or repo_paths.get(project) or "")
            if not repo_path:
                state["items"][key] = {
                    "project": project,
                    "sha": sha,
                    "status": "failed",
                    "reason": "missing repo_path",
                    "updated_at": store.now(),
                }
                continue
            source, mode = _prepare_source(repo_path, project, sha)
            if not source:
                state["items"][key] = {
                    "project": project,
                    "sha": sha,
                    "status": "failed",
                    "reason": mode,
                    "updated_at": store.now(),
                }
                continue
            DISPATCH_LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_path = DISPATCH_LOG_DIR / f"{project}-{sha[:12]}.log"
            exit_file = DISPATCH_LOG_DIR / f"{project}-{sha[:12]}.exit"
            exit_file.unlink(missing_ok=True)
            branch = str(item.get("branch") or current_branch(repo_path))
            item["branch"] = branch
            item["repo_path"] = repo_path
            try:
                Path(str(item["queue_path"])).write_text(
                    json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            except OSError:
                pass
            command = (
                f"{shlex.quote(str(ROOT / 'run.sh'))} {shlex.quote(source)} "
                f"--project {shlex.quote(project)}"
            )
            wrapper = (
                f"{command} > {shlex.quote(str(log_path))} 2>&1; "
                f"echo $? > {shlex.quote(str(exit_file))}"
            )
            env = os.environ.copy()
            env["TARGET_BRANCH"] = branch
            env["WATCH_BRANCH"] = branch
            env["WATCH_SHA"] = sha
            env["WATCH_PROJECT"] = project
            process = subprocess.Popen(
                ["bash", "-c", wrapper], cwd=ROOT, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            active = {
                "key": key,
                "project": project,
                "sha": sha,
                "branch": branch,
                "source": source,
                "source_mode": mode,
                "pid": process.pid,
                "log": str(log_path),
                "exit_file": str(exit_file),
                "started_at": store.now(),
            }
            state["active"] = active
            state["items"][key] = {**active, "status": "running", "updated_at": store.now()}
            started += 1
            log(
                f"dispatch {project} {sha[:12]} branch={branch or '-'} "
                f"mode={mode} pid={process.pid}"
            )
        _write_dispatch_state(state)
        return {"ok": True, "started": started, "active": state.get("active")}
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def dispatch_status():
    state = _load_dispatch_state()
    active = state.get("active") if isinstance(state.get("active"), dict) else None
    live = _live_runs()
    items = state.get("items", {})
    if live and not live[0].get("sha"):
        for item in items.values():
            if (
                isinstance(item, dict)
                and item.get("project") == live[0]["project"]
                and item.get("sha")
            ):
                live[0] = {
                    **live[0],
                    "sha": item.get("sha"),
                    "commit": item.get("sha"),
                    "branch": item.get("branch") or live[0].get("branch", ""),
                }
                break
    alive = bool((active and _pid_alive(active.get("pid"))) or live)
    if active and live and not active.get("run"):
        active = {**active, "run": live[0]}
    return {
        "ok": True,
        "active": active,
        "alive": alive,
        "live": live[0] if live else None,
        "items": state.get("items", {}),
    }


def cmd_dispatch(args):
    if args.status:
        print(json.dumps(dispatch_status(), ensure_ascii=False, indent=2))
        return 0
    if args.loop:
        while True:
            result = dispatch_once(limit=args.limit)
            log(f"dispatch cycle: {json.dumps(result, ensure_ascii=False)}")
            time.sleep(max(1, args.interval))
    result = dispatch_once(limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def window_start(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def fetch_repo(path, ref, shallow, depth):
    """Fetch the watched branch.

    Shallow clones (the default for ``targets/``) are fetched with a bounded
    ``--depth`` so a large repository does not try to transfer its whole
    history on every poll. Full clones use a plain fetch.
    """
    branch = ref.split("/", 1)[1] if ref.startswith("origin/") else ""
    if branch == "HEAD":
        branch = ""
    args = ["fetch", "--prune", "--quiet", "--no-tags"]
    if shallow and depth and depth > 0:
        args.append(f"--depth={depth}")
    args.append("origin")
    if branch:
        args.append(branch)
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        timeout=600,
    )


def poll_repo(
    conn, row, fetch=False, limit=50, initial_scan=False, window_hours=DEFAULT_WINDOW_HOURS,
    fetch_depth=DEFAULT_FETCH_DEPTH,
):
    project, path = row["project"], Path(row["path"])
    if not path.is_dir():
        log(f"{project}: path missing: {path}")
        return 0
    shallow = diffaudit.is_shallow(path)
    if fetch:
        ref_hint, _ = diffaudit.resolve_head(path)
        if ref_hint.startswith("origin/"):
            try:
                completed = fetch_repo(path, ref_hint, shallow, fetch_depth)
            except subprocess.TimeoutExpired:
                log(f"{project}: fetch timed out, using last known remote ref")
            else:
                if completed.returncode != 0:
                    log(f"{project}: fetch failed: {completed.stderr.strip()[:200]}")
    ref, head = diffaudit.resolve_head(path)
    last = row["last_sha"]
    since = window_start(window_hours) if window_hours and window_hours > 0 else ""

    if not last:
        commits = diffaudit.commits_between(path, "", head, since=since)
        if not commits:
            store.set_last_sha(conn, project, head)
            log(f"{project}: baseline {head[:12]} via {ref}")
            return 0
    elif head == last:
        store.set_last_sha(conn, project, head)
        return 0
    else:
        ancestor = diffaudit.is_ancestor(path, last, head)
        if not ancestor and shallow:
            log(f"{project}: shallow clone cannot verify ancestry; reviewing window only")
        elif not ancestor:
            report = {
                "project": project,
                "sha": head,
                "branch": current_branch(path),
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
                path, ["rev-list", "--reverse", f"--max-count={limit}", head]
            ).stdout.split()
            last = commits[0] if commits else head
            store.set_last_sha(conn, project, last)
            row = store.get_repo(conn, project)

        commits = diffaudit.commits_between(path, last, head, since=since)
        if not commits and initial_scan:
            commits = [head]

    if len(commits) > limit:
        commits = commits[-limit:]
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
        try:
            total += poll_repo(
                conn,
                row,
                fetch=args.fetch,
                limit=args.limit,
                initial_scan=args.initial_scan,
                window_hours=args.window_hours,
                fetch_depth=args.fetch_depth,
            )
        except Exception as exc:
            log(f"{row['project']}: poll failed: {exc}")
    write_state(conn)
    conn.close()
    dispatched = dispatch_once(limit=1) if args.auto_run else None
    print(
        json.dumps(
            {"ok": True, "new_events": total, "state": str(STATE_OUT), "dispatch": dispatched},
            ensure_ascii=False, indent=2,
        )
    )
    return 0


def build_brief(conn, limit=10):
    branches = {
        row["project"]: current_branch(row["path"])
        for row in store.list_repos(conn)
        if Path(row["path"]).is_dir()
    }
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
                "branch": branches.get(e["project"], ""),
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
                "branch": current_branch(row["path"]) if Path(row["path"]).is_dir() else "",
                "last_checked": row["last_checked"],
                "deep_scan_at": row["deep_scan_at"],
                "recent": [
                    {
                        "sha": e["sha"],
                        "verdict": e["verdict"],
                        "score": e["score"],
                        "subject": e["subject"],
                        "branch": current_branch(row["path"]) if Path(row["path"]).is_dir() else "",
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
        "dispatch": dispatch_status(),
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
                    total += poll_repo(
                        conn,
                        row,
                        fetch=args.fetch,
                        limit=args.limit,
                        window_hours=args.window_hours,
                        fetch_depth=args.fetch_depth,
                    )
                except Exception as exc:
                    log(f"{row['project']}: poll failed: {exc}")
            write_state(conn)
            if args.auto_run:
                try:
                    dispatch_once(limit=1)
                except Exception as exc:
                    log(f"auto dispatch failed: {exc}")
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

    dispatch = sub.add_parser("dispatch")
    dispatch.add_argument("--once", action="store_true")
    dispatch.add_argument("--loop", action="store_true")
    dispatch.add_argument("--interval", type=int, default=60)
    dispatch.add_argument("--limit", type=int, default=1)
    dispatch.add_argument("--status", action="store_true")
    dispatch.set_defaults(func=cmd_dispatch)

    poll = sub.add_parser("poll")
    poll.add_argument("--project", default="")
    poll.add_argument("--fetch", action="store_true")
    poll.add_argument("--limit", type=int, default=50)
    poll.add_argument("--initial-scan", action="store_true")
    poll.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    poll.add_argument("--fetch-depth", type=int, default=DEFAULT_FETCH_DEPTH)
    poll.add_argument("--auto-run", action="store_true")
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
    watch.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    watch.add_argument("--fetch-depth", type=int, default=DEFAULT_FETCH_DEPTH)
    watch.add_argument("--auto-run", action="store_true")
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
