import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mcp_rejection_contains_example_and_allows_repair_in_same_session(tmp_path):
    file = tmp_path / "report.json"
    file.write_text("{}")
    args = {"artifact": str(file), "summary": "提交", "limitations": []}
    child = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts/stages/submission.py"),
         "serve", "--stage", "verify", "--root", str(tmp_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    def call(identifier):
        request = {"jsonrpc": "2.0", "id": identifier, "method": "tools/call",
                   "params": {"name": "submit_stage_result", "arguments": args}}
        child.stdin.write(json.dumps(request) + "\n")
        child.stdin.flush()
        return json.loads(child.stdout.readline())["result"]
    try:
        rejected = call(1)
        payload = rejected["structuredContent"]
        assert payload["success"] is False
        assert payload["decision"] == "needs_revision"
        assert rejected["isError"] is True
        assert payload["repair"]["artifact_example"]["verdict"] == "blocked"
        assert payload["repair"]["resubmit_example"]["artifact"] == str(file)
        assert payload["errors"]
        file.write_text(json.dumps({"finding_id": "F-1", "verdict": "rejected",
                                    "reason": "实际检查排除", "evidence": []}))
        accepted = call(2)
        assert accepted["structuredContent"]["success"] is True
        assert accepted["structuredContent"]["decision"] == "accepted"
        assert accepted["isError"] is False
        assert "repair" not in accepted["structuredContent"]
        assert len(list((tmp_path / ".stage-submissions/verify").glob("*.json"))) == 2
    finally:
        child.stdin.close()
        child.wait(timeout=5)
