import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "redteam"))
import agent  # noqa: E402


def test_parse_action_takes_first_valid_object_from_multiple():
    content = (
        '{"thought":"first","action":"shell","command":"ls"}\n'
        '{"thought":"second","action":"trigger"}'
    )
    assert agent.parse_action(content) == {"thought": "first", "action": "shell", "command": "ls"}


def test_parse_action_skips_invalid_braces_before_action():
    content = 'not json {broken} then {"thought":"ok","action":"trigger"}'
    assert agent.parse_action(content) == {"thought": "ok", "action": "trigger"}


def test_parse_action_rejects_unknown_action():
    assert agent.parse_action('{"thought":"x","action":"unknown"}') is None


def test_terminal_done_only_for_empty_answer():
    assert agent.terminal_done({"action": "done"})
    assert agent.terminal_done({"action": "done", "answer": ""})
    assert agent.terminal_done({"action": "done", "answer": "   "})
    assert agent.terminal_done({"action": "done", "answer": None})
    assert not agent.terminal_done({"action": "done", "answer": "FLAG{real}"})
    assert not agent.terminal_done({"action": "shell", "command": "true"})
