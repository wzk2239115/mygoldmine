import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _frontmatter(text):
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    assert match, "缺少 frontmatter"
    return match.group(1)


def _tools(text):
    frontmatter = _frontmatter(text)
    match = re.search(r"^tools:\s*(.*)$", frontmatter, re.M)
    assert match, "frontmatter 缺少 tools 字段"
    inline = match.group(1).strip()
    if inline:
        return {
            item.strip().strip("'\"")
            for item in inline.strip("[]").split(",")
            if item.strip()
        }

    tools = set()
    for line in frontmatter[match.end() :].splitlines():
        item = re.match(r"^\s+-\s+(.+)$", line)
        if item:
            tools.add(item.group(1).strip().strip("'\""))
        elif line.strip():
            break
    return tools


def _section(text, heading_pattern):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(heading_pattern, line):
            level = len(re.match(r"^(#+)", line).group(1))
            end = len(lines)
            for offset in range(index + 1, len(lines)):
                next_heading = re.match(r"^(#+)\s+", lines[offset])
                if next_heading and len(next_heading.group(1)) <= level:
                    end = offset
                    break
            return "\n".join(lines[index:end])
    raise AssertionError(f"未找到标题匹配 {heading_pattern!r}")


def test_infra_analyst_uses_native_audit_tools_without_edit():
    tools = _tools(_read(".claude/agents/infra-analyst.md"))
    for name in ("Read", "Grep", "Glob", "Bash", "Write", "Skill"):
        assert name in tools, f"infra-analyst 缺少工具 {name}"
    assert "Edit" not in tools, "infra-analyst 不应包含 Edit"


def test_audit_skill_worker_exists_and_exposes_skill_tool():
    path = ROOT / ".claude/agents/audit-skill-worker.md"
    assert path.is_file(), "缺少 audit-skill-worker 智能体定义"
    text = path.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)
    assert re.search(r"^name:\s*audit-skill-worker\s*$", frontmatter, re.M)
    tools = _tools(text)
    for name in ("Skill", "Grep", "Glob"):
        assert name in tools, f"audit-skill-worker 缺少工具 {name}"


def test_security_orchestrator_uses_audit_skill_worker_and_bounded_waves():
    text = _read(".claude/agents/security-orchestrator.md")
    assert "audit-skill-worker" in text
    assert "recommended_skills" in text
    assert re.search(r"(?:最多|至多)\s*3\s*[波批轮]", text), "缺少每轮最多 3 波的表述"
    assert re.search(r"18|3\s*[×xX*]\s*6", text), "缺少 18 个任务或 3 × 6 的等价表述"


def test_infra_flow_does_not_depend_on_skill_runner():
    text = _read(".claude/agents/security-orchestrator.md")
    infra = _section(text, r"^#+\s*.*(?:基础设施.*流程|流程.*基础设施)")
    assert infra.strip(), "基础设施流程段落为空"
    assert "skill-runner" not in infra, "基础设施流程段落仍依赖 skill-runner"


@pytest.mark.parametrize("agent", ["hypothesis-critic", "report-generator"])
def test_critic_and_report_use_grep_glob_without_edit(agent):
    tools = _tools(_read(f".claude/agents/{agent}.md"))
    assert {"Grep", "Glob"} <= tools, f"{agent} 缺少 Grep/Glob"
    assert "Edit" not in tools, f"{agent} 不应包含 Edit"


@pytest.mark.parametrize(
    "skill", ["audit-coverage-planner", "audit-review-planner"]
)
def test_audit_planners_bound_tasks_per_wave_and_emit_dedup_fields(skill):
    text = _read(f".claude/skills/{skill}/SKILL.md")
    assert re.search(
        r"(?:每\s*[波批轮][^。\n]{0,30}最多\s*6\s*(?:个|条|项)"
        r"|最多\s*6\s*(?:个|条|项)[^。\n]{0,30}[波批轮])",
        text,
    ), f"{skill} 缺少每波最多 6 个任务的约束"
    for field in ("skill", "coverage_id", "dedup_key"):
        assert field in text, f"{skill} 缺少字段 {field}"
