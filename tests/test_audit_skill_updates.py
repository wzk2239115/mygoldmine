import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/stages"))
from audit_skill_updates import apply_updates, request_update
from skill_bank import SkillBank, write
from stage_tools import submit_structured


def setup(tmp_path):
    root = tmp_path / "runs/demo/one"
    root.mkdir(parents=True)
    (root / "trace.txt").write_text("真实的探索证据")
    return SkillBank(tmp_path), root


def propose(root, scope, name, content):
    return request_update(
        "learner",
        root,
        {
            "scope": scope,
            "skill_name": name,
            "content": content,
            "evidence": [str(root / "trace.txt")],
        },
    )["id"]


def deliver(root, ids):
    receipt = submit_structured(
        "learner",
        root,
        {
            "status": "completed" if ids else "no_changes",
            "conclusions": [
                {
                    "stage": "orchestrator",
                    "category": "method_gap",
                    "reason": "存在未探索入口",
                    "next_action": "深入调用关系",
                    "evidence": ["trace.txt"],
                }
            ],
            "proposal_ids": ids,
            "summary": "本轮方法更新",
            "limitations": [],
        },
        task={"project": "demo"},
    )
    assert receipt["success"], receipt


def test_accepted_learning_updates_both_scopes_without_evaluation_suite(tmp_path):
    bank, root = setup(tmp_path)
    ids = [
        propose(root, "general", "trust-boundary", "追踪配置到执行入口"),
        propose(root, "project", "plugin-architecture", "深入插件更新权限"),
    ]
    deliver(root, ids)
    result = apply_updates(bank, root, "demo")
    assert len(result["published"]) == 2
    assert not (tmp_path / "config/stage-evals").exists()
    text = bank.render("orchestrator", "demo")["text"]
    assert "追踪配置到执行入口" in text and "深入插件更新权限" in text
    assert "深入插件更新权限" not in bank.render("orchestrator", "other")["text"]
    assert "追踪配置到执行入口" in bank.render("orchestrator", "other")["text"]
    again = apply_updates(bank, root, "demo")
    assert again["published"] == []
    assert len(list((bank.root / "publications").glob("*.json"))) == 2


def test_update_same_name_preserves_other_skills_and_frozen_round(tmp_path, monkeypatch):
    bank, root = setup(tmp_path)
    ids = [
        propose(root, "project", "auth", "old auth"),
        propose(root, "project", "plugins", "keep plugins"),
    ]
    deliver(root, ids)
    apply_updates(bank, root, "demo")
    frozen = tmp_path / "baseline.json"
    write(frozen, bank.active())
    newer = propose(root, "project", "auth", "new auth")
    deliver(root, [newer])
    apply_updates(bank, root, "demo")
    text = bank.render("orchestrator", "demo")["text"]
    assert "new auth" in text and "old auth" not in text and "keep plugins" in text
    monkeypatch.setenv("STAGE_SKILL_BASELINE", str(frozen))
    previous = bank.render("orchestrator", "demo")["text"]
    assert "old auth" in previous and "new auth" not in previous


def test_unaccepted_learning_does_not_activate_and_rollback_supported(tmp_path):
    bank, root = setup(tmp_path)
    identifier = propose(root, "project", "method", "actual method")
    assert bank.active() == {}
    # A hand-written file without an accepted tool receipt cannot activate.
    write(
        root / "rsi/learning-result.json",
        {"project": "demo", "status": "completed", "proposal_ids": [identifier]},
    )
    with pytest.raises(ValueError):
        apply_updates(bank, root, "demo")
    assert bank.active() == {}
    deliver(root, [identifier])
    result = apply_updates(bank, root, "demo")
    version = bank.root / "versions" / result["published"][0] / "SKILL.md"
    assert version.is_file()
    publication = next((bank.root / "publications").glob("*.json"))
    bank.rollback(publication.stem)
    assert bank.active() == {}


def test_only_explicit_learning_requests_are_adopted(tmp_path):
    bank, root = setup(tmp_path)
    hidden = propose(root, "general", "unselected", "must not enable")
    selected = propose(root, "project", "selected", "enable this")
    deliver(root, [selected])
    apply_updates(bank, root, "demo")
    assert "must not enable" not in bank.render("orchestrator", "demo")["text"]
    assert not (bank.root / "imported" / (hidden + ".json")).exists()


def test_retry_learning_publishes_current_requests_before_return(tmp_path, monkeypatch):
    import retry_learning as retry

    bank, source = setup(tmp_path)
    output = tmp_path / "runs/demo/two"
    output.mkdir(parents=True)
    (output / "trace.txt").write_text("真实反馈")
    monkeypatch.setattr(retry, "ROOT", tmp_path)
    monkeypatch.setattr(retry, "feedback", lambda *a, **k: {"interesting": False})

    def producer(root, project, **kwargs):
        identifier = propose(root, "project", "next-target", "优先追踪尚未覆盖的入口")
        deliver(root, [identifier])
        return {"exit_code": 0, "skillopt": {"results": []}}

    monkeypatch.setattr(retry, "learn", producer)
    result = retry.retry_learning(source, output, "demo")
    assert result["status"] == "completed"
    assert result["evaluation"]["status"] == "updated_for_next_round"
    assert result["evaluation"]["published"]
    assert "优先追踪尚未覆盖的入口" in bank.render("orchestrator", "demo")["text"]
