#!/usr/bin/env python3
"""Native memory safety candidate scan for NPD, MLK and UAF."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

SKILL = "memory-safety-analyzer"
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "third_party",
    "3rdparty",
    "vendor",
    "dist",
    "build",
    "tests",
    "test",
    "examples",
    "example",
    "docs",
    "benchmarks",
    "benchmark",
}
CODE_SUFFIXES = {
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cxx",
    ".hpp",
    ".hh",
    ".cu",
    ".cuh",
    ".rs",
    ".go",
    ".py",
    ".pyx",
    ".pxd",
}
LANGUAGE_BY_SUFFIX = {
    ".c": "c/c++",
    ".h": "c/c++",
    ".cc": "c/c++",
    ".cpp": "c/c++",
    ".cxx": "c/c++",
    ".hpp": "c/c++",
    ".hh": "c/c++",
    ".cu": "cuda",
    ".cuh": "cuda",
    ".rs": "rust",
    ".go": "go",
    ".py": "python",
    ".pyx": "python",
    ".pxd": "python",
}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LOOKAHEAD = 80
USE_SINKS = (
    "strlen",
    "strcpy",
    "strncpy",
    "strcat",
    "strcmp",
    "memcpy",
    "memmove",
    "memset",
    "printf",
    "fprintf",
    "sprintf",
    "snprintf",
    "fread",
    "fwrite",
    "read",
    "write",
    "send",
    "recv",
    "cudaMemcpy",
    "cudaMemcpyAsync",
    "cudaLaunchKernel",
    "PyObject_",
    "C.",
)
RELEASE_PATTERNS = (
    ("free", re.compile(r"\bfree\s*\(\s*([A-Za-z_]\w*)\s*\)")),
    ("delete", re.compile(r"\bdelete(?:\s*\[\s*\])?\s+([A-Za-z_]\w*)\s*;")),
    ("fclose", re.compile(r"\bfclose\s*\(\s*([A-Za-z_]\w*)\s*\)")),
    ("close", re.compile(r"\bclose\s*\(\s*([A-Za-z_]\w*)\s*\)")),
    ("cudaFree", re.compile(r"\bcudaFree\s*\(\s*([A-Za-z_]\w*)\s*\)")),
    ("Py_DECREF", re.compile(r"\b(?:Py_DECREF|Py_XDECREF)\s*\(\s*([A-Za-z_]\w*)\s*\)")),
    ("C.free", re.compile(r"\bC\.free\s*\(\s*([A-Za-z_]\w*)\s*\)")),
    ("drop", re.compile(r"\bdrop\s*\(\s*([A-Za-z_]\w*)\s*\)")),
)
NULL_CHECK_RE = re.compile(
    r"if\s*\(\s*(?:!\s*{v}|{v}\s*==\s*(?:NULL|nullptr|0)|{v}\s*!=\s*(?:NULL|nullptr|0)|{v}\s*\)|"
    r"{v}\s+is\s+None|not\s+{v}|let\s+Some\(\s*{v}\s*\)|match\s+{v}|"
    r"assert\s*\(\s*{v}|BUG_ON\s*\(\s*!\s*{v})"
)


def load_rules() -> List[Dict[str, Any]]:
    path = Path(__file__).with_name("patterns") / "memory.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rules = data.get("rules")
    return rules if isinstance(rules, list) else []


def language_for(path: Path) -> Optional[str]:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix.lower() in CODE_SUFFIXES and root.stat().st_size <= MAX_FILE_BYTES:
            yield root
        return
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if (
                path.is_file()
                and path.suffix.lower() in CODE_SUFFIXES
                and path.stat().st_size <= MAX_FILE_BYTES
            ):
                yield path
        except OSError:
            continue


def read_lines(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def line_text(lines: Sequence[str], index: int) -> str:
    if 0 <= index < len(lines):
        return lines[index].strip()[:400]
    return ""


def find_null_check(lines: Sequence[str], index: int, var: str) -> bool:
    pattern = re.compile(NULL_CHECK_RE.pattern.format(v=re.escape(var)))
    for offset in range(index, min(index + 5, len(lines))):
        if pattern.search(lines[offset]):
            return True
    return False


def find_release_before(lines: Sequence[str], start: int, end: int, var: str) -> bool:
    for index in range(start, min(end, len(lines))):
        for _, pattern in RELEASE_PATTERNS:
            match = pattern.search(lines[index])
            if match and match.group(1) == var:
                return True
    return False


def find_deref_near(lines: Sequence[str], index: int, var: str, limit: int = 12) -> bool:
    escaped = re.escape(var)
    deref = re.compile(rf"{escaped}\s*(?:->|\[|\.)|\*\s*{escaped}\b")
    sink = re.compile(rf"\b(?:{'|'.join(re.escape(item) for item in USE_SINKS)})\s*\(")
    for offset in range(index + 1, min(index + limit, len(lines))):
        text = lines[offset]
        if deref.search(text):
            return True
        if sink.search(text) and re.search(rf"\b{escaped}\b", text):
            return True
    return False


def find_assignment_before(lines: Sequence[str], start: int, end: int, var: str) -> bool:
    escaped = re.escape(var)
    assignment = re.compile(
        rf"(?:->\w+\s*=\s*{escaped}\b|\.\w+\s*=\s*{escaped}\b|"
        rf"\b\w+\s*=\s*{escaped}\s*;|\breturn\s+{escaped}\b)"
    )
    for index in range(start, min(end, len(lines))):
        if assignment.search(lines[index]):
            return True
    return False


CONTROL_FLOW_RE = re.compile(r"^\s*(?:if|for|while|switch|else|do|catch|try)\b")


def find_scope_end(lines: Sequence[str], start: int) -> int:
    begin = start
    for index in range(start, -1, -1):
        text = lines[index]
        if CONTROL_FLOW_RE.search(text):
            continue
        if "{" in text and ("(" in text or text.strip().endswith("{")):
            begin = index
            break
    depth = 0
    opened = False
    for index in range(begin, len(lines)):
        text = lines[index]
        depth += text.count("{")
        if "{" in text:
            opened = True
        depth -= text.count("}")
        if opened and depth <= 0:
            return index + 1
    return min(start + MAX_LOOKAHEAD, len(lines))


def is_null_guard_return(lines: Sequence[str], index: int, var: str) -> bool:
    pattern = re.compile(NULL_CHECK_RE.pattern.format(v=re.escape(var)))
    if 0 <= index < len(lines) and pattern.search(lines[index]):
        return True
    if re.search(r"\bif\b", lines[index]):
        return False
    return index > 0 and bool(pattern.search(lines[index - 1]))


def add_candidate(
    candidates: List[Dict[str, Any]],
    *,
    rule: str,
    kind: str,
    severity: str,
    confidence: str,
    language: str,
    path: Path,
    line: int,
    evidence: str,
    message: str,
    why: str,
    cwe: str,
    follow_up: str,
) -> None:
    candidates.append(
        {
            "skill": SKILL,
            "rule": rule,
            "kind": kind,
            "severity": severity,
            "confidence": confidence,
            "language": language,
            "file": str(path),
            "line": line,
            "evidence": evidence,
            "message": message,
            "why": why,
            "cwe": cwe,
            "follow_up": follow_up,
        }
    )


def scan_release_use(
    lines: Sequence[str],
    release_index: int,
    var: str,
    language: str,
    path: Path,
    candidates: List[Dict[str, Any]],
) -> None:
    end = min(find_scope_end(lines, release_index), release_index + MAX_LOOKAHEAD)
    escaped = re.escape(var)
    reassigned = re.compile(rf"^\s*{escaped}\s*=")
    use_pattern = re.compile(
        rf"(?:{escaped}\s*->|{escaped}\s*\[|\*\s*{escaped}\b|{escaped}\s*\.)"
    )
    call_pattern = re.compile(rf"\b(?:{'|'.join(re.escape(item) for item in USE_SINKS)})\s*\(")
    for index in range(release_index + 1, end):
        text = lines[index]
        if reassigned.search(text):
            return
        for _, pattern in RELEASE_PATTERNS:
            match = pattern.search(text)
            if match and match.group(1) == var:
                add_candidate(
                    candidates,
                    rule="MEM-DOUBLE-FREE",
                    kind="double_free",
                    severity="high",
                    confidence="medium",
                    language=language,
                    path=path,
                    line=index + 1,
                    evidence=f"L{release_index + 1} 释放 {var}；L{index + 1} 再次释放",
                    message="同一对象在未重新赋值前被再次释放",
                    why="重复释放会破坏分配器状态，可能导致内存损坏或拒绝服务",
                    cwe="CWE-415",
                    follow_up="确认两条释放路径能否在同一请求或错误分支中先后到达",
                )
                return
        if use_pattern.search(text) or (
            call_pattern.search(text) and re.search(rf"\b{escaped}\b", text)
        ):
            add_candidate(
                candidates,
                rule="MEM-UAF-USE",
                kind="uaf",
                severity="high",
                confidence="medium",
                language=language,
                path=path,
                line=index + 1,
                evidence=f"L{release_index + 1} 释放 {var}；L{index + 1} 继续使用",
                message="对象释放后仍在同一作用域或相邻路径中被使用",
                why="释放后继续访问会读取已回收内存，可能导致内存损坏、信息泄露或拒绝服务",
                cwe="CWE-416",
                follow_up="确认释放后的使用路径可由外部输入、错误分支或并发时序到达",
            )
            return


def scan_allocation_leak(
    lines: Sequence[str],
    alloc_index: int,
    var: str,
    language: str,
    path: Path,
    candidates: List[Dict[str, Any]],
) -> None:
    end = min(find_scope_end(lines, alloc_index), alloc_index + MAX_LOOKAHEAD)
    for index in range(alloc_index + 1, end):
        text = lines[index]
        if re.search(r"\breturn\b", text) or re.search(r"\bgoto\b", text):
            if is_null_guard_return(lines, index, var):
                continue
            if find_release_before(lines, alloc_index + 1, index, var):
                return
            if find_assignment_before(lines, alloc_index + 1, index, var):
                return
            if re.search(rf"\breturn\b[^;]*\b{re.escape(var)}\b", text):
                return
            add_candidate(
                candidates,
                rule="MEM-MLK-EARLY-EXIT",
                kind="mlk",
                severity="medium",
                confidence="low",
                language=language,
                path=path,
                line=index + 1,
                evidence=f"L{alloc_index + 1} 分配 {var}；L{index + 1} 提前退出且未释放",
                message="分配后存在提前退出路径，未看到对应释放",
                why="错误分支或参数校验失败时提前返回，容易漏掉释放或引用计数回滚",
                cwe="CWE-401",
                follow_up=(
                    "确认该提前退出路径可由外部输入触发，"
                    "并且该对象没有被交给其他所有者"
                ),
            )
            return


def scan_file(
    path: Path,
    rules: Sequence[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
) -> None:
    language = language_for(path)
    if not language:
        return
    lines = read_lines(path)
    if not lines:
        return

    for rule in rules:
        if language not in (rule.get("languages") or []):
            continue
        try:
            pattern = re.compile(str(rule.get("pattern", "")))
        except re.error:
            continue
        if rule.get("id") == "MEM-NPD-ALLOC":
            for index, text in enumerate(lines):
                for match in pattern.finditer(text):
                    var = match.group(1)
                    if not find_null_check(
                        lines, index, var
                    ) and find_deref_near(lines, index, var):
                        add_candidate(
                            candidates,
                            rule=str(rule.get("id", "MEM-NPD-ALLOC")),
                            kind=str(rule.get("kind", "npd")),
                            severity=str(rule.get("severity", "medium")),
                            confidence=str(rule.get("confidence", "low")),
                            language=language,
                            path=path,
                            line=index + 1,
                            evidence=line_text(lines, index),
                            message=str(rule.get("message", "")),
                            why=str(rule.get("why", "")),
                            cwe=str(rule.get("cwe", "CWE-476")),
                            follow_up="确认分配失败路径可到达，并且后续解引用前没有有效空值检查",
                        )
                    scan_allocation_leak(lines, index, var, language, path, candidates)
            continue
        for index, text in enumerate(lines):
            for match in pattern.finditer(text):
                var = match.group(1) if match.groups() else ""
                if rule.get("require_no_null_check") and var:
                    if find_null_check(lines, index, var) or not find_deref_near(lines, index, var):
                        continue
                if rule.get("kind") == "release" and var:
                    scan_release_use(lines, index, var, language, path, candidates)
                    continue
                add_candidate(
                    candidates,
                    rule=str(rule.get("id", "MEM-UNKNOWN")),
                    kind=str(rule.get("kind", "unknown")),
                    severity=str(rule.get("severity", "low")),
                    confidence=str(rule.get("confidence", "low")),
                    language=language,
                    path=path,
                    line=index + 1,
                    evidence=line_text(lines, index),
                    message=str(rule.get("message", "")),
                    why=str(rule.get("why", "")),
                    cwe=str(rule.get("cwe", "")),
                    follow_up="回到调用链核对来源、所有权和防护条件，不把单行命中当作漏洞结论",
                )
                break


def scan_root(root: Path) -> Dict[str, Any]:
    rules = load_rules()
    candidates: List[Dict[str, Any]] = []
    files = list(iter_files(root))
    for path in files:
        scan_file(path, rules, candidates)
    unique: List[Dict[str, Any]] = []
    seen = set()
    for item in candidates:
        key = (item["file"], item["line"], item["rule"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    unique.sort(key=lambda item: (order.get(item["severity"], 4), item["file"], item["line"]))
    by_kind: Dict[str, int] = {}
    for item in unique:
        by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
    return {
        "skill": SKILL,
        "root": str(root),
        "summary": {
            "files_scanned": len(files),
            "candidates": len(unique),
            "by_kind": by_kind,
        },
        "candidates": unique,
    }


def format_markdown(result: Dict[str, Any]) -> str:
    lines = [
        "# 原生内存安全候选",
        "",
        f"- 扫描根目录：`{result['root']}`",
        f"- 文件数量：{result['summary']['files_scanned']}",
        f"- 候选数量：{result['summary']['candidates']}",
        "",
        "| 严重度 | 类型 | 文件:行号 | 证据 | 待核实 |",
        "|---|---|---|---|---|",
    ]
    for item in result["candidates"]:
        lines.append(
            "| {severity} | {kind} | `{file}:{line}` | {evidence} | {follow_up} |".format(
                severity=item["severity"],
                kind=item["kind"],
                file=item["file"],
                line=item["line"],
                evidence=item["evidence"].replace("|", "\\|"),
                follow_up=item["follow_up"].replace("|", "\\|"),
            )
        )
    return "\n".join(lines)


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="memory-safety-selftest-") as temp:
        root = Path(temp)
        (root / "uaf.c").write_text(
            "#include <stdlib.h>\n"
            "void handle(char *input) {\n"
            "    char *buffer = malloc(16);\n"
            "    if (!buffer) { return; }\n"
            "    free(buffer);\n"
            "    buffer[0] = input[0];\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "leak.c").write_text(
            "#include <stdlib.h>\n"
            "int load(int fail) {\n"
            "    char *buffer = malloc(16);\n"
            "    if (!buffer) { return -1; }\n"
            "    if (fail) { return -1; }\n"
            "    free(buffer);\n"
            "    return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "npd.c").write_text(
            "#include <stdlib.h>\n"
            "void use(void) {\n"
            "    char *buffer = malloc(16);\n"
            "    buffer[0] = 0;\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "raw.rs").write_text(
            "unsafe fn take(ptr: *mut u8) {\n"
            "    let value = ptr::read(ptr);\n"
            "    drop(value);\n"
            "}\n",
            encoding="utf-8",
        )
        result = scan_root(root)
        kinds = result["summary"]["by_kind"]
        failures = []
        if kinds.get("uaf", 0) < 1:
            failures.append("未发现释放后使用候选")
        if kinds.get("mlk", 0) < 1:
            failures.append("未发现内存泄漏候选")
        if kinds.get("npd", 0) < 1:
            failures.append("未发现空指针解引用候选")
        if failures:
            print(
                json.dumps(
                    {"ok": False, "failures": failures, "result": result},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        print(json.dumps({"ok": True, "summary": result["summary"]}, ensure_ascii=False, indent=2))
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="原生内存安全候选扫描")
    parser.add_argument("paths", nargs="*", default=["."], help="要扫描的项目路径")
    parser.add_argument("--format", choices=("json", "md"), default="json", help="输出格式")
    parser.add_argument("--output", "-o", default="", help="写入文件")
    parser.add_argument("--self-test", action="store_true", help="运行内置自检")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    results = []
    for raw in args.paths:
        path = Path(raw).resolve()
        if not path.exists():
            print(f"路径不存在: {path}", file=sys.stderr)
            return 2
        results.append(scan_root(path))
    payload = results[0] if len(results) == 1 else {"skill": SKILL, "results": results}

    if args.format == "md":
        if len(results) == 1:
            text = format_markdown(results[0])
        else:
            text = "\n\n".join(format_markdown(item) for item in results)
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        try:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"写入失败: {exc}", file=sys.stderr)
            return 2
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
