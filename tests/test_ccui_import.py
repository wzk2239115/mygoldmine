from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ccui" / "import_runs.py"
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
        row["type"] == "assistant" and "audit complete" in json.dumps(row, ensure_ascii=False)
        for row in rows
    )
    history = (home / ".claude" / "history.jsonl").read_text()
    assert session_id in history

    sidecar_path = run.with_name(run.name + ".meta") / "ccui-session.json"
    assert sidecar_path.is_file()
    sidecar = json.loads(sidecar_path.read_text())
    assert sidecar["sessionId"] == session_id
    assert sidecar["project"] == "demo"
    assert sidecar["runId"] == "20260101T000000Z"
    assert sidecar["sessionFile"] == str(path)
    assert sidecar["messages"] >= 2
    assert sidecar["importedAt"]


def test_run_dirs_excludes_smoke_by_default(tmp_path: Path) -> None:
    demo = _run(tmp_path, "demo")
    smoke = _run(tmp_path, "smoke-demo")
    runs_root = tmp_path / "runs"
    assert ccui._run_dirs(runs_root, None, True) == [demo]
    assert set(ccui._run_dirs(runs_root, None, True, True)) == {demo, smoke}


def test_run_dirs_wanted_runs_pick_specific_run(tmp_path: Path) -> None:
    _run(tmp_path, "demo")
    newer = _run(tmp_path, "other")
    runs_root = tmp_path / "runs"
    assert ccui._run_dirs(runs_root, None, True, False, {"other/20260101T000000Z"}) == [newer]
    # A run without raw.jsonl is never picked.
    assert ccui._run_dirs(runs_root, None, True, False, {"missing/20260101T000000Z"}) == []


def _append_events(run: Path, events: list[dict]) -> None:
    with (run / "raw.jsonl").open("a") as stream:
        for event in events:
            stream.write(json.dumps(event) + "\n")


def test_subagent_prompt_is_not_flattened_into_human_conversation(tmp_path: Path) -> None:
    run = _run(tmp_path)
    prompt = "Analyze config trust boundary"
    _append_events(
        run,
        [
            {
                "type": "system",
                "subtype": "task_started",
                "tool_use_id": "call-agent",
                "task_id": "agent-config",
                "description": "Config analysis",
            },
            {
                "type": "assistant",
                "uuid": "launch-1",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call-agent",
                            "name": "Agent",
                            "input": {"prompt": prompt},
                        }
                    ],
                },
            },
            {
                "type": "user",
                "uuid": "child-prompt",
                "parent_tool_use_id": "call-agent",
                "message": {"role": "user", "content": [{"type": "text", "text": prompt}]},
            },
            {
                "type": "assistant",
                "uuid": "child-tool",
                "parent_tool_use_id": "call-agent",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "id": "read-1",
                            "input": {"file_path": "config.ts"},
                        }
                    ],
                },
            },
        ],
    )
    _, path = ccui.convert_run(run, tmp_path / "home", "demo")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert not any(row.get("uuid") == "child-prompt" for row in rows)
    assert any(row.get("uuid") == "launch-1" for row in rows)
    children = path.parent / "sess-demo/subagents/agent-agent-config.jsonl"
    child_rows = [json.loads(line) for line in children.read_text().splitlines()]
    assert [row["uuid"] for row in child_rows] == ["child-prompt", "child-tool"]
    assert all(row["isSidechain"] and row["agentId"] == "agent-config" for row in child_rows)
    assert child_rows[1]["parentUuid"] == "child-prompt"
    assert json.loads(children.with_suffix(".meta.json").read_text())["toolUseId"] == "call-agent"
    sidecar = json.loads((run.with_name(run.name + ".meta") / "ccui-session.json").read_text())
    assert sidecar["subagents"] == 1 and sidecar["subagentMessages"] == 2
    assert "child-prompt" in (run / "raw.jsonl").read_text()


def test_identical_stream_event_is_imported_once_but_distinct_turns_are_preserved(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    event = {
        "type": "user",
        "uuid": "repeat-1",
        "message": {"role": "user", "content": "same text"},
    }
    _append_events(run, [event, event, {**event, "uuid": "repeat-2"}])
    _, path = ccui.convert_run(run, tmp_path / "home", "demo")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    repeated = [row for row in rows if row.get("message", {}).get("content") == "same text"]
    assert [row["uuid"] for row in repeated] == ["repeat-1", "repeat-2"]


def test_live_import_without_final_metadata_keeps_timestamps_stable(tmp_path: Path) -> None:
    run = _run(tmp_path)
    (run / "run-meta.json").unlink()
    _, path = ccui.convert_run(run, tmp_path / "home", "demo")
    before = path.read_text()
    ccui.convert_run(run, tmp_path / "home", "demo")
    assert path.read_text() == before
    assert "2026-01-01T00:00:00+00:00" in before


def test_subagent_path_cannot_escape_session_directory(tmp_path: Path) -> None:
    run = _run(tmp_path)
    _append_events(
        run,
        [
            {
                "type": "system",
                "subtype": "task_started",
                "tool_use_id": "call-agent",
                "task_id": "../../escape",
            },
            {
                "type": "user",
                "uuid": "child",
                "parent_tool_use_id": "call-agent",
                "message": {"role": "user", "content": "child prompt"},
            },
        ],
    )
    _, path = ccui.convert_run(run, tmp_path / "home", "demo")
    children = list((path.parent / "sess-demo/subagents").glob("agent-*.jsonl"))
    assert len(children) == 1
    assert not (path.parent / "escape.jsonl").exists()


def test_convert_run_accepts_node_trace_and_sidecar(tmp_path: Path) -> None:
    run = _run(tmp_path)
    raw = run / "environment-builder.log"
    raw.write_text((run / "raw.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    sidecar = run.with_name(run.name + ".meta") / "ccui-sessions/environment.json"
    result = ccui.convert_run(
        run,
        tmp_path / "home",
        "demo",
        raw_path=raw,
        sidecar_path=sidecar,
        title_suffix=" · 环境构建第 1 轮",
        agent_name="environment-builder",
    )
    assert result is not None
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["title"].endswith(" · 环境构建第 1 轮")
    assert payload["sessionId"] == "sess-demo"
    assert Path(payload["sessionFile"]).is_file()


def test_environment_trace_import_does_not_create_audit_output_directory(tmp_path: Path) -> None:
    source = _run(tmp_path)
    raw = source / "raw.jsonl"
    run = tmp_path / "runs/demo/not-started"
    sidecar = run.with_name(run.name + ".meta") / "ccui-sessions/environment.json"
    result = ccui.convert_run(run, tmp_path / "home", "demo", raw_path=raw, sidecar_path=sidecar, agent_name="environment-builder")
    assert result is not None
    assert sidecar.is_file()
    assert not run.exists()


def test_import_records_source_version_for_clock_independent_cache(tmp_path: Path) -> None:
    run = _run(tmp_path)
    raw = run / "raw.jsonl"
    before = raw.stat()
    ccui.convert_run(run, tmp_path / "home", "demo")
    sidecar = json.loads(run.with_name(run.name + ".meta").joinpath("ccui-session.json").read_text())
    assert sidecar["sourceFile"] == str(raw.resolve())
    assert sidecar["sourceSize"] == before.st_size
    assert sidecar["sourceMtimeNs"] == str(before.st_mtime_ns)
