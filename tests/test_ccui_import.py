from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "ccui"
    / "import_runs.py"
)
spec = importlib.util.spec_from_file_location("ccui_import_runs", SCRIPT)
assert spec and spec.loader
ccui = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ccui
spec.loader.exec_module(ccui)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _run(tmp_path: Path, project: str = "demo") -> Path:
    run = tmp_path / "runs" / project / "20260101T000000Z"
    run.mkdir(parents=True)
    _write(
        run / "run-meta.json",
        {
            "project": project,
            "commit": "abcdef1234567890",
            "model": "test-model",
            "agent": "security-orchestrator",
            "started_at": "2026-01-01T00:00:00Z",
        },
    )
    rows = [
        {
            "type": "system",
            "subtype": "init",
            "session_id": "sess-demo",
            "cwd": "/workspace/repo",
            "model": "test-model",
        },
        {
            "type": "assistant",
            "uuid": "assistant-1",
            "timestamp": "2026-01-01T00:00:01Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "checking auth"}],
            },
        },
        {
            "type": "user",
            "uuid": "user-1",
            "timestamp": "2026-01-01T00:00:02Z",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "content": "ok"}],
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "result": "audit complete",
        },
    ]
    (run / "raw.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return run


def test_convert_run_writes_claude_session(tmp_path: Path) -> None:
    run = _run(tmp_path)
    home = tmp_path / "home"
    result = ccui.convert_run(run, home, "demo")
    assert result is not None
    session_id, path = result
    assert session_id == "sess-demo"
    assert path.is_file()
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["type"] == "user"
    assert rows[0]["sessionId"] == session_id
    assert rows[1]["type"] == "custom-title"
    assert any(row["type"] == "assistant" for row in rows)
    assert any(
        row["type"] == "assistant"
        and "audit complete" in json.dumps(row, ensure_ascii=False)
        for row in rows
    )
    history = (home / ".claude" / "history.jsonl").read_text()
    assert session_id in history


def test_run_dirs_excludes_smoke_by_default(tmp_path: Path) -> None:
    demo = _run(tmp_path, "demo")
    smoke = _run(tmp_path, "smoke-demo")
    runs_root = tmp_path / "runs"
    assert ccui._run_dirs(runs_root, None, True) == [demo]
    assert set(ccui._run_dirs(runs_root, None, True, True)) == {demo, smoke}
