from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load(
    "check_orchestration",
    ROOT / "scripts" / "audit" / "check_orchestration.py",
)
profiler = _load(
    "project_profiler_quick_scan",
    ROOT / ".claude" / "skills" / "project-profiler" / "quick-scan.py",
)


def _task(skill: str, coverage_id: str, wave: int = 2, dedup: str | None = None):
    return {
        "wave": wave,
        "coverage_id": coverage_id,
        "skill": skill,
        "dedup_key": dedup or f"{coverage_id}:{skill}:{wave}",
    }


def test_current_orchestrator_contract_has_cross_domain_wave_rules():
    text = (ROOT / ".claude/agents/security-orchestrator.md").read_text(encoding="utf-8")
    assert checker.check_orchestrator(text) == []


def test_orchestrator_rules_cover_all_required_contracts():
    codes = {item["code"] for item in checker.check_orchestrator("")}
    expected = {code for code, _, _ in checker.ORCHESTRATOR_RULES}
    assert expected == codes


@pytest.mark.parametrize("kind", sorted(checker.ENTRY_SKILL_RULES))
def test_profile_check_flags_each_supported_entry_without_skill(kind: str):
    profile = {
        "entrypoints": {"infra": [{"kind": kind, "file": "entry.py", "line": 1}]},
        "recommended_skills": [],
    }
    codes = {item["code"] for item in checker.check_profile(profile)}
    assert "profile.missing_skill" in codes


def test_profile_check_flags_http_entry_without_auth_skill():
    profile = {
        "entrypoints": {"infra": [{"kind": "http", "file": "router.py", "line": 1}]},
        "recommended_skills": ["code-injection-analyzer"],
    }
    codes = {item["code"] for item in checker.check_profile(profile)}
    assert "profile.missing_skill" in codes


def test_profile_check_accepts_http_entry_with_auth_skill():
    profile = {
        "entrypoints": {"infra": [{"kind": "http", "file": "router.py", "line": 1}]},
        "recommended_skills": ["web-auth-analyzer"],
    }
    assert checker.check_profile(profile) == []


def test_profiler_keeps_entrypoint_skills_in_recommended_pool(tmp_path: Path):
    root = tmp_path / "verl"
    package = root / "verl"
    package.mkdir(parents=True)
    (root / "pyproject.toml").write_text('name = "verl"\n', encoding="utf-8")
    (package / "router.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {}\n",
        encoding="utf-8",
    )
    (package / "train.py").write_text(
        "import subprocess\n"
        "subprocess.run(['sh', '-c', 'echo train'])\n",
        encoding="utf-8",
    )
    (package / "checkpoint.py").write_text(
        "import torch\n"
        "torch.load('checkpoint.pt')\n",
        encoding="utf-8",
    )

    infra = profiler.detect_infra(root)
    skills = set(infra["recommended_skills"])
    assert "training-framework" in infra["project_types"]
    assert {"web-auth-analyzer", "unauth-route-scanner"} <= skills
    assert {"command-injection-analyzer", "code-injection-analyzer"} <= skills
    assert {"model-loading-analyzer", "insecure-deserialization-analyzer"} <= skills

    profile = {
        "entrypoints": {"infra": infra["entrypoints"]},
        "recommended_skills": infra["recommended_skills"],
    }
    assert checker.check_profile(profile) == []


def test_plan_check_flags_single_skill_wave():
    plan = {
        "tasks": [
            _task("code-injection-analyzer", f"COV-{index}")
            for index in range(6)
        ]
    }
    codes = {item["code"] for item in checker.check_plan(plan)}
    assert "plan.single_skill_wave" in codes
    assert "plan.skill_overused" in codes


def test_plan_check_flags_skill_overused_without_single_skill_wave():
    plan = {
        "tasks": [
            _task("code-injection-analyzer", "COV-001"),
            _task("code-injection-analyzer", "COV-002"),
            _task("code-injection-analyzer", "COV-003"),
            _task("web-auth-analyzer", "COV-004"),
            _task("web-auth-analyzer", "COV-005"),
            _task("path-traversal-analyzer", "COV-006"),
        ]
    }
    codes = {item["code"] for item in checker.check_plan(plan)}
    assert "plan.skill_overused" in codes
    assert "plan.single_skill_wave" not in codes


def test_plan_check_flags_wave_over_limit():
    plan = {
        "tasks": [
            _task(f"analyzer-{index}", f"COV-{index}")
            for index in range(7)
        ]
    }
    codes = {item["code"] for item in checker.check_plan(plan)}
    assert "plan.wave_too_large" in codes


def test_plan_check_flags_missing_coverage_and_skill():
    plan = {"tasks": [{"wave": 2, "dedup_key": "one"}]}
    codes = {item["code"] for item in checker.check_plan(plan)}
    assert "plan.missing_coverage" in codes
    assert "plan.missing_skill" in codes


def test_plan_check_accepts_diverse_wave():
    plan = {
        "tasks": [
            _task("web-auth-analyzer", "COV-001"),
            _task("web-auth-analyzer", "COV-002"),
            _task("command-injection-analyzer", "COV-003"),
            _task("command-injection-analyzer", "COV-004"),
            _task("path-traversal-analyzer", "COV-005"),
            _task("path-traversal-analyzer", "COV-006"),
        ]
    }
    assert checker.check_plan(plan) == []


def test_plan_check_flags_duplicate_dedup_key():
    plan = {
        "tasks": [
            _task("web-auth-analyzer", "COV-001", dedup="same-key"),
            _task("command-injection-analyzer", "COV-002", dedup="same-key"),
        ]
    }
    codes = {item["code"] for item in checker.check_plan(plan)}
    assert "plan.duplicate_dedup" in codes


def test_plan_check_flags_too_many_waves_and_consecutive_dominance():
    plan = {
        "tasks": [
            _task("code-injection-analyzer", "COV-001", wave=1),
            _task("code-injection-analyzer", "COV-002", wave=2),
            _task("path-traversal-analyzer", "COV-003", wave=3),
            _task("path-traversal-analyzer", "COV-004", wave=4),
        ]
    }
    codes = {item["code"] for item in checker.check_plan(plan)}
    assert "plan.too_many_waves" in codes
    assert "plan.consecutive_skill" in codes


def test_audit_is_advisory_and_does_not_fail_on_soft_diversity_findings():
    report = checker.audit(
        orchestrator_text=(ROOT / ".claude/agents/security-orchestrator.md").read_text(
            encoding="utf-8"
        ),
        profile={
            "entrypoints": {"infra": [{"kind": "http", "file": "router.py", "line": 1}]},
            "recommended_skills": ["code-injection-analyzer"],
        },
    )
    assert report["ok"] is True
    assert report["summary"]["warnings"] == 1
