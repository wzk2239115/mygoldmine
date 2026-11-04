from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "mine" / "visual_report.sh"


def _write_executable(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _write_build_fake(path: Path) -> Path:
    return _write_executable(
        path,
        """#!/usr/bin/env python3
import json, os, pathlib, sys

args = sys.argv[1:]
def opt(name):
    return args[args.index(name) + 1]

with open(os.environ["FAKE_CALL_LOG"], "a", encoding="utf-8") as stream:
    stream.write("build " + " ".join(args) + "\\n")

run_dir = pathlib.Path(opt("--run-dir"))
ids = json.loads(os.environ.get("FAKE_SCENE_IDS", "[]"))
model = {
    "project": opt("--project"),
    "run_dir": str(run_dir),
    "trees": {
        "attacks": [
            {"finding_id": fid, "id": "attack:" + fid, "status": "high", "label": fid, "scene": {}}
            for fid in ids
        ]
    },
}
out = run_dir / "visual" / "visual-model.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(model), encoding="utf-8")
print(json.dumps({"out": str(out)}))
""",
    )


def _write_scene_fake(path: Path, role: str, mode_env: str) -> Path:
    return _write_executable(
        path,
        f"""#!/usr/bin/env python3
import json, os, pathlib, sys

role = {role!r}
args = sys.argv[1:]
def opt(name):
    return args[args.index(name) + 1]

with open(os.environ["FAKE_CALL_LOG"], "a", encoding="utf-8") as stream:
    stream.write(role + " " + " ".join(args) + "\\n")

out_dir = pathlib.Path(opt("--out-dir"))
out_dir.mkdir(parents=True, exist_ok=True)
ids = json.loads(os.environ.get("FAKE_SCENE_IDS", "[]"))
limit = int(opt("--max"))
mode = os.environ.get({mode_env!r}, "ok")
if mode == "fail":
    print("image service unavailable: 401 unauthorized", file=sys.stderr)
    raise SystemExit(1)
if mode == "subset":
    count = min(1, len(ids))
    code = 0
else:
    count = min(limit, len(ids))
    code = 0
for fid in ids[:count]:
    (out_dir / ("scene-" + fid + ".webp")).write_bytes(b"fake-webp")
raise SystemExit(code)
""",
    )


def _write_render_fake(path: Path) -> Path:
    return _write_executable(
        path,
        """#!/usr/bin/env python3
import os, pathlib, sys

args = sys.argv[1:]
def opt(name):
    return args[args.index(name) + 1]

with open(os.environ["FAKE_CALL_LOG"], "a", encoding="utf-8") as stream:
    stream.write("diagrams " + " ".join(args) + "\\n")

out_dir = pathlib.Path(opt("--out-dir"))
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "report-illustrated.md").write_text("# illustrated\\n", encoding="utf-8")
""",
    )


def _run_visual(
    tmp_path: Path,
    *,
    scene_ids: list[str],
    max_scenes: int = 5,
    claude_available: bool = True,
    agentic_mode: str = "ok",
    images_mode: str = "ok",
    audit: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    if audit:
        (run_dir / "audit-report.json").write_text(
            json.dumps({"findings": []}), encoding="utf-8"
        )
    out_dir = tmp_path / "rendered"
    calls = tmp_path / "calls.log"

    binaries = tmp_path / "bin"
    binaries.mkdir()
    build = _write_build_fake(binaries / "build_visual_model.py")
    agentic = _write_scene_fake(
        binaries / "render_attack_scenes_agentic.py", "agentic", "FAKE_AGENTIC_MODE"
    )
    images = _write_scene_fake(
        binaries / "render_attack_images.py", "images", "FAKE_IMAGES_MODE"
    )
    render = _write_render_fake(binaries / "render_diagrams.py")
    claude = _write_executable(binaries / "claude", "#!/usr/bin/env bash\nexit 0\n")

    env = os.environ.copy()
    env.update(
        {
            "VISUAL_BUILD_MODEL_BIN": str(build),
            "VISUAL_AGENTIC_BIN": str(agentic),
            "VISUAL_IMAGES_BIN": str(images),
            "VISUAL_RENDER_BIN": str(render),
            "VISUAL_CLAUDE": str(claude if claude_available else tmp_path / "missing-claude"),
            "FAKE_CALL_LOG": str(calls),
            "FAKE_SCENE_IDS": json.dumps(scene_ids),
            "FAKE_AGENTIC_MODE": agentic_mode,
            "FAKE_IMAGES_MODE": images_mode,
        }
    )
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--project", "demo",
            "--run-dir", str(run_dir),
            "--max", str(max_scenes),
            "--timeout", "10",
            "--agent-timeout", "20",
            "--output", str(out_dir),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result, run_dir, out_dir, calls


def _calls(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.split(" ", 1)[0] for line in path.read_text(encoding="utf-8").splitlines()]


def _summary(out_dir: Path) -> dict:
    return json.loads((out_dir / "visual-summary.json").read_text(encoding="utf-8"))


def test_missing_audit_report_exits_3(tmp_path: Path) -> None:
    result, _, out_dir, calls = _run_visual(tmp_path, scene_ids=[], audit=False)
    assert result.returncode == 3
    assert "audit-report.json" in result.stderr
    assert _calls(calls) == []
    assert not (out_dir / "visual-summary.json").exists()


def test_invalid_audit_report_exits_3(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "audit-report.json").write_text("{not json", encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), "--project", "demo", "--run-dir", str(run_dir)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 3
    assert "合法 JSON" in result.stderr


def test_agentic_scene_path_preferred_when_claude_exists(tmp_path: Path) -> None:
    result, _, out_dir, calls = _run_visual(
        tmp_path, scene_ids=["F-1", "F-2"], agentic_mode="ok"
    )
    assert result.returncode == 0, result.stderr
    assert _calls(calls) == ["build", "agentic", "diagrams"]

    summary = _summary(out_dir)
    assert summary["status"] == "ready"
    assert summary["scene_status"] == "ready"
    assert summary["scene_count"] == 2
    assert summary["critical_high_scene_ids"] == ["F-1", "F-2"]
    assert summary["missing_critical_high_scene_ids"] == []
    assert summary["steps"]["build_visual_model"]["ok"] is True
    assert summary["steps"]["render_attack_scenes_agentic"]["ok"] is True
    assert summary["steps"]["render_attack_images"]["attempted"] is False
    assert summary["steps"]["render_diagrams"]["ok"] is True
    assert Path(summary["illustrated_report_path"]).exists()


def test_agentic_failure_falls_back_to_image_renderer(tmp_path: Path) -> None:
    result, _, out_dir, calls = _run_visual(
        tmp_path,
        scene_ids=["F-1", "F-2"],
        agentic_mode="fail",
        images_mode="ok",
    )
    assert result.returncode == 0, result.stderr
    assert _calls(calls) == ["build", "agentic", "images", "diagrams"]

    summary = _summary(out_dir)
    assert summary["status"] == "ready"
    assert summary["scene_status"] == "ready"
    assert summary["scene_count"] == 2
    assert summary["missing_critical_high_scene_ids"] == []
    assert summary["returncodes"]["render_attack_scenes_agentic"] == 1
    assert summary["returncodes"]["render_attack_images"] == 0
    assert any("fallback" in reason for reason in summary["reasons"])


def test_image_failure_is_blocked_and_honest_without_fake_images(tmp_path: Path) -> None:
    result, _, out_dir, calls = _run_visual(
        tmp_path,
        scene_ids=["F-1", "F-2"],
        claude_available=False,
        images_mode="fail",
    )
    assert result.returncode == 0, result.stderr
    assert _calls(calls) == ["build", "images", "diagrams"]

    summary = _summary(out_dir)
    assert summary["status"] == "partial"
    assert summary["scene_status"] == "blocked"
    assert summary["scene_count"] == 0
    assert summary["missing_critical_high_scene_ids"] == ["F-1", "F-2"]
    assert summary["returncodes"]["render_attack_scenes_agentic"] is None
    assert summary["returncodes"]["render_attack_images"] == 1
    assert any("image generation failed" in reason for reason in summary["reasons"])
    assert not list(out_dir.glob("scene-*.webp"))


def test_partial_scene_generation_reports_missing_ids(tmp_path: Path) -> None:
    result, _, out_dir, _ = _run_visual(
        tmp_path,
        scene_ids=["F-1", "F-2"],
        claude_available=False,
        images_mode="subset",
    )
    assert result.returncode == 0, result.stderr

    summary = _summary(out_dir)
    assert summary["status"] == "partial"
    assert summary["scene_status"] == "partial"
    assert summary["scene_count"] == 1
    assert summary["missing_critical_high_scene_ids"] == ["F-2"]
    assert summary["missing_selected_scene_ids"] == ["F-2"]
    assert any("F-2" in reason for reason in summary["reasons"])


def test_max_limits_attempted_scenes_but_still_reports_all_missing(tmp_path: Path) -> None:
    result, _, out_dir, calls = _run_visual(
        tmp_path,
        scene_ids=["F-1", "F-2", "F-3"],
        max_scenes=1,
        claude_available=False,
        images_mode="ok",
    )
    assert result.returncode == 0, result.stderr
    assert _calls(calls) == ["build", "images", "diagrams"]

    summary = _summary(out_dir)
    assert summary["status"] == "partial"
    assert summary["scene_status"] == "partial"
    assert summary["scene_count"] == 1
    assert summary["selected_scene_ids"] == ["F-1"]
    assert summary["missing_selected_scene_ids"] == []
    assert summary["missing_critical_high_scene_ids"] == ["F-2", "F-3"]
    assert summary["returncodes"]["render_attack_images"] == 0
