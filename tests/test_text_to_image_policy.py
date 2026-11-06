import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".claude/skills/project-cartographer/scripts"
sys.path.insert(0, str(SCRIPTS))
from image_provenance import generated_image, record_generation

spec = importlib.util.spec_from_file_location("image_delivery", ROOT / "scripts/stages/submission.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


def test_report_assembly_never_draws_svg_or_uses_svg_fallback(tmp_path):
    model = tmp_path / "model.json"
    model.write_text(json.dumps({"project": "demo", "trees": {"attacks": [
        {"finding_id": "F-1", "label": "测试", "scene": {"attacker": ["输入"], "victim": ["处理"]}}
    ]}}))
    output = tmp_path / "output"
    subprocess.run([sys.executable, str(SCRIPTS / "render_diagrams.py"), "--model", str(model),
                    "--out-dir", str(output)], check=True, capture_output=True)
    assert not list(output.glob("*.svg"))
    text = (output / "report-illustrated.md").read_text()
    assert ".svg)" not in text
    assert "尚无可用的文生图模型插图" in text


def test_delivery_rejects_svg_and_renamed_svg_accepts_model_receipt(tmp_path):
    director = tmp_path / "scene-F-1.director.json"
    director.write_text(json.dumps({"finding_id": "F-1"}))
    args = {"artifact": str(director), "summary": "场景交付", "limitations": []}
    (tmp_path / "scene-F-1.svg").write_text("<svg/>")
    assert delivery.submit("visual", tmp_path, args)["decision"] == "needs_revision"
    image = tmp_path / "scene-F-1.webp"
    image.write_text("<svg/>")
    assert not generated_image(image)
    assert delivery.submit("visual", tmp_path, args)["decision"] == "needs_revision"
    Image.new("RGB", (2, 2), "white").save(image, format="WEBP")
    assert delivery.submit("visual", tmp_path, args)["decision"] == "needs_revision"
    record_generation(image, "fixture/image-model", "prompt-hash")
    assert delivery.submit("visual", tmp_path, args)["decision"] == "accepted"
    image.write_bytes(image.read_bytes() + b"changed")
    assert not generated_image(image)


def test_image_api_cache_hit_writes_matching_generation_receipt(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    original = tmp_path / "cached.webp"
    Image.new("RGB", (2, 2), "white").save(original, format="WEBP")
    digest = hashlib.sha256(b"fixture/model\n1024x1024\nfixture prompt").hexdigest()
    (cache / (digest + ".json")).write_text(json.dumps({"file": str(original), "model": "fixture/model"}))
    output = tmp_path / "new.webp"
    result = subprocess.run([sys.executable, str(SCRIPTS / "image2.py"), "--model", "fixture/model",
        "--prompt", "fixture prompt", "--out", str(output), "--cache-dir", str(cache), "--json"],
        env={**os.environ, "IMAGE_API_KEY": "fixture", "IMAGE_API_BASE": "https://invalid.invalid"},
        capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["cached"] is True
    assert generated_image(output)


def test_report_prompt_uses_technical_template_and_ignores_legacy_metaphor(tmp_path):
    model = tmp_path / "visual" / "visual-model.json"
    model.parent.mkdir()
    model.write_text(json.dumps({"project": "demo", "trees": {"attacks": [{
        "finding_id": "F-1", "label": "配置进入执行器",
        "scene": {"kind": "rce", "boundary": "配置与执行边界",
                  "attacker": ["可控配置"], "victim": ["解析配置", "启动进程"],
                  "flow": ["配置", "子进程"], "result": "命令执行",
                  "visual": "LEGACY_STORY_MARKER"}
    }]}}))
    result = subprocess.run([sys.executable, str(SCRIPTS / "render_attack_images.py"),
        "--model", str(model), "--dry-run", "--all"], capture_output=True, text=True, check=True)
    rows = json.loads(result.stdout)["results"]
    assert rows[0]["size"] == "1536x864"
    prompt = Path(rows[0]["prompt"]).read_text()
    assert "technical-explainer-v1" in prompt and "16:9" in prompt
    assert all(color in prompt for color in ("#334155", "#2563EB", "#DC2626"))
    assert "LEGACY_STORY_MARKER" not in prompt
    assert "配置与执行边界" in prompt
    assert not list(tmp_path.rglob("*.svg"))


def test_agentic_prompt_requests_same_technical_style():
    source = (SCRIPTS / "render_attack_scenes_agentic.py").read_text()
    agent = (SCRIPTS.parents[2] / "agents" / "attack-scene-director.md").read_text()
    assert "technical-explainer-prompt.md" in source and "technical-explainer-v1" in source
    assert "--size 1536x864" in agent
    assert "图里不要文字" not in agent
