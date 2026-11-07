import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "token_usage", ROOT / "scripts/workflow/token_usage.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_summary_replaces_message_usage_and_keeps_unknown(tmp_path):
    repo = tmp_path
    file = repo / "runs/demo/run/raw.jsonl"
    file.parent.mkdir(parents=True)
    rows = [
        {
            "type": "assistant",
            "session_id": "s",
            "message": {"id": "m", "usage": {"input_tokens": 10, "output_tokens": 5}},
        },
        {"type": "result", "session_id": "s", "usage": {"input_tokens": 20, "output_tokens": 8}},
        {"type": "model_usage", "request_key": "retry-2", "usage": None},
    ]
    file.write_text("".join(json.dumps(x) + "\n" for x in rows))
    result = module.refresh(repo)
    assert result["records"] == 2
    assert result["groups"][0]["totals"]["input_tokens"] == 20
    assert result["groups"][0]["unknown_usage"] == 1
    assert module.refresh(repo)["records"] == 2
    mirror = file.with_name("mirror.agent.log")
    mirror.write_bytes(file.read_bytes())
    assert module.refresh(repo)["records"] == 2


def test_partial_line_and_cache_conventions(tmp_path):
    path = tmp_path / "runs/p/r/model-usage.jsonl"
    path.parent.mkdir(parents=True)
    event = {
        "type": "model_usage",
        "request_key": "1",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 4,
            "prompt_tokens_details": {"cached_tokens": 80},
        },
    }
    path.write_text(json.dumps(event))
    assert module.refresh(tmp_path)["records"] == 0
    path.write_text(json.dumps(event) + "\n")
    result = module.refresh(tmp_path)
    assert result["groups"][0]["totals"]["input_tokens"] == 100
    assert result["groups"][0]["totals"]["cache_read_input_tokens"] == 80
    assert result["groups"][0]["missing_fields"]["cache_creation_input_tokens"] == 1


def test_jev_batch_import_is_idempotent(tmp_path):
    path = tmp_path / "runs/p/r/triage/jev-infra.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"stats": {"input_tokens": 15, "output_tokens": 2}}))
    assert module.refresh(tmp_path)["groups"][0]["stage"] == "triage"
    assert module.refresh(tmp_path)["records"] == 1
