from __future__ import annotations

import json
import time

from scripts.watch import watch


def test_dispatch_launches_run_with_branch_and_commit(tmp_path, monkeypatch):
    queue = tmp_path / "runs" / "watch" / "queue"
    queue.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    run_sh = tmp_path / "run.sh"
    run_sh.write_text(
        """#!/usr/bin/env bash
set -eu
printf '%s|%s|%s|%s\\n' "$WATCH_PROJECT" "$WATCH_SHA" "$TARGET_BRANCH" "$1" > "$DISPATCH_MARKER"
exit 0
""",
        encoding="utf-8",
    )
    run_sh.chmod(0o755)
    (queue / "demo-deadbeef.json").write_text(
        json.dumps({
            "project": "demo",
            "sha": "deadbeefcafebabe",
            "branch": "release/1.0",
            "repo_path": str(repo),
            "verdict": "high",
            "score": 30,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(watch, "ROOT", tmp_path)
    monkeypatch.setattr(watch, "QUEUE_DIR", queue)
    monkeypatch.setattr(watch, "DISPATCH_STATE", tmp_path / "dispatch-state.json")
    monkeypatch.setattr(watch, "DISPATCH_LOCK", tmp_path / ".dispatch.lock")
    monkeypatch.setattr(watch, "WORKTREE_ROOT", tmp_path / "worktrees")
    monkeypatch.setattr(watch, "DISPATCH_LOG_DIR", tmp_path / "dispatch")
    monkeypatch.setenv("DISPATCH_MARKER", str(tmp_path / "dispatch.marker"))

    result = watch.dispatch_once(limit=1)
    assert result["ok"] is True
    assert result["started"] == 1
    assert result["active"]["branch"] == "release/1.0"

    marker = tmp_path / "dispatch.marker"
    for _ in range(40):
        if marker.exists():
            break
        time.sleep(0.05)
    assert marker.exists()
    fields = marker.read_text(encoding="utf-8").strip().split("|")
    assert fields[:3] == ["demo", "deadbeefcafebabe", "release/1.0"]
    assert fields[3] == str(repo)
    state = json.loads((tmp_path / "dispatch-state.json").read_text(encoding="utf-8"))
    assert state["items"]["demo:deadbeefcafebabe"]["status"] == "running"


def test_dispatch_reuses_existing_run_for_same_commit(tmp_path, monkeypatch):
    queue = tmp_path / "runs" / "watch" / "queue"
    queue.mkdir(parents=True)
    run_dir = tmp_path / "runs" / "demo" / "20260101T000000Z"
    run_dir.mkdir(parents=True)
    (run_dir / "run-meta.json").write_text(
        json.dumps({"commit": "deadbeefcafebabe"}), encoding="utf-8"
    )
    (queue / "demo-deadbeef.json").write_text(
        json.dumps({
            "project": "demo",
            "sha": "deadbeefcafebabe",
            "branch": "main",
            "repo_path": str(tmp_path / "repo"),
            "verdict": "critical",
            "score": 40,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(watch, "ROOT", tmp_path)
    monkeypatch.setattr(watch, "QUEUE_DIR", queue)
    monkeypatch.setattr(watch, "DISPATCH_STATE", tmp_path / "dispatch-state.json")
    monkeypatch.setattr(watch, "DISPATCH_LOCK", tmp_path / ".dispatch.lock")
    monkeypatch.setattr(watch, "WORKTREE_ROOT", tmp_path / "worktrees")
    monkeypatch.setattr(watch, "DISPATCH_LOG_DIR", tmp_path / "dispatch")

    result = watch.dispatch_once(limit=1)
    assert result["started"] == 0
    state = json.loads((tmp_path / "dispatch-state.json").read_text(encoding="utf-8"))
    assert state["items"]["demo:deadbeefcafebabe"]["status"] == "reused"
    assert state["items"]["demo:deadbeefcafebabe"]["run_dir"] == str(run_dir)
