#!/usr/bin/env python3
"""审计覆盖记录的确定性检查；不调用模型，不修改审计结论。"""

import fcntl
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER_SCRIPT = ROOT / "scripts" / "audit" / "coverage_ledger.py"
COUNTER_NAME = ".coverage-stop-count"
PAUSE_NAME = ".coverage-paused"


def load_module():
    spec = importlib.util.spec_from_file_location("coverage_ledger", LEDGER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_root(payload):
    candidates = [os.environ.get("CLAUDE_PROJECT_DIR"), payload.get("cwd"), os.getcwd()]
    for candidate in candidates:
        if candidate and (Path(candidate) / ".workspace").is_dir():
            return Path(candidate)
    for candidate in candidates:
        if candidate:
            return Path(candidate)
    return Path.cwd()


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _ledger_value(ledger, key):
    return ledger.get(key, "unknown") if isinstance(ledger, dict) else "unknown"


def progress(root, errors, ledger=None):
    entries = ledger.get("entries", []) if isinstance(ledger, dict) else []
    lines = [
        "# 审计覆盖恢复进度",
        "",
        f"- 更新时间：{datetime.now(timezone.utc).isoformat()}",
        f"- 项目：{_ledger_value(ledger, 'project')}",
        f"- 源码版本：{_ledger_value(ledger, 'source_version')}",
    ]
    if errors:
        lines += ["", "## 待修正", ""] + [f"- {item}" for item in errors]
    if entries:
        lines += ["", "## 条目", ""]
        for entry in entries[:30]:
            lines.append(f"- `{entry.get('id')}` {entry.get('status')}：{entry.get('next_action')}")
    write_atomic(root / ".workspace" / "findings" / "coverage-progress.md", "\n".join(lines) + "\n")


def pre_tool_use(payload, root):
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or "")
    if not file_path.endswith("coverage-ledger.json"):
        return 0
    content = tool_input.get("content")
    if not isinstance(content, str):
        return 0
    try:
        ledger = json.loads(content)
    except ValueError as exc:
        print(f"覆盖记录不是有效 JSON：{exc}", file=sys.stderr)
        return 2
    module = load_module()
    errors = module.validate_ledger(ledger)
    if errors:
        print("覆盖记录缺少必要字段，修正后再写入：", file=sys.stderr)
        for item in errors[:20]:
            print(f"- {item}", file=sys.stderr)
        return 2
    return 0


def pre_compact(payload, root):
    ledger_path = root / ".workspace" / "findings" / "coverage-ledger.json"
    if not ledger_path.is_file():
        return 0
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        errors = load_module().validate_ledger(ledger)
    except (OSError, ValueError) as exc:
        ledger = None
        errors = [f"无法读取覆盖记录：{exc}"]
    progress(root, errors, ledger)
    return 0


def stop(payload, root):
    ledger_path = root / ".workspace" / "findings" / "coverage-ledger.json"
    if not ledger_path.is_file():
        return 0
    findings = root / ".workspace" / "findings"
    findings.mkdir(parents=True, exist_ok=True)
    lock_path = findings / ".coverage-guard.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        if (findings / PAUSE_NAME).exists():
            progress(root, ["已记录暂停标记，不再阻止结束"], None)
            return 0
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            errors = load_module().validate_ledger(ledger)
        except (OSError, ValueError) as exc:
            ledger = None
            errors = [f"无法读取覆盖记录：{exc}"]
        if not errors:
            (findings / COUNTER_NAME).unlink(missing_ok=True)
            return 0
        progress(root, errors, ledger)
        counter = findings / COUNTER_NAME
        count = 0
        try:
            count = int(counter.read_text().strip())
        except (OSError, ValueError):
            pass
        counter.write_text(str(count + 1), encoding="utf-8")
        print("覆盖记录尚未达到可交付状态：", file=sys.stderr)
        for item in errors[:20]:
            print(f"- {item}", file=sys.stderr)
        print(f"进度已保存到 {root / '.workspace/findings/coverage-progress.md'}", file=sys.stderr)
        if count >= 1:
            print("已连续提示一次；本轮允许结束，保留恢复进度和未决条目。", file=sys.stderr)
            return 0
        print("请补齐字段、证据、缺失证据或下一步动作后再次结束。", file=sys.stderr)
        return 2


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    root = project_root(payload)
    event = payload.get("hook_event_name") or ""
    if event == "PreToolUse" or ("tool_name" in payload and "tool_input" in payload):
        return pre_tool_use(payload, root)
    if event == "PreCompact":
        return pre_compact(payload, root)
    return stop(payload, root)


if __name__ == "__main__":
    raise SystemExit(main())
