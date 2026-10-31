"""Convert Claude Code stream-json events into action-level trajectory records."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
MAX_SUMMARY_CHARS = 600
MAX_FILES = 20

_SECRET_PATTERNS = (
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "[REDACTED]"),
    (re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{8,}\b"), "[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED]"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]{8,}"), r"\1[REDACTED]"),
    (
        re.compile(
            r"(?i)((?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|secret|password|passwd|authorization)"
            r"\s*[:=]\s*[\"']?)[^\s\"',;}]{4,}"
        ),
        r"\1[REDACTED]",
    ),
)
_RETURN_CODE = re.compile(r"(?i)(?:exit(?:\s+code)?|return\s*code|returncode)\s*[:=]?\s*(-?\d+)")
_PATH_KEYS = ("file_path", "filepath", "path")
_SUMMARY_KEYS = ("description", "command", "pattern", "query", "url", "glob")


def _redact(value: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def _summary(value: Any, limit: int = MAX_SUMMARY_CHARS) -> str:
    text = _redact(_as_text(value))
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _number(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return value


def _timestamp_ms(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.timestamp() * 1000


def _duration_ms(*values: Any) -> float | int:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            return value
    return 0


def _cost(usage: Any, duration_ms: float | int = 0, total_cost_usd: Any = 0) -> dict[str, Any]:
    usage = usage if isinstance(usage, dict) else {}
    input_tokens = _number(usage.get("input_tokens"))
    output_tokens = _number(usage.get("output_tokens"))
    tokens = _number(usage.get("total_tokens")) or input_tokens + output_tokens
    cost_usd = _number(total_cost_usd)
    return {
        "duration_ms": duration_ms,
        "tokens": tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": _number(usage.get("cache_creation_input_tokens")),
        "cache_read_input_tokens": _number(usage.get("cache_read_input_tokens")),
        "total_cost_usd": cost_usd,
        "cost_estimated": not (duration_ms or tokens or cost_usd),
    }


def _content_blocks(event: dict[str, Any]) -> list[dict[str, Any]]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else event.get("content")
    if isinstance(content, list):
        return [block for block in content if isinstance(block, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def _controlled_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    match = re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:/-]{0,119}", value.strip())
    return match.group(0) if match else ""


def _task_metadata(data: dict[str, Any], tool_use_id: str) -> dict[str, str]:
    prompt = data.get("prompt") if isinstance(data.get("prompt"), str) else ""
    description = data.get("description") if isinstance(data.get("description"), str) else ""
    boundary = _controlled_token(data.get("boundary"))
    if not boundary:
        match = re.search(r"\b([A-Za-z][A-Za-z0-9_.-]{0,79})\s+boundary\b", description)
        if not match:
            match = re.search(r"负责\s+\*\*([A-Za-z][A-Za-z0-9_.-]{0,79})", prompt)
        boundary = match.group(1) if match else ""
    skill = _controlled_token(
        data.get("skill") or data.get("subagent_type") or data.get("agent_type")
    )
    task_id = _controlled_token(data.get("task_id") or data.get("taskId"))
    return {
        "tool_use_id": tool_use_id,
        "task_id": task_id,
        "boundary": boundary,
        "skill": skill,
    }


def _files(data: dict[str, Any], tool_name: str) -> list[dict[str, str]]:
    values: list[Any] = []
    for key in _PATH_KEYS:
        if data.get(key):
            values.append(data[key])
    raw_files = data.get("files")
    if isinstance(raw_files, list):
        values.extend(raw_files)
    files = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("path") or value.get("file_path") or value.get("file")
        if not isinstance(value, str) or not value:
            continue
        files.append({"path": _summary(value, 300), "operation": tool_name.lower()})
        if len(files) >= MAX_FILES:
            break
    return files


def _tool_summary(data: dict[str, Any]) -> str:
    for key in _SUMMARY_KEYS:
        if data.get(key):
            return _summary(data[key])
    return ""


def _base_context(tools: list[str], boundary: str = "") -> dict[str, Any]:
    return {"tools": list(tools), "boundary": boundary, "files": []}


def _action(
    *,
    project: str,
    run_id: str,
    sequence: int,
    event: dict[str, Any],
    line_number: int,
    name: str,
    parent_action_id: str | None,
    context: dict[str, Any],
    pre_action: dict[str, Any],
    usage: Any,
    pending: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "action_id": f"{project}/{run_id}/action-{sequence:06d}",
        "sequence": sequence,
        "parent_action_id": parent_action_id,
        "project": project,
        "run_id": run_id,
        "ts": str(event.get("timestamp") or ""),
        "action": name,
        "context": context,
        "pre_action": pre_action,
        "post_action": {"status": "pending" if pending else "recorded", "result_summary": ""},
        "outcome": {"returncode": None, "error": None, "duration_ms": 0},
        "cost": _cost(usage),
        "policy": None,
        "action_propensity": None,
        "source": "claude_stream_json",
        "source_event": {"line": line_number, "uuid": str(event.get("uuid") or "")},
    }


def _result_returncode(block: dict[str, Any], event: dict[str, Any], text: str) -> int | None:
    details = event.get("tool_use_result")
    details = details if isinstance(details, dict) else {}
    for container in (details, block):
        for key in ("returncode", "returnCode", "exit_code", "exitCode"):
            value = container.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    match = _RETURN_CODE.search(text)
    return int(match.group(1)) if match else None


def _apply_tool_result(
    action: dict[str, Any],
    block: dict[str, Any],
    event: dict[str, Any],
) -> None:
    details = event.get("tool_use_result")
    details = details if isinstance(details, dict) else {}
    text = _as_text(block.get("content"))
    error = bool(block.get("is_error") or details.get("is_error") or details.get("error"))
    started_ms = _timestamp_ms(action["ts"])
    ended_ms = _timestamp_ms(event.get("timestamp"))
    observed_duration = _duration_ms(
        details.get("duration_ms"), details.get("durationMs"), block.get("duration_ms")
    )
    if (
        not observed_duration
        and started_ms is not None
        and ended_ms is not None
        and ended_ms >= started_ms
    ):
        observed_duration = ended_ms - started_ms
    action["post_action"] = {
        "status": "error" if error else "completed",
        "result_summary": _summary(block.get("content")),
    }
    action["outcome"] = {
        "returncode": _result_returncode(block, event, text),
        "error": error,
        "duration_ms": observed_duration,
    }
    action["cost"]["duration_ms"] = observed_duration
    if observed_duration:
        action["cost"]["cost_estimated"] = False
    agent_id = _controlled_token(details.get("agentId"))
    if agent_id and action["action"] in {"Task", "Agent"}:
        action["pre_action"]["task_id"] = agent_id


def parse_raw_trace(path: str | Path, project: str, run_id: str) -> list[dict[str, Any]]:
    """Parse a raw.jsonl file without inventing ordering, costs, or dependencies."""

    actions: list[dict[str, Any]] = []
    actions_by_tool: dict[str, dict[str, Any]] = {}
    task_actions: dict[str, dict[str, Any]] = {}
    boundaries: dict[str, str] = {}
    visible_tools: list[str] = []
    source_path = Path(path)

    with source_path.open(encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            parent_tool_id = str(event.get("parent_tool_use_id") or "")
            parent = task_actions.get(parent_tool_id)
            parent_action_id = parent["action_id"] if parent else None
            boundary = boundaries.get(parent_tool_id, "")

            if event_type == "system" and event.get("subtype") == "init":
                raw_tools = event.get("tools")
                if isinstance(raw_tools, list):
                    visible_tools = [
                        _summary(item, 120) for item in raw_tools if isinstance(item, str)
                    ]
                action = _action(
                    project=project,
                    run_id=run_id,
                    sequence=len(actions) + 1,
                    event=event,
                    line_number=line_number,
                    name="init",
                    parent_action_id=None,
                    context=_base_context(visible_tools),
                    pre_action={"cwd": _summary(event.get("cwd"), 300)},
                    usage=None,
                )
                actions.append(action)
                continue

            if event_type == "system" and event.get("subtype") == "task_started":
                tool_id = str(event.get("tool_use_id") or event.get("task_id") or "")
                task = task_actions.get(tool_id)
                if task:
                    task_id = _controlled_token(event.get("task_id"))
                    if task_id:
                        task["pre_action"]["task_id"] = task_id
                continue

            if event_type == "assistant":
                message = event.get("message")
                usage = message.get("usage") if isinstance(message, dict) else None
                for block in _content_blocks(event):
                    block_type = block.get("type")
                    if block_type == "text":
                        text = block.get("text")
                        if not text:
                            continue
                        action = _action(
                            project=project,
                            run_id=run_id,
                            sequence=len(actions) + 1,
                            event=event,
                            line_number=line_number,
                            name="text",
                            parent_action_id=parent_action_id,
                            context=_base_context(visible_tools, boundary),
                            pre_action={"text_summary": _summary(text)},
                            usage=usage,
                        )
                        actions.append(action)
                        continue
                    if block_type != "tool_use":
                        continue
                    tool_name = str(block.get("name") or "unknown_tool")
                    tool_id = str(block.get("id") or "")
                    data = block.get("input") if isinstance(block.get("input"), dict) else {}
                    is_task = tool_name in {"Task", "Agent"}
                    metadata = _task_metadata(data, tool_id) if is_task else {}
                    task_boundary = metadata.get("boundary", "")
                    context = _base_context(visible_tools, task_boundary or boundary)
                    context["tool"] = {"name": tool_name, "input_summary": _tool_summary(data)}
                    context["files"] = [] if is_task else _files(data, tool_name)
                    pre_action = metadata if is_task else {"input_summary": _tool_summary(data)}
                    action = _action(
                        project=project,
                        run_id=run_id,
                        sequence=len(actions) + 1,
                        event=event,
                        line_number=line_number,
                        name=tool_name,
                        parent_action_id=parent_action_id,
                        context=context,
                        pre_action=pre_action,
                        usage=usage,
                        pending=True,
                    )
                    actions.append(action)
                    if tool_id:
                        actions_by_tool[tool_id] = action
                        if is_task:
                            task_actions[tool_id] = action
                            boundaries[tool_id] = task_boundary
                continue

            if event_type == "user":
                for block in _content_blocks(event):
                    if block.get("type") != "tool_result":
                        continue
                    tool_id = str(block.get("tool_use_id") or "")
                    action = actions_by_tool.get(tool_id)
                    if action:
                        _apply_tool_result(action, block, event)
                        continue
                    action = _action(
                        project=project,
                        run_id=run_id,
                        sequence=len(actions) + 1,
                        event=event,
                        line_number=line_number,
                        name="tool_result",
                        parent_action_id=parent_action_id,
                        context=_base_context(visible_tools, boundary),
                        pre_action={"tool_use_id": tool_id},
                        usage=None,
                    )
                    _apply_tool_result(action, block, event)
                    actions.append(action)
                continue

            if event_type == "result":
                duration = _duration_ms(event.get("duration_ms"), event.get("durationMs"))
                action = _action(
                    project=project,
                    run_id=run_id,
                    sequence=len(actions) + 1,
                    event=event,
                    line_number=line_number,
                    name="result",
                    parent_action_id=parent_action_id,
                    context=_base_context(visible_tools, boundary),
                    pre_action={"subtype": str(event.get("subtype") or "")},
                    usage=event.get("usage"),
                )
                action["post_action"] = {
                    "status": "error" if event.get("is_error") else "completed",
                    "result_summary": _summary(event.get("result")),
                }
                action["outcome"] = {
                    "returncode": None,
                    "error": bool(event.get("is_error")),
                    "duration_ms": duration,
                }
                action["cost"] = _cost(event.get("usage"), duration, event.get("total_cost_usd"))
                actions.append(action)

    return actions


def write_jsonl(actions: Iterable[dict[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for action in actions:
            handle.write(json.dumps(action, ensure_ascii=False, sort_keys=True) + "\n")
