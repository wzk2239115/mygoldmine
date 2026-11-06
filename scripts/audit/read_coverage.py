#!/usr/bin/env python3
"""阶段二读取观测与事先声明的审计意图；不改变漏洞验证状态。"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
from agentcov.claude_transcript import (  # noqa: E402
    _claude_read_result_bounds,
    payloads_from_claude_records,
)
from agentcov.hooks import events_from_payload  # noqa: E402

FIELDS = ("AUDIT_INTENT_ID", "AUDIT_INTENT", "COVERAGE_ID", "HYPOTHESIS", "AUDIT_SCOPE")
NOTE = (
    "读取观测不证明已经理解或完成审计；搜索命中、未知范围和未关联意图分别保留。"
    "没有完整分母，不计算全仓库覆盖率。"
)


def declaration(prompt):
    result = {}
    for field in FIELDS:
        match = re.search(r"^[ \t]*" + field + r":[ \t]*([^\n]+)", prompt, re.M)
        if match:
            result[field] = match.group(1).strip()
    return result if all(result.get(key) for key in FIELDS) else None


def append(root, name, value):
    root.mkdir(parents=True, exist_ok=True)
    with (root / name).open("a", encoding="utf-8") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        file.write(json.dumps(value, ensure_ascii=False) + "\n")


def records(file):
    if not file.exists():
        return []
    result = []
    with file.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    result.append(item)
            except ValueError:
                continue
    return result


def transcript_file(payload):
    own = payload.get("agent_transcript_path")
    main = payload.get("transcript_path")
    agent = payload.get("agent_id")
    if own:
        return Path(own)
    if main and agent and re.fullmatch(r"[A-Za-z0-9_-]+", agent):
        return Path(main).with_suffix("") / "subagents" / f"agent-{agent}.jsonl"
    return Path(main) if main else None


def task_intent(payload, root):
    """只使用当前会话的原始任务与派发前登记匹配，不按最近任务猜测。"""
    transcript = transcript_file(payload)
    if not transcript or not transcript.is_file():
        return None
    prompt = ""
    # 原始会话的第一个用户消息是分派任务；后续工具输出不能改变意图。
    with Path(transcript).open(encoding="utf-8", errors="replace") as stream:
        for index, line in enumerate(stream):
            if index > 40:
                break
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if item.get("type") != "user":
                continue
            content = item.get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "\n".join(x.get("text", "") for x in content if x.get("type") == "text")
            if isinstance(content, str) and content:
                prompt = content
                break
    declared = declaration(prompt)
    if not declared:
        return None
    registered = [
        x.get("intent")
        for x in records(root / "intents.jsonl")
        if x.get("intent") and x.get("status") == "declared"
    ]
    same_id = [x for x in registered if x.get("AUDIT_INTENT_ID") == declared["AUDIT_INTENT_ID"]]
    return declared if same_id and all(x == declared for x in same_id) else None


def observe(payload, root, target, project, version):
    if payload.get("hook_event_name") == "SubagentStop":
        transcript = transcript_file(payload)
        if not transcript or not transcript.is_file():
            return
        history = records(transcript)
        results = {}
        for record in history:
            message = record.get("message", {}).get("content", [])
            if not isinstance(message, list):
                continue
            for block in message:
                if block.get("type") == "tool_result":
                    results[block.get("tool_use_id")] = (
                        record.get("toolUseResult", block.get("content")),
                        block.get("is_error"),
                    )
        for record in history:
            message = record.get("message", {}).get("content", [])
            if not isinstance(message, list):
                continue
            for block in message:
                if block.get("type") != "tool_use" or block.get("name") not in {
                    "Read",
                    "Grep",
                    "Bash",
                }:
                    continue
                result = results.get(block.get("id"))
                if result is None or result[1]:
                    continue
                observe(
                    {
                        **payload,
                        "hook_event_name": "PostToolUse",
                        "tool_name": block["name"],
                        "tool_input": block.get("input", {}),
                        "tool_use_id": block.get("id"),
                        "tool_response": result[0],
                    },
                    root,
                    target,
                    project,
                    version,
                )
        return
    if payload.get("hook_event_name") == "PreToolUse":
        if payload.get("tool_name") not in {"Agent", "Task"}:
            return
        prompt = payload.get("tool_input", {}).get("prompt", "")
        intent = declaration(prompt)
        existing = [
            x.get("intent")
            for x in records(root / "intents.jsonl")
            if x.get("intent") and x.get("status") == "declared"
        ]
        conflict = intent and any(
            x["AUDIT_INTENT_ID"] == intent["AUDIT_INTENT_ID"] and x != intent for x in existing
        )
        append(
            root,
            "intents.jsonl",
            {
                "intent": intent,
                "tool_use_id": payload.get("tool_use_id"),
                "status": "conflict" if conflict else "declared" if intent else "missing",
                "stage": "II",
            },
        )
        if not intent or conflict:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": (
                                "分派前请填写 AUDIT_INTENT_ID、AUDIT_INTENT、"
                                "COVERAGE_ID、HYPOTHESIS、AUDIT_SCOPE 五个独立行。"
                                "意图编号不得与已登记的不同任务冲突。"
                            ),
                        }
                    },
                    ensure_ascii=False,
                )
            )
        return
    if payload.get("hook_event_name") != "PostToolUse":
        return
    result = payload.get("tool_response")
    if isinstance(result, dict) and (
        result.get("is_error")
        or result.get("error")
        or result.get("exitCode", result.get("exit_code", 0))
    ):
        append(
            root, "errors.jsonl", {"type": "tool_failed", "tool_use_id": payload.get("tool_use_id")}
        )
        return
    if payload.get("tool_name") == "Read" and _claude_read_result_bounds(result) is None:
        append(
            root,
            "events.jsonl",
            {
                "kind": "unknown",
                "ranges": [],
                "tool_use_id": payload.get("tool_use_id"),
                "session_id": payload.get("session_id"),
                "stage": "II",
                "project": project,
                "source_version": version,
                "intent": task_intent(payload, root),
            },
        )
        return
    tool_id = payload.get("tool_use_id", "observed")
    # 复用上游 Claude 适配器，依据实际返回范围处理截断、失败和搜索输出。
    content = {
        "type": "tool_use",
        "id": tool_id,
        "name": payload.get("tool_name"),
        "input": payload.get("tool_input", {}),
    }
    use = {
        "type": "assistant",
        "cwd": payload.get("cwd", str(target)),
        "sessionId": payload.get("session_id"),
        "message": {"content": [content]},
    }
    response = {
        "type": "user",
        "toolUseResult": payload.get("tool_response"),
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": payload.get("tool_response"),
                }
            ]
        },
    }
    intent = task_intent(payload, root)
    for normalized in payloads_from_claude_records([use, response]):
        _, events = events_from_payload(normalized, source="stage-II-post-tool-use", agent="claude")
        for event in events:
            item = event.to_json()
            if item.get("file"):
                file = Path(item["file"])
                file = (Path(item.get("repo_root") or target) / file).resolve()
                try:
                    relative = file.relative_to(target.resolve())
                except ValueError:
                    continue
                # 仅统计版本管理中的目标代码，排除技能、报告和沙箱外文件。
                tracked = (
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(target),
                            "ls-files",
                            "--error-unmatch",
                            "--",
                            str(relative),
                        ],
                        capture_output=True,
                    ).returncode
                    == 0
                )
                if not tracked or not file.is_file() or file.stat().st_size > 5 * 1024 * 1024:
                    continue
                item["file"] = str(relative)
                item["file_sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
            # 命令和任务原文可能含敏感内容，仅持久化结构化位置和明确的意图。
            for key in ("command", "task_path", "cwd", "repo_root"):
                item.pop(key, None)
            item.update(
                project=project,
                source_version=version,
                stage="II",
                intent=intent,
                intent_status="declared" if intent else "unattributed",
                transcript=(transcript_file(payload) or Path("unknown")).name,
            )
            append(root, "events.jsonl", item)


def summarize(root, project, version):
    events = records(root / "events.jsonl")
    unique = {}
    for item in events:
        identity = tuple(
            item.get(k)
            for k in ("session_id", "transcript", "tool_use_id", "file", "kind", "file_sha256")
        )
        identity += (json.dumps(item.get("ranges"), sort_keys=True),)
        unique[identity] = item
    events = list(unique.values())
    groups = {}
    for item in events:
        key = (
            item.get("file"),
            item.get("file_sha256"),
            (item.get("intent") or {}).get("AUDIT_INTENT_ID"),
            item.get("kind"),
        )
        group = groups.setdefault(
            key,
            {
                "file": key[0],
                "file_sha256": key[1],
                "intent": item.get("intent"),
                "kind": key[3],
                "ranges": [],
                "observations": 0,
            },
        )
        group["observations"] += 1
        group["ranges"].extend(item.get("ranges", []))
    document = {
        "schema_version": 1,
        "stage": "II",
        "project": project,
        "source_version": version,
        "collector": "agentcov",
        "supported_tools": ["Read", "Grep", "Bash"],
        "intent_granularity": "dispatched_task",
        "intent_source": "pre_dispatch_declaration",
        "collector_revision": "d9b1f7abcfbe9262dc9abab988d6b3bc92dd944a",
        "status": "observed" if events else "no_observations",
        "observations": len(events),
        "unattributed": sum(not x.get("intent") for x in events),
        "collection_errors": len(records(root / "errors.jsonl")),
        "intents": records(root / "intents.jsonl"),
        "files": list(groups.values()),
        "limitations": [NOTE],
    }
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / "summary.tmp"
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(root / "summary.json")
    lines = [
        "# 阶段二：读取覆盖与审计意图",
        "",
        NOTE,
        "",
        f"项目：{project}；源码版本：{version}；读取观测：{len(events)}；未关联意图：{document['unattributed']}；采集异常：{document['collection_errors']}",
        "",
    ]
    for group in groups.values():
        intent = group["intent"] or {}
        bounds = ", ".join(f"{x['start']}-{x['end']}" for x in group["ranges"])
        lines.append(
            f"- `{group['file'] or '未知位置'}`（{group['kind']}，{bounds or '未知范围'}）："
            f"{intent.get('AUDIT_INTENT', '未关联意图')}；"
            f"假设：{intent.get('HYPOTHESIS', '未登记')}"
        )
    (root / "summary.md").write_text("\n".join(lines) + "\n")
    return document


def main():
    parser = argparse.ArgumentParser(description="阶段二读取覆盖与审计意图采集")
    parser.add_argument("action", choices=["hook", "summary", "init"])
    args = parser.parse_args()
    if not os.environ.get("MYGOLDMINE_READ_COVERAGE_ROOT"):
        return
    root = Path(os.environ["MYGOLDMINE_READ_COVERAGE_ROOT"])
    try:
        target = Path(os.environ["MYGOLDMINE_READ_COVERAGE_TARGET"])
        project = os.environ["MYGOLDMINE_READ_COVERAGE_PROJECT"]
        version = os.environ["MYGOLDMINE_READ_COVERAGE_VERSION"]
        if args.action == "init":
            if root.exists():
                import time

                root.rename(
                    root.parent.parent
                    / "task-state"
                    / ("previous-read-coverage-" + str(time.time_ns()))
                )
            root.mkdir(parents=True, exist_ok=True)
            (root / "context.json").write_text(
                json.dumps(
                    {
                        "project": project,
                        "source_version": version,
                        "run_id": root.parent.parent.name,
                        "stage": "II",
                    }
                )
            )
        elif args.action == "hook":
            observe(json.load(sys.stdin), root, target, project, version)
        else:
            summarize(root, project, version)
    except Exception as exc:
        append(root, "errors.jsonl", {"type": type(exc).__name__, "message": str(exc)[:300]})
        print("读取覆盖采集异常，已记录；不改变漏洞验证结论。", file=sys.stderr)
        return 1 if args.action == "init" else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
