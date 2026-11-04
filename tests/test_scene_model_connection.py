import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/skills/project-cartographer/scripts/render_attack_scenes_agentic.py"
spec = importlib.util.spec_from_file_location("scene_renderer", SCRIPT)
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)


def test_proxy_model_and_credentials_reach_child_environment(tmp_path):
    config = tmp_path / "opencode.json"
    config.write_text(json.dumps({"provider": {"360-proxy": {"options": {"apiKey": "test-token"}}}}))
    original = {"OPENCODE_CONFIG": str(config)}
    model, env = scene.claude_connection("360-proxy/deepseek/deepseek-v4.1-flash", original)
    assert model == "deepseek/deepseek-v4.1-flash"
    assert env["ANTHROPIC_BASE_URL"] == "https://api.360.cn"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "test-token"
    assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == model
    assert "ANTHROPIC_AUTH_TOKEN" not in original


def test_explicit_connection_is_preserved():
    model, env = scene.claude_connection("opencode/custom", {
        "ANTHROPIC_BASE_URL": "https://configured.example",
        "ANTHROPIC_API_KEY": "existing-key",
        "GLM_API_KEY": "unused-key",
    })
    assert model == "custom"
    assert env["ANTHROPIC_BASE_URL"] == "https://configured.example"
    assert env["ANTHROPIC_API_KEY"] == "existing-key"
    assert "ANTHROPIC_AUTH_TOKEN" not in env
