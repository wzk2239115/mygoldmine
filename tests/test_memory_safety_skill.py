from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".claude" / "skills" / "memory-safety-analyzer"
QUICK_SCAN = SKILL_DIR / "quick-scan.py"
PROFILER = ROOT / ".claude" / "skills" / "project-profiler" / "quick-scan.py"
CHECKER = ROOT / "scripts" / "audit" / "check_orchestration.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_has_frontmatter_and_required_sections():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "name: memory-safety-analyzer" in text
    assert "description:" in text
    for heading in ("空指针解引用", "内存泄漏", "释放后使用", "误报排除", "输出格式"):
        assert heading in text
    assert (SKILL_DIR / "patterns" / "memory.json").is_file()


def test_quick_scan_self_test_passes():
    module = _load("memory_safety_quick_scan", QUICK_SCAN)
    assert module.self_test() == 0


def test_quick_scan_detects_npd_mlk_and_uaf(tmp_path: Path):
    (tmp_path / "sample.c").write_text(
        "#include <stdlib.h>\n"
        "void handle(int fail) {\n"
        "    char *buffer = malloc(16);\n"
        "    if (!buffer) { return; }\n"
        "    if (fail) { return; }\n"
        "    free(buffer);\n"
        "    buffer[0] = 0;\n"
        "}\n",
        encoding="utf-8",
    )
    module = _load("memory_safety_quick_scan_2", QUICK_SCAN)
    result = module.scan_root(tmp_path)
    kinds = result["summary"]["by_kind"]
    assert kinds.get("uaf", 0) >= 1
    assert kinds.get("mlk", 0) >= 1
    assert result["summary"]["candidates"] >= 2


def test_profiler_recommends_memory_skill_for_native_project(tmp_path: Path):
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.10)\n", encoding="utf-8"
    )
    (tmp_path / "main.c").write_text(
        "#include <stdlib.h>\n"
        "int main(void) {\n"
        "    char *buffer = malloc(4);\n"
        "    free(buffer);\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(PROFILER), str(tmp_path), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    profile = json.loads(completed.stdout)
    assert profile["native_memory"]["detected"] is True
    assert "memory-safety-analyzer" in profile["recommended_skills"]


def test_orchestration_checker_requires_memory_skill_for_native_entry():
    checker = _load("check_orchestration_memory", CHECKER)
    missing = checker.check_profile(
        {
            "entrypoints": {"infra": [{"kind": "native", "file": "main.c", "line": 1}]},
            "recommended_skills": [],
        }
    )
    assert any(item["code"] == "profile.missing_skill" for item in missing)
    present = checker.check_profile(
        {
            "entrypoints": {"infra": [{"kind": "native", "file": "main.c", "line": 1}]},
            "recommended_skills": ["memory-safety-analyzer"],
        }
    )
    assert present == []


def test_orchestrator_and_profiler_import_memory_skill_conditions():
    orchestrator = (ROOT / ".claude/agents/security-orchestrator.md").read_text(encoding="utf-8")
    profiler = (ROOT / ".claude/skills/project-profiler/SKILL.md").read_text(encoding="utf-8")
    assert "memory-safety-analyzer" in orchestrator
    assert "空指针解引用" in orchestrator
    assert "memory-safety-analyzer" in profiler
    assert "native_memory" in profiler
