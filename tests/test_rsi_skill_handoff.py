import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))

import audit_skill_updates
from audit_skill_updates import (
    apply_updates,
    audit_skill_index,
    read_named_audit_skill,
    request_update,
)
from skill_bank import SkillBank, audit_skill_summary
from stage_tools import submit_structured


def setup_run(tmp_path):
    root = tmp_path / "runs/demo/one"
    root.mkdir(parents=True)
    (root / "trace.txt").write_text("本轮真实审计轨迹")
    return SkillBank(tmp_path), root


def propose(root, scope, name, content):
    return request_update(
        "learner", root,
        {
            "scope": scope,
            "skill_name": name,
            "content": content,
            "evidence": [str(root / "trace.txt")],
        },
    )["id"]


def deliver(root, ids):
    receipt = submit_structured(
        "learner", root,
        {
            "status": "completed",
            "conclusions": [{
                "stage": "orchestrator",
                "category": "method_gap",
                "reason": "存在未探索入口",
                "next_action": "深入调用关系",
                "evidence": ["trace.txt"],
            }],
            "proposal_ids": ids,
            "summary": "本轮方法更新",
            "limitations": [],
        },
        task={"project": "demo"},
    )
    assert receipt["success"], receipt


def test_stage_two_index_points_to_existing_immutable_versions(tmp_path):
    bank, root = setup_run(tmp_path)
    ids = [
        propose(root, "general", "boundary", "追踪信任边界"),
        propose(root, "project", "plugin", "追踪项目插件"),
    ]
    deliver(root, ids)
    apply_updates(bank, root, "demo")
    versions = bank.render("orchestrator", "demo")["versions"]
    index = audit_skill_summary(bank, "demo", versions)
    for item in versions:
        source = bank.root / "versions" / item["id"] / "SKILL.md"
        assert source.is_file()
        assert not (bank.root / "candidates" / f"{item['id']}.md").exists()
        assert str(source) in index
        assert source.read_text().rstrip() == bank.candidate(item["id"])["content"]
    assert "candidates/" not in index


def test_learner_index_is_bounded_and_reads_only_named_section(tmp_path):
    bank, root = setup_run(tmp_path)
    first = "A" * 12000
    ids = [
        propose(root, "general", "boundary", first),
        propose(root, "general", "workflow", "B" * 12000),
        propose(root, "project", "plugin", "C" * 12000),
    ]
    deliver(root, ids)
    apply_updates(bank, root, "demo")
    listing = audit_skill_index(bank, "demo")
    assert len(json.dumps(listing, ensure_ascii=False)) < 2000
    assert all("content" not in row for skill in listing["skills"] for row in skill["skills"])
    first_page = read_named_audit_skill(
        bank, "demo", {"scope": "general", "skill_name": "boundary"}
    )
    assert first_page["content"] == first[:8000]
    assert first_page["next_offset"] == 8000
    second_page = read_named_audit_skill(
        bank, "demo", {"scope": "general", "skill_name": "boundary", "offset": 8000}
    )
    assert second_page["content"] == first[8000:]
    assert second_page["next_offset"] is None
    with pytest.raises(ValueError, match="最多读取"):
        read_named_audit_skill(bank, "demo", {
            "scope": "general", "skill_name": "boundary", "length": 8001,
        })


def test_bad_later_proposal_does_not_publish_earlier_one(tmp_path):
    bank, root = setup_run(tmp_path)
    ids = [
        propose(root, "general", "first", "可用的通用方法"),
        propose(root, "project", "second", "需要证据的项目方法"),
    ]
    deliver(root, ids)
    request_file = root / ".stage-skill-proposals" / (ids[1] + ".json")
    request = json.loads(request_file.read_text())
    request["evidence"] = [str(root / "missing.txt")]
    request_file.write_text(json.dumps(request))
    with pytest.raises(ValueError, match="证据"):
        apply_updates(bank, root, "demo")
    assert bank.active() == {}
    assert not list((bank.root / "publications").glob("*.json"))


def test_multiple_proposals_replace_active_pointer_once(tmp_path, monkeypatch):
    bank, root = setup_run(tmp_path)
    ids = [
        propose(root, "project", "one", "第一项规则"),
        propose(root, "project", "two", "第二项规则"),
    ]
    deliver(root, ids)
    writes = []
    original = audit_skill_updates.write

    def counted(file, value):
        if Path(file) == bank.root / "active.json":
            writes.append(dict(value))
        return original(file, value)

    monkeypatch.setattr(audit_skill_updates, "write", counted)
    result = apply_updates(bank, root, "demo")
    assert len(writes) == 1
    assert len(result["published"]) == 2
    current = bank.candidate(bank.active()["orchestrator/project/demo"])
    assert current["provenance"]["sections"] == {
        "one": "第一项规则", "two": "第二项规则",
    }



def test_learner_mcp_exposes_bounded_skill_reads(tmp_path, monkeypatch):
    import io
    import submission

    bank, root = setup_run(tmp_path)
    ids = [propose(root, "general", "boundary", "追踪信任边界")]
    deliver(root, ids)
    apply_updates(bank, root, "demo")
    monkeypatch.setattr(submission, "SkillBank", lambda: bank)
    monkeypatch.setattr(submission, "infer_project", lambda _: "demo")
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "get_audit_skills", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "read_audit_skill",
                    "arguments": {"scope": "general", "skill_name": "boundary"}}},
    ]
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        "".join(json.dumps(item) + "\n" for item in requests)
    ))
    monkeypatch.setattr(sys, "stdout", output)
    submission.serve("learner", root)
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    names = {item["name"] for item in responses[0]["result"]["tools"]}
    assert "get_audit_skills" in names and "read_audit_skill" in names
    listing = responses[1]["result"]["structuredContent"]
    assert listing["skills"][0]["skills"] == [{
        "name": "boundary", "characters": len("追踪信任边界"),
    }]
    detail = responses[2]["result"]["structuredContent"]
    assert detail["content"] == "追踪信任边界"



