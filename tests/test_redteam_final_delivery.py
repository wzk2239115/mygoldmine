import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/redteam"))
from agent import submit_final_delivery


@pytest.mark.parametrize("rejected_count", [0, 4, 8])
def test_agent_retries_until_accepted_without_fixed_attempt_limit(tmp_path, rejected_count):
    result = {"status": "not_captured", "captured": False}
    (tmp_path / "result.json").write_text(json.dumps(result))
    requests, usage = [], []

    def create(**kwargs):
        attempt = len(requests)
        requests.append(attempt)
        assert attempt <= rejected_count, "accepted 后不得继续提交"
        action = {"action": "submit_stage_result", "summary": "" if attempt < rejected_count
                  else "本次未复现，提交真实结论", "limitations": ["未捕获"]}
        return SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content=json.dumps(action)))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    options = SimpleNamespace(model="test", max_tokens=800, model_timeout=60)
    messages = []
    receipt = submit_final_delivery(
        client, options, SimpleNamespace(run_dir=tmp_path), {"id": "F-1"},
        result, messages, tmp_path / "agent.jsonl", lambda *args: usage.append(args), 10,
    )
    assert receipt["decision"] == "accepted"
    assert len(requests) == rejected_count + 1
    assert len(usage) == rejected_count + 1
    replies = [json.loads(row["content"]) for row in messages
               if row["role"] == "user" and row["content"].startswith("{")]
    assert all(row["success"] is False and "repair" in row for row in replies[:-1])
    assert replies[-1]["success"] is True
