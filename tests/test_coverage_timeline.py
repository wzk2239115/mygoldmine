import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "coverage_timeline",
    Path(__file__).resolve().parents[1] / "scripts/workflow/coverage_timeline.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_request_link_and_duplicate_read(tmp_path):
    run = tmp_path / "runs/demo/one"
    root = run / "task-artifacts/read-coverage"
    root.mkdir(parents=True)
    (root / "summary.json").write_text(json.dumps({"source_version": "v1"}))
    events = []
    for tool, start, end, second in [("a", 1, 10, 1), ("b", 6, 20, 2)]:
        events.append(
            {
                "kind": "read",
                "file": "app.py",
                "file_sha256": "hash",
                "ranges": [{"start": start, "end": end}],
                "timestamp": f"2026-11-09T00:00:0{second}Z",
                "tool_use_id": tool,
            }
        )
    (root / "events.jsonl").write_text("\n".join(json.dumps(r) for r in events))
    messages = []
    for identifier, tool in [("m1", "a"), ("m2", "b")]:
        messages.append(
            {
                "type": "assistant",
                "session_id": "session",
                "message": {
                    "id": identifier,
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                    "content": [{"type": "tool_use", "id": tool}],
                },
            }
        )
    (run / "raw.jsonl").write_text("\n".join(json.dumps(r) for r in messages + messages))
    series = module.timeline(tmp_path, "demo")["series"][0]
    assert series["tokens"] == 240
    assert series["lines"] == 20
    assert len(series["time_points"]) > 2
    assert series["missing_requests"] == 0
    assert series["time_points"][-1]["seconds"] == 1