def test_learner_reads_workflow_snapshot_after_concurrent_publication(tmp_path, monkeypatch):
    from skill_bank import write

    bank, first_run = setup_run(tmp_path)
    first = propose(first_run, "general", "boundary", "本轮看到的旧规则")
    deliver(first_run, [first])
    apply_updates(bank, first_run, "demo")
    frozen = tmp_path / "workflow-baseline.json"
    write(frozen, bank.active())
    old_id = bank.active()["orchestrator/general/shared"]

    second_run = tmp_path / "runs/demo/two"
    second_run.mkdir(parents=True)
    (second_run / "trace.txt").write_text("另一个工作流的真实轨迹")
    second = propose(second_run, "general", "boundary", "并发发布的新规则")
    deliver(second_run, [second])
    apply_updates(bank, second_run, "demo")
    assert bank.active()["orchestrator/general/shared"] != old_id

    monkeypatch.setenv("STAGE_SKILL_BASELINE", str(frozen))
    listing = audit_skill_index(bank, "demo")
    assert listing["skills"][0]["id"] == old_id
    detail = read_named_audit_skill(
        bank, "demo", {"scope": "general", "skill_name": "boundary"}
    )
    assert detail["id"] == old_id
    assert detail["content"] == "本轮看到的旧规则"
    assert "本轮看到的旧规则" in bank.render("orchestrator", "demo")["text"]

    monkeypatch.delenv("STAGE_SKILL_BASELINE")
    assert read_named_audit_skill(
        bank, "demo", {"scope": "general", "skill_name": "boundary"}
    )["content"] == "并发发布的新规则"



def test_concurrent_same_name_update_is_skipped_without_losing_other_proposals(
    tmp_path, monkeypatch,
):
    from skill_bank import write

    bank, initial = setup_run(tmp_path)
    first = propose(initial, "general", "boundary", "初始规则")
    deliver(initial, [first])
    apply_updates(bank, initial, "demo")
    baseline = tmp_path / "old-baseline.json"
    write(baseline, bank.active())

    waiting = tmp_path / "runs/demo/waiting"
    waiting.mkdir(parents=True)
    (waiting / "trace.txt").write_text("等待中的学习轨迹")
    monkeypatch.setenv("STAGE_SKILL_BASELINE", str(baseline))
    stale = propose(waiting, "general", "boundary", "基于旧规则的改写")
    independent = propose(waiting, "general", "new-area", "另一个独立主题")
    queued = json.loads((waiting / ".stage-skill-proposals" / f"{stale}.json").read_text())
    assert queued["provenance"]["base_version"] == bank.active()["orchestrator/general/shared"]
    monkeypatch.delenv("STAGE_SKILL_BASELINE")

    other = tmp_path / "runs/demo/other"
    other.mkdir(parents=True)
    (other / "trace.txt").write_text("并发发布轨迹")
    newer = propose(other, "general", "boundary", "其他工作流的新规则")
    deliver(other, [newer])
    apply_updates(bank, other, "demo")
    deliver(waiting, [stale, independent])
    outcome = apply_updates(bank, waiting, "demo")

    assert len(outcome["published"]) == 1
    assert len(outcome["conflicts"]) == 1
    assert outcome["conflicts"][0]["request"] == stale
    assert outcome["conflicts"][0]["status"] == "concurrent_skill_conflict"
    assert outcome["conflicts"][0]["baseline_version"] != outcome["conflicts"][0]["current_version"]
    assert not (bank.root / "imported" / f"{stale}.json").exists()
    current = bank.candidate(bank.active()["orchestrator/general/shared"])
    assert current["provenance"]["sections"] == {
        "boundary": "其他工作流的新规则",
        "new-area": "另一个独立主题",
    }



def test_concurrent_different_name_keeps_direct_adoption(tmp_path, monkeypatch):
    from skill_bank import write

    bank, initial = setup_run(tmp_path)
    first = propose(initial, "general", "boundary", "初始规则")
    deliver(initial, [first])
    apply_updates(bank, initial, "demo")
    baseline = tmp_path / "old-baseline.json"
    write(baseline, bank.active())

    waiting = tmp_path / "runs/demo/waiting"
    waiting.mkdir(parents=True)
    (waiting / "trace.txt").write_text("等待中的学习轨迹")
    monkeypatch.setenv("STAGE_SKILL_BASELINE", str(baseline))
    change = propose(waiting, "general", "boundary", "本轮改进规则")
    monkeypatch.delenv("STAGE_SKILL_BASELINE")

    other = tmp_path / "runs/demo/other"
    other.mkdir(parents=True)
    (other / "trace.txt").write_text("并发发布轨迹")
    addition = propose(other, "general", "other-area", "其他主题规则")
    deliver(other, [addition])
    apply_updates(bank, other, "demo")
    deliver(waiting, [change])
    outcome = apply_updates(bank, waiting, "demo")

    assert len(outcome["published"]) == 1
    assert outcome["conflicts"] == []
    current = bank.candidate(bank.active()["orchestrator/general/shared"])
    assert current["provenance"]["sections"] == {
        "boundary": "本轮改进规则",
        "other-area": "其他主题规则",
    }
