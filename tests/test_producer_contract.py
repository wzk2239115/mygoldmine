import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))
from submission import accepted_submissions, config, submit


def arguments(file):
    return {"artifact": str(file), "summary": "交付", "limitations": ["实际能力限制"]}


def test_environment_blocked_is_a_valid_outcome_without_docker(tmp_path, monkeypatch):
    import submission
    monkeypatch.setattr(submission.subprocess, "run",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("不应查询镜像")))
    file = tmp_path / "env-manifest.json"
    file.write_text(json.dumps({"env_status": "blocked", "reason": "依赖下载不可用"}))
    assert submit("environment", tmp_path, arguments(file))["decision"] == "accepted"


def test_verify_task_identity_and_enum_are_checked_at_submission(tmp_path):
    root = tmp_path / "verify/agent/F-1"
    root.mkdir(parents=True)
    finding = root.parent / "inputs/F-1/finding.json"
    finding.parent.mkdir(parents=True)
    finding.write_text('{"id":"F-1"}')
    task = json.loads(config("verify", root)["mcpServers"]["stage_delivery"]["args"][-1])
    file = root / "verify-report.json"
    for identifier, verdict in [("F-2", "rejected"), ("F-1", "anything")]:
        file.write_text(json.dumps({"finding_id": identifier, "verdict": verdict, "evidence": []}))
        assert submit("verify", root, arguments(file), task=task)["decision"] == "needs_revision"
    finding.write_text('{"id":"F-2"}')
    file.write_text('{"finding_id":"F-1","verdict":"rejected","evidence":[]}')
    assert submit("verify", root, arguments(file), task=task)["decision"] == "accepted"


def test_orchestrator_collects_formal_artifacts_and_detects_mutation(tmp_path):
    report = tmp_path / "audit-report.json"
    report.write_text('{"findings":[]}')
    attachment = tmp_path / "task-artifacts/notes.md"
    attachment.parent.mkdir()
    attachment.write_text("真实分析")
    receipt = submit("orchestrator", tmp_path, arguments(report))
    assert receipt["decision"] == "accepted"
    assert str(attachment) in {item["path"] for item in receipt["files"]}
    attachment.write_text("changed")
    import pytest
    with pytest.raises(ValueError):
        accepted_submissions("orchestrator", tmp_path)


def test_visual_provenance_is_frozen_with_bitmap(tmp_path):
    from PIL import Image
    scripts = Path(__file__).resolve().parents[1] / ".claude/skills/project-cartographer/scripts"
    sys.path.insert(0, str(scripts))
    from image_provenance import record_generation
    file = tmp_path / "scene-F-1.director.json"
    file.write_text('{"finding_id":"F-1"}')
    image = tmp_path / "scene-F-1.png"
    Image.new("RGB", (16, 16)).save(image)
    record_generation(image, "test-model", "prompt-hash")
    receipt = submit("visual", tmp_path, arguments(file))
    assert receipt["decision"] == "accepted"
    provenance = Path(str(image) + ".generation.json")
    assert str(provenance) in {item["path"] for item in receipt["files"]}
