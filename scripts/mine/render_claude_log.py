#!/usr/bin/env python3
"""Render Claude Code stream-json (raw.jsonl) into a human-readable log.

Usage:
    python3 scripts/mine/render_claude_log.py --input raw.jsonl --output claude.rendered.log
    python3 scripts/mine/render_claude_log.py --self-test

The renderer is deliberately tolerant: non-JSON lines are echoed, unknown event
types are skipped, missing fields degrade to placeholders, and a single bad
record never aborts the whole log. Secrets matching common key patterns are
redacted unless --no-redact is given.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

SCHEMA_VERSION = 1
DEFAULT_MAX_TEXT = 4000
DEFAULT_MAX_RESULT = 2000
DEFAULT_MAX_RAW = 2000

SECRET_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "sk-[REDACTED]"),
    (
        re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]{16,}"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)((?:api[_-]?key|access[_-]?token|secret|password)"
            r"\s*[:=]\s*[\"']?)[^\s\"',}]{8,}"
        ),
        r"\1[REDACTED]",
    ),
)

TOOL_HINTS = ("description", "command", "file_path", "path", "pattern", "url", "query", "prompt")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact(text: str) -> str:
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def clip(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


def indent_block(text: str, prefix: str = "  ") -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(prefix + line if line else prefix.rstrip() for line in lines)


def block_text(block: Any) -> str:
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return as_text(block)
    btype = block.get("type")
    if btype == "text":
        return as_text(block.get("text"))
    if btype == "thinking":
        return as_text(block.get("thinking"))
    if btype == "redacted_thinking":
        return "[redacted thinking]"
    if btype == "image":
        return "[image]"
    if btype == "tool_result":
        return as_text(block.get("content"))
    return as_text(block)


def render_tool_use(block: dict, redact_on: bool, max_text: int) -> list[str]:
    name = as_text(block.get("name")) or "?"
    raw_input = block.get("input")
    data = raw_input if isinstance(raw_input, dict) else {}
    lines: list[str] = []

    summary = ""
    for key in TOOL_HINTS:
        if data.get(key):
            summary = as_text(data.get(key))
            break
    if not summary and data:
        summary = as_text(data)
    if not summary and isinstance(raw_input, str):
        summary = raw_input
    lines.append(f"[tool:{name}] {clip(summary, 300)}".rstrip())

    if data.get("command"):
        command = clip(as_text(data.get("command")), max_text)
        lines.append(indent_block(command, "  $ "))
    if data.get("file_path") or data.get("path"):
        lines.append(f"  file: {as_text(data.get('file_path') or data.get('path'))}")
    if data.get("pattern"):
        lines.append(f"  pattern: {as_text(data.get('pattern'))}")
    if data.get("url"):
        lines.append(f"  url: {as_text(data.get('url'))}")
    known = set(TOOL_HINTS)
    extras = {k: v for k, v in data.items() if k not in known}
    if extras and name not in {"Bash", "Read", "Edit", "Write", "Grep", "Glob"}:
        lines.append(f"  input: {clip(as_text(extras), 500)}")
    if redact_on:
        lines = [redact(line) for line in lines]
    return lines


def render_content(
    content: Any, role: str, redact_on: bool, max_text: int, max_result: int
) -> list[str]:
    lines: list[str] = []
    blocks: Iterable[Any]
    if isinstance(content, list):
        blocks = content
    elif content is None:
        blocks = []
    else:
        blocks = [content]

    for block in blocks:
        if isinstance(block, dict):
            btype = block.get("type")
            if btype == "tool_use":
                lines.extend(render_tool_use(block, redact_on, max_text))
                continue
            if btype == "tool_result":
                if role == "user":
                    is_error = bool(block.get("is_error"))
                    tag = "[tool-error]" if is_error else "[tool-result]"
                    text = clip(as_text(block.get("content")), max_result)
                    lines.append(f"{tag} {text}".rstrip())
                    continue
            if btype == "thinking":
                thinking = clip(as_text(block.get("thinking")), max_text)
                lines.append(f"[thinking] {thinking}".rstrip())
                continue
            if btype == "text":
                text = clip(as_text(block.get("text")), max_text)
                if text:
                    lines.append(f"[assistant] {text}" if role == "assistant" else text)
                continue
            if btype == "image":
                lines.append("[image]")
                continue
            if btype == "redacted_thinking":
                lines.append("[thinking] [redacted thinking]")
                continue
            text = as_text(block)
            if text:
                lines.append(clip(text, max_text))
        else:
            text = as_text(block)
            if text:
                lines.append(clip(text, max_text))
    if redact_on:
        lines = [redact(line) for line in lines]
    return lines


def render_event(
    event: dict,
    stats: dict,
    redact_on: bool,
    max_text: int,
    max_result: int,
    include_unknown: bool = False,
) -> list[str]:
    etype = as_text(event.get("type"))
    stats["events"][etype or "<unknown>"] += 1

    if etype == "system":
        subtype = as_text(event.get("subtype")) or "?"
        stats["events"][f"system:{subtype}"] += 1
        if subtype == "init":
            model = as_text(event.get("model")) or "?"
            cwd = as_text(event.get("cwd")) or "?"
            tools = event.get("tools")
            tool_note = f" tools={len(tools)}" if isinstance(tools, list) else ""
            line = f"[init] model={model} cwd={cwd}{tool_note}"
        else:
            line = f"[system:{subtype}] {as_text(event.get('status') or event.get('message') or '')}".rstrip()
        return [redact(line) if redact_on else line]

    if etype == "rate_limit_event":
        info = event.get("rate_limit_info")
        info = info if isinstance(info, dict) else {}
        status = as_text(info.get("status")) or "?"
        kind = as_text(info.get("rateLimitType")) or as_text(info.get("type"))
        line = f"[rate-limit] status={status}"
        if kind:
            line += f" type={kind}"
        return [line]

    if etype in ("assistant", "user"):
        message = event.get("message")
        if isinstance(message, dict):
            role = as_text(message.get("role")) or etype
            content = message.get("content")
        else:
            role = etype
            content = event.get("content")
        return render_content(content, role, redact_on, max_text, max_result)

    if etype == "result":
        stats["result_seen"] = True
        is_error = bool(event.get("is_error"))
        if is_error:
            stats["result_errors"] += 1
        parts = [f"is_error={str(is_error).lower()}"]
        for key in ("subtype", "duration_ms", "duration_api_ms", "num_turns", "total_cost_usd"):
            if event.get(key) is not None:
                parts.append(f"{key}={as_text(event.get(key))}")
        lines = [f"[result] {' '.join(parts)}"]
        text = as_text(event.get("result"))
        if text:
            lines.append(clip(text, max_text))
        if redact_on:
            lines = [redact(line) for line in lines]
        return lines

    if etype == "stream_event" or not include_unknown:
        return []

    payload = as_text(event.get("message") or event.get("content") or "")
    line = f"[event:{etype or '?'}] {clip(payload, 500)}".rstrip()
    return [redact(line) if redact_on else line]


def iter_content_blocks(event: dict) -> Iterable[dict]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else event.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block
    elif isinstance(content, dict):
        yield content


def render_stream(
    lines: Iterable[str],
    source: str,
    redact_on: bool = True,
    max_text: int = DEFAULT_MAX_TEXT,
    max_result: int = DEFAULT_MAX_RESULT,
    max_raw: int = DEFAULT_MAX_RAW,
    include_unknown: bool = False,
) -> tuple[str, dict]:
    stats = {
        "lines_total": 0,
        "json_ok": 0,
        "invalid": 0,
        "blank": 0,
        "events": Counter(),
        "tool_calls": Counter(),
        "tool_errors": 0,
        "render_errors": 0,
        "result_seen": False,
        "result_errors": 0,
    }
    out: list[str] = [
        "# Claude stream-json rendered log",
        f"# source: {source}",
        f"# rendered_at: {utc_now()}",
        f"# renderer: render_claude_log.py schema={SCHEMA_VERSION}",
        "",
    ]

    def emit(text: str) -> None:
        out.append(redact(text) if redact_on else text)

    for raw_line in lines:
        stats["lines_total"] += 1
        line = raw_line.rstrip("\n").rstrip("\r")
        if not line.strip():
            stats["blank"] += 1
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            stats["invalid"] += 1
            emit(clip(line, max_raw))
            continue
        stats["json_ok"] += 1
        if not isinstance(event, dict):
            emit(clip(line, max_raw))
            continue
        try:
            rendered = render_event(
                event, stats, redact_on, max_text, max_result, include_unknown
            )
            for block in iter_content_blocks(event):
                if block.get("type") == "tool_use":
                    stats["tool_calls"][as_text(block.get("name")) or "?"] += 1
                elif block.get("type") == "tool_result" and block.get("is_error"):
                    stats["tool_errors"] += 1
            for item in rendered:
                if item:
                    emit(item)
        except Exception as exc:  # noqa: BLE001 - renderer must never abort a run
            stats["render_errors"] += 1
            emit(f"[render-error] {type(exc).__name__}: {exc}")

    tool_total = sum(stats["tool_calls"].values())
    tool_detail = " ".join(f"{k}={v}" for k, v in sorted(stats["tool_calls"].items()))
    summary = (
        f"[summary] lines={stats['lines_total']} json_ok={stats['json_ok']} "
        f"invalid={stats['invalid']} blank={stats['blank']} "
        f"tool_calls={tool_total} tool_errors={stats['tool_errors']} "
        f"render_errors={stats['render_errors']} "
        f"result_seen={str(stats['result_seen']).lower()} "
        f"result_errors={stats['result_errors']}"
    )
    if tool_detail:
        summary += f" tools({tool_detail})"
    out.append("")
    emit(summary)
    return "\n".join(out) + "\n", stats


def run_render(args: argparse.Namespace) -> int:
    if args.input == "-":
        source = "<stdin>"
        data = sys.stdin.read()
    else:
        source = args.input
        try:
            with open(args.input, "r", encoding="utf-8", errors="replace") as handle:
                data = handle.read()
        except OSError as exc:
            print(f"render_claude_log: 无法读取输入 {args.input}: {exc}", file=sys.stderr)
            return 2

    text, stats = render_stream(
        data.splitlines(),
        source=source,
        redact_on=not args.no_redact,
        max_text=args.max_text,
        max_result=args.max_result,
        max_raw=args.max_raw,
        include_unknown=args.include_unknown,
    )

    if args.output == "-":
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except BrokenPipeError:
            return 0
        return 0

    try:
        parent = os.path.dirname(os.path.abspath(args.output))
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = f"{args.output}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8", errors="replace") as handle:
            handle.write(text)
        os.replace(tmp, args.output)
    except OSError as exc:
        print(f"render_claude_log: 无法写入 {args.output}: {exc}", file=sys.stderr)
        return 3

    if not args.quiet:
        print(
            f"render_claude_log: {stats['lines_total']} lines, "
            f"{stats['invalid']} invalid, {sum(stats['tool_calls'].values())} tool calls "
            f"-> {args.output}",
            file=sys.stderr,
        )
    return 0


SAMPLE_EVENTS = [
    {"type": "system", "subtype": "init", "model": "test-model", "cwd": "/workspace/repo", "tools": ["Bash", "Edit"]},
    {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}},
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "先看项目结构"},
                {"type": "text", "text": "开始审计目标仓库。"},
                {"type": "tool_use", "name": "Bash", "input": {"description": "列出源码", "command": "ls -la && echo ok"}},
            ],
        },
    },
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/workspace/repo/app.py"}},
                {
                    "type": "tool_use",
                    "name": "Write",
                    "input": {"file_path": "/runs/x/audit-report.md", "content": "x" * 50},
                },
            ],
        },
    },
    {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "content": "file-a\nfile-b", "is_error": False},
                {"type": "tool_result", "content": "permission denied", "is_error": True},
            ],
        },
    },
    {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "content": [{"type": "text", "text": "nested"}]}]},
    },
    {"type": "result", "is_error": False, "duration_ms": 1234, "num_turns": 3, "total_cost_usd": 0.01, "result": "报告已生成"},
    {"type": "result", "is_error": True, "subtype": "error_during_execution", "duration_ms": 9},
    {"type": "assistant"},
    {"type": "user"},
    {"type": "assistant", "message": {"content": None}},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
    {"type": "unknown_event", "message": "hello"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "key sk-ABCDEFGHIJKLMNOPQRSTUVWX and Bearer abcdefghijklmnopqrstuvwx"}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "api_key = \"supersecretvalue\""}]}},
    "not-json-line",
    "{broken json",
    "",
    "[1, 2, 3]",
    '"json string"',
]


def self_test() -> int:
    failures: list[str] = []

    raw_text = "\n".join(
        item if isinstance(item, str) else json.dumps(item, ensure_ascii=False) for item in SAMPLE_EVENTS
    )
    rendered, stats = render_stream(raw_text.splitlines(), source="<self-test>")

    checks = {
        "[init] model=test-model cwd=/workspace/repo": "init event",
        "[rate-limit] status=allowed": "rate limit event",
        "[thinking] 先看项目结构": "thinking block",
        "[assistant] 开始审计目标仓库。": "assistant text",
        "[tool:Bash] 列出源码": "tool summary",
        "$ ls -la && echo ok": "bash command",
        "file: /workspace/repo/app.py": "file path",
        "[tool-result] file-a": "tool result",
        "[tool-error] permission denied": "tool error",
        "nested": "nested tool result blocks",
        "[result] is_error=false duration_ms=1234 num_turns=3 total_cost_usd=0.01": "result fields",
        "报告已生成": "result text",
        "not-json-line": "non-JSON line passthrough",
        "{broken json": "invalid JSON passthrough",
        "[render-error]": "should not appear",
        "[summary]": "summary line",
        "sk-[REDACTED]": "sk- redaction",
        "Bearer [REDACTED]": "bearer redaction",
        'api_key = "[REDACTED]"': "generic secret redaction",
    }
    for needle, label in checks.items():
        present = needle in rendered
        if needle == "[render-error]":
            if present:
                failures.append(f"unexpected {label}")
            continue
        if not present:
            failures.append(f"missing {label}: {needle!r}")

    for leaked in ("sk-ABCDEFGHIJKLMNOPQRSTUVWX", "abcdefghijklmnopqrstuvwx", "supersecretvalue"):
        if leaked in rendered:
            failures.append(f"secret leaked: {leaked}")

    if stats["invalid"] < 2:
        failures.append(f"expected >=2 invalid lines, got {stats['invalid']}")
    if stats["render_errors"] != 0:
        failures.append(f"unexpected render errors: {stats['render_errors']}")
    if stats["tool_calls"].get("Bash") != 2:
        failures.append(f"expected 2 Bash calls, got {dict(stats['tool_calls'])}")
    if stats["tool_errors"] != 1:
        failures.append(f"expected 1 tool error, got {stats['tool_errors']}")

    no_redact, _ = render_stream(raw_text.splitlines(), source="<self-test>", redact_on=False)
    if "sk-ABCDEFGHIJKLMNOPQRSTUVWX" not in no_redact:
        failures.append("--no-redact did not preserve original text")

    empty_out, empty_stats = render_stream([], source="<empty>")
    if "[summary]" not in empty_out or empty_stats["lines_total"] != 0:
        failures.append("empty input did not render cleanly")

    weird = render_stream(["\x00\x01\x02", '{"type": "assistant", "message": {"content": [{"type": "text"}]}}'], source="<weird>")
    if "[summary]" not in weird[0]:
        failures.append("weird input did not render cleanly")

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "raw.jsonl")
        out_path = os.path.join(tmpdir, "nested", "claude.rendered.log")
        with open(raw_path, "w", encoding="utf-8") as handle:
            handle.write(raw_text + "\n")
        rc = run_render(
            argparse.Namespace(
                input=raw_path,
                output=out_path,
                no_redact=False,
                max_text=DEFAULT_MAX_TEXT,
                max_result=DEFAULT_MAX_RESULT,
                max_raw=DEFAULT_MAX_RAW,
                include_unknown=False,
                quiet=True,
            )
        )
        if rc != 0:
            failures.append(f"file render exited {rc}")
        if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
            failures.append("file render produced no output")
        else:
            with open(out_path, "r", encoding="utf-8") as handle:
                if "sk-ABCDEFGHIJKLMNOPQRSTUVWX" in handle.read():
                    failures.append("file render leaked a secret")

    if failures:
        for failure in failures:
            print(f"[self-test] FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"[self-test] OK: {stats['lines_total']} lines, {stats['invalid']} invalid, {sum(stats['tool_calls'].values())} tool calls")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把 Claude Code stream-json 渲染为人读日志（容错，不因坏行中断）"
    )
    parser.add_argument("--input", "-i", default="-", help="输入 raw.jsonl，'-' 表示 stdin（默认）")
    parser.add_argument("--output", "-o", default="-", help="输出渲染日志，'-' 表示 stdout（默认）")
    parser.add_argument("--no-redact", action="store_true", help="关闭密钥模式脱敏")
    parser.add_argument("--max-text", type=int, default=DEFAULT_MAX_TEXT, help="单条文本最大字符数")
    parser.add_argument("--max-result", type=int, default=DEFAULT_MAX_RESULT, help="单条工具结果最大字符数")
    parser.add_argument("--max-raw", type=int, default=DEFAULT_MAX_RAW, help="非 JSON/坏行最大字符数")
    parser.add_argument("--include-unknown", action="store_true", help="输出未知事件类型（默认跳过）")
    parser.add_argument("--quiet", "-q", action="store_true", help="不打印统计到 stderr")
    parser.add_argument("--self-test", action="store_true", help="运行内置自测并退出")
    parser.add_argument("--version", action="version", version=f"render_claude_log {SCHEMA_VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.max_text < 0 or args.max_result < 0 or args.max_raw < 0:
        parser.error("--max-* 必须是非负整数")
    return run_render(args)


if __name__ == "__main__":
    sys.exit(main())