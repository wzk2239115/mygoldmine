#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "catalog" / "manifest.json"
OUT = ROOT / "ui" / "data" / "projects.json"
LEGACY = {
    "vllm": {"name": "vLLM", "direction": "Inference Engine", "url": "https://github.com/vllm-project/vllm", "icon": "server", "tone": "blue"},
    "sglang": {"name": "SGLang", "direction": "Inference Engine", "url": "https://github.com/sgl-project/sglang", "icon": "server", "tone": "amber"},
    "deepseek-harness": {"name": "DeepSeek Harness", "direction": "Agent Harness", "url": "", "icon": "brain", "tone": "violet"},
    "codex": {"name": "Codex", "direction": "Agent Harness", "url": "https://github.com/openai/codex", "icon": "terminal", "tone": "ink"},
    "verl": {"name": "verl", "direction": "Training Framework", "url": "https://github.com/volcengine/verl", "icon": "cpu", "tone": "green"},
}


def icon_for(name, direction):
    text = f"{name} {direction}".lower()
    if "sandbox" in text or "沙箱" in text or "security" in text:
        return "shield"
    if "training" in text or "训练" in text or "rl" in text:
        return "cpu"
    if "inference" in text or "推理" in text or "serving" in text or "served" in text:
        return "server"
    if "vector" in text or "database" in text or "数据库" in text:
        return "database"
    if "agent sdk" in text or "编排" in text or "framework" in text:
        return "boxes"
    if "agent harness" in text or "agent" in text:
        return "bot"
    if "model" in text or "模型" in text or "multimodal" in text or "多模态" in text:
        return "brain"
    if "cli" in text or "code" in text:
        return "terminal"
    return "layers"


def tone_for(key):
    tones = ["ink", "blue", "amber", "green", "violet", "red"]
    return tones[sum(ord(c) for c in key) % len(tones)]


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    projects = dict(LEGACY)
    for key, item in (manifest.get("projects") or {}).items():
        direction = item.get("direction") or ""
        name = item.get("name") or key
        projects[key] = {
            "name": name,
            "direction": direction,
            "url": item.get("url") or "",
            "icon": icon_for(name, direction),
            "tone": tone_for(key),
            "audit_id": item.get("audit_id") or "",
        }
    OVERRIDES = {
        "aud-001-cline": ("bot", "blue"),
        "aud-003-gemini-cli": ("terminal", "violet"),
        "aud-005-opencode": ("terminal", "ink"),
        "aud-006-openhands-software-agent-sdk-a-gent-server": ("boxes", "amber"),
        "aud-024-deep-agents": ("brain", "green"),
        "aud-046-agentscope-runtime": ("boxes", "red"),
        "aud-047-anthropic-sandbox-runtime": ("shield", "amber"),
        "aud-048-opensandbox": ("shield", "red"),
        "aud-060-llama-cpp": ("server", "green"),
        "aud-080-xinference": ("server", "blue"),
        "aud-097-vllm-ascend": ("server", "amber"),
        "aud-099-litellm": ("server", "violet"),
    }
    for key, (icon, tone) in OVERRIDES.items():
        if key in projects:
            projects[key]["icon"] = icon
            projects[key]["tone"] = tone
    OUT.write_text(json.dumps({"schema_version": 1, "projects": projects}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[projects] {len(projects)} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
