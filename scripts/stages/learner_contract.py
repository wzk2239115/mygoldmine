"""Validate the learning agent's own final deliverable."""
import json
from pathlib import Path

STAGES = {"environment", "orchestrator", "visual", "verify", "redteam-lab",
          "redteam-agent", "judge", "learner"}
CATEGORIES = {"method_gap", "project_knowledge", "framework_bug", "insufficient_evidence",
              "no_change"}


def validate_learning_result(file, root, project=None):
    root = Path(root).resolve()
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("学习产物必须为 schema_version=1 的 JSON 对象")
    if not isinstance(data.get("project"), str) or not data["project"].strip():
        raise ValueError("学习产物缺少项目编号")
    if project and project != "unknown" and data["project"] != project:
        raise ValueError("学习产物项目编号与本次任务不一致")
    if data.get("status") not in {"completed", "no_changes", "blocked"}:
        raise ValueError("学习产物结论必须为 completed、no_changes 或 blocked")
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or any(not isinstance(v, str) for v in limitations):
        raise ValueError("学习产物 limitations 必须为字符串数组")
    if data["status"] == "blocked" and not limitations:
        raise ValueError("学习受阻必须说明限制")
    proposals = data.get("proposal_ids")
    if not isinstance(proposals, list) or any(not isinstance(v, str) for v in proposals):
        raise ValueError("学习产物 proposal_ids 必须为字符串数组")
    if data["status"] == "no_changes" and proposals:
        raise ValueError("无修改结论不能同时声明已提交候选")
    for identifier in proposals:
        if not identifier or Path(identifier).name != identifier:
            raise ValueError("优化候选编号无效")
        if not (root / ".stage-skill-proposals" / (identifier + ".json")).is_file():
            raise ValueError("优化候选编号没有对应的提交记录")
    conclusions = data.get("conclusions")
    if not isinstance(conclusions, list) or not conclusions:
        raise ValueError("学习产物必须包含至少一条归因，包括无修改或受阻的原因")
    files = []
    for row in conclusions:
        if not isinstance(row, dict) or row.get("stage") not in STAGES:
            raise ValueError("学习归因缺少有效阶段")
        if row.get("category") not in CATEGORIES:
            raise ValueError("学习归因类别无效")
        for key in ("reason", "next_action"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError("学习归因必须说明 reason 和 next_action")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("每条学习归因必须引用本次目录中的证据文件")
        for value in evidence:
            if not isinstance(value, str) or not value:
                raise ValueError("学习证据路径无效")
            path = Path(value)
            path = path if path.is_absolute() else root / path
            if path in {root / "rsi/exploration-feedback.json", root / "rsi/reward.json",
                        root / "rsi/stage-learning-run.json", root / "rsi/stage-learning-evaluation.json",
                        root / "rsi/learning-retry.json"}:
                raise ValueError("该反馈文件会在后续评估中更新；请使用 Write 将引用片段保存至 rsi/learning-evidence 后引用快照")
            if not path.is_relative_to(root) or ".." in path.parts:
                raise ValueError("学习证据超出本次输出目录")
            cursor = root
            for part in path.relative_to(root).parts:
                cursor /= part
                if cursor.is_symlink():
                    raise ValueError("学习证据不能包含符号链接")
            if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("学习证据缺失、不是普通文件或超过大小限制")
            files.append(path)
    return sorted(set(files))
