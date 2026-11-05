from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    script_dir = root / "scripts"
    script_dir.mkdir(parents=True)
    script = script_dir / "clean.sh"
    shutil.copy2(ROOT / "scripts/clean.sh", script)
    generated = [
        "runs/demo/run/audit-report.json",
        "logs/audit.log",
        "rsi/mining-repairs/agentic/mrc_demo.md",
        "rsi/verification-experience.jsonl",
        ".claude/skills/rsi-shared-experience/rules/mr_demo.md",
        "knowledge/project-rules/demo/mr_demo.md",
        "ui/data/finding-ledger.json",
    ]
    for name in generated:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated", encoding="utf-8")
    preserved = [
        "targets/demo/source.py",
        "env/demo/env-manifest.json",
        "knowledge/projects/demo.md",
        ".claude/agents/security-orchestrator.md",
        ".claude/skills/rsi-shared-experience/SKILL.md",
        "ui/data/projects.json",
    ]
    for name in preserved:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserve", encoding="utf-8")
    return root


def test_clean_dry_run_preserves_everything(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    completed = subprocess.run(
        ["bash", str(root / "scripts/clean.sh"), "--dry-run"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "未删除任何文件" in completed.stdout
    assert (root / "runs/demo/run/audit-report.json").exists()
    assert (root / "rsi/verification-experience.jsonl").exists()


def test_clean_removes_only_generated_state(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    subprocess.run(
        ["bash", str(root / "scripts/clean.sh"), "--yes"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert not (root / "runs/demo").exists()
    assert not (root / "rsi/verification-experience.jsonl").exists()
    assert not (root / "rsi/mining-repairs").exists()
    assert not (root / ".claude/skills/rsi-shared-experience/rules").exists()
    assert not (root / "knowledge/project-rules").exists()
    assert not (root / "ui/data/finding-ledger.json").exists()
    assert (root / "runs").is_dir()
    assert (root / "targets/demo/source.py").is_file()
    assert (root / "env/demo/env-manifest.json").is_file()
    assert (root / "knowledge/projects/demo.md").is_file()
    assert (root / ".claude/agents/security-orchestrator.md").is_file()
    assert (root / ".claude/skills/rsi-shared-experience/SKILL.md").is_file()
    assert (root / "ui/data/projects.json").is_file()
