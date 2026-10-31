#!/usr/bin/env python3
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "runs" / "watch" / "watch.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    project TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    url TEXT DEFAULT '',
    last_sha TEXT DEFAULT '',
    added_at TEXT NOT NULL,
    last_checked TEXT DEFAULT '',
    deep_scan_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    sha TEXT NOT NULL,
    parent TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    author TEXT DEFAULT '',
    committed_at TEXT DEFAULT '',
    kind TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    verdict TEXT NOT NULL DEFAULT 'low',
    summary TEXT DEFAULT '',
    report_json TEXT DEFAULT '',
    report_md TEXT DEFAULT '',
    recommended_action TEXT DEFAULT '',
    seen INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(project, sha, kind)
);

CREATE INDEX IF NOT EXISTS events_project ON events(project, created_at DESC);
CREATE INDEX IF NOT EXISTS events_verdict ON events(verdict, created_at DESC);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_repo(conn, project, path, url=""):
    row = conn.execute("SELECT * FROM repos WHERE project = ?", (project,)).fetchone()
    if row:
        conn.execute(
            "UPDATE repos SET path = ?, url = ? WHERE project = ?",
            (str(path), url or row["url"], project),
        )
    else:
        conn.execute(
            "INSERT INTO repos(project, path, url, added_at) VALUES (?, ?, ?, ?)",
            (project, str(path), url, now()),
        )
    conn.commit()
    return conn.execute("SELECT * FROM repos WHERE project = ?", (project,)).fetchone()


def get_repo(conn, project):
    return conn.execute("SELECT * FROM repos WHERE project = ?", (project,)).fetchone()


def list_repos(conn):
    return conn.execute("SELECT * FROM repos ORDER BY project").fetchall()


def set_last_sha(conn, project, sha, deep=False):
    if deep:
        conn.execute(
            "UPDATE repos SET last_sha = ?, last_checked = ?, deep_scan_at = ? WHERE project = ?",
            (sha, now(), now(), project),
        )
    else:
        conn.execute(
            "UPDATE repos SET last_sha = ?, last_checked = ? WHERE project = ?",
            (sha, now(), project),
        )
    conn.commit()


def insert_event(conn, event):
    cur = conn.execute(
        """
        INSERT OR REPLACE INTO events(
            project, sha, parent, subject, author, committed_at, kind, score,
            verdict, summary, report_json, report_md, recommended_action, seen, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["project"],
            event["sha"],
            event.get("parent", ""),
            event.get("subject", ""),
            event.get("author", ""),
            event.get("committed_at", ""),
            event["kind"],
            int(event.get("score", 0)),
            event.get("verdict", "low"),
            event.get("summary", ""),
            event.get("report_json", ""),
            event.get("report_md", ""),
            event.get("recommended_action", ""),
            int(event.get("seen", 0)),
            event.get("created_at") or now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_events(conn, project=None, verdict=None, limit=50, unseen_only=False):
    clauses, values = [], []
    if project:
        clauses.append("project = ?")
        values.append(project)
    if verdict:
        clauses.append("verdict = ?")
        values.append(verdict)
    if unseen_only:
        clauses.append("seen = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(limit)
    return conn.execute(
        f"SELECT * FROM events {where} ORDER BY created_at DESC, id DESC LIMIT ?", values
    ).fetchall()


def mark_seen(conn, event_id):
    conn.execute("UPDATE events SET seen = 1 WHERE id = ?", (event_id,))
    conn.commit()


def counts(conn):
    rows = conn.execute("SELECT verdict, COUNT(*) AS n FROM events GROUP BY verdict").fetchall()
    return {row["verdict"]: row["n"] for row in rows}


def event_dict(row):
    data = dict(row)
    for key in ("report_json", "report_md"):
        value = data.get(key) or ""
        data[key] = value
    return data


def dump_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
