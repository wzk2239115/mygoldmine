#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CJK = re.compile(r"[\u3400-\u9fff]")
INLINE_CODE = re.compile(r"`[^`]*`")
TECHNICAL_NOTE = re.compile(r"[（(][A-Za-z][A-Za-z0-9_./+ -]*[）)]")
URL = re.compile(r"https?://\S+")
PATH_VALUE = re.compile(r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+\b")
FILE_LINE = re.compile(r"\b[A-Za-z0-9_.-]+:\d+\b")
ENGLISH_PHRASE = re.compile(
    r"\b[A-Za-z][A-Za-z0-9_-]*(?:[ +][A-Za-z][A-Za-z0-9_-]*)+\b"
)
EXCLUDED_DIRS = {
    ".cache",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".workspace",
    "backups",
    "dist",
    "env",
    "node_modules",
    "runs",
    "smartbugs-curated",
    "targets",
    "third_party",
}
SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
CODE_SUFFIXES = {".py", ".sh"}
BANNED_TERMS = {
    "闭环已通": "只读建议已跑通；尚未完成验证、发布和结果回写",
    "墙钟": "实际运行时间",
    "断点续跑": "恢复未完成项目",
    "挖掘工厂": "批量审计",
    "挖矿": "批量审计",
    "矿场": "批量审计",
    "质量门": "完整性检查",
    "门禁": "通过条件或发布检查",
    "台账": "发现记录表",
    "影子模式": "只读建议模式",
    "影子链路": "只读建议模式",
    "飞轮": "学习循环或流程步骤",
    "回流": "结果回写",
}
MIXED_TERMS = tuple(
    sorted(
        {
            "agentic",
            "approved",
            "artifact",
            "artifacts",
            "attempt",
            "baseline",
            "blocked",
            "candidate_only",
            "checksum",
            "confirmed",
            "deadline",
            "editable surface",
            "finding",
            "findings",
            "flags",
            "flips",
            "gate",
            "harness",
            "holdout",
            "idle",
            "inconclusive",
            "insufficient",
            "judge",
            "lab",
            "lane",
            "matched-action",
            "mitigations",
            "mutation",
            "occurrence",
            "pending",
            "priority",
            "promote",
            "propensity",
            "proposal",
            "provenance",
            "raw",
            "recovery",
            "rejected",
            "replay",
            "review",
            "reviewReady",
            "run",
            "schema",
            "semantic",
            "setup",
            "shadow",
            "sink",
            "static",
            "surface",
            "tool",
            "trusted",
            "unknown",
            "uplift",
            "utility",
            "validated",
            "verify",
            "worker",
        },
        key=len,
        reverse=True,
    )
)
MIXED_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(term) for term in MIXED_TERMS) + r")(?![A-Za-z0-9_])"
)


def excluded(relative: Path) -> bool:
    if relative.parts[:2] == (".agent", "history"):
        return True
    return any(part in EXCLUDED_DIRS for part in relative.parts)


def discover_files(root: Path) -> dict[Path, str]:
    discovered: dict[Path, str] = {}
    for directory, dirnames, filenames in os.walk(root):
        current = Path(directory)
        dirnames[:] = [
            name for name in dirnames if not excluded((current / name).relative_to(root))
        ]
        for filename in filenames:
            path = current / filename
            relative = path.relative_to(root)
            if excluded(relative) or relative == Path(".agent/LOG.md"):
                continue
            suffix = path.suffix
            scope = None
            if suffix == ".md":
                if relative.parts[0] in {".agent", ".claude"}:
                    scope = "agent-instructions"
                else:
                    scope = "documentation"
            elif (
                relative.parts[0] == "ui"
                and len(relative.parts) > 1
                and relative.parts[1] == "src"
            ):
                if suffix in SOURCE_SUFFIXES:
                    scope = "interface"
            elif filename == "run.sh" and relative.parent == Path("."):
                scope = "command-and-report"
            elif relative.parts[0] in {"scripts", "audit_rsi", "rsi_version", "integrations"}:
                if suffix in CODE_SUFFIXES or (suffix == ".txt" and "prompts" in relative.parts):
                    scope = "command-and-report"
            elif relative.parts[0] == ".claude" and suffix in CODE_SUFFIXES:
                scope = "command-and-report"
            if scope:
                discovered[path] = scope
    return discovered


def visible_text(line: str, markdown: bool) -> str:
    value = line
    if markdown:
        value = INLINE_CODE.sub("", value)
    value = TECHNICAL_NOTE.sub("", value)
    value = URL.sub("", value)
    value = PATH_VALUE.sub("", value)
    value = FILE_LINE.sub("", value)
    return value


def line_findings(
    relative: str,
    number: int,
    original: str,
    visible: str,
) -> list[dict[str, str | int]]:
    findings = []
    for term, replacement in BANNED_TERMS.items():
        if term in visible:
            findings.append(
                {
                    "path": relative,
                    "line": number,
                    "kind": "banned-term",
                    "term": term,
                    "replacement": replacement,
                    "text": original.strip(),
                }
            )
    mixed = list(MIXED_PATTERN.finditer(visible))
    for match in mixed:
        findings.append(
            {
                "path": relative,
                "line": number,
                "kind": "mixed-language",
                "term": match.group(1),
                "replacement": "先用中文解释，技术对应放在首次括号或行内代码中",
                "text": original.strip(),
            }
        )
    if not mixed:
        for match in ENGLISH_PHRASE.finditer(visible):
            findings.append(
                {
                    "path": relative,
                    "line": number,
                    "kind": "english-phrase",
                    "term": match.group(0),
                    "replacement": "检查是否可用完整中文表达",
                    "text": original.strip(),
                }
            )
    return findings


def fingerprint(finding: dict[str, str | int]) -> str:
    value = json.dumps(
        [finding["path"], finding["kind"], finding["term"], finding["text"]],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def audit(root: Path) -> dict:
    discovered = discover_files(root)
    scopes: dict[str, dict[str, int]] = {}
    findings = []
    errors = []
    scanned = 0
    for path, scope in sorted(discovered.items()):
        relative_path = path.relative_to(root)
        relative = relative_path.as_posix()
        summary = scopes.setdefault(
            scope,
            {"discovered": 0, "scanned": 0, "cjk_lines": 0, "findings": 0},
        )
        summary["discovered"] += 1
        try:
            content = path.read_bytes()
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("gb18030")
            lines = text.splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append({"path": relative, "error": str(exc)})
            continue
        scanned += 1
        summary["scanned"] += 1
        markdown = path.suffix == ".md"
        fenced = False
        for number, original in enumerate(lines, 1):
            stripped = original.lstrip()
            if markdown and (stripped.startswith("```") or stripped.startswith("~~~")):
                fenced = not fenced
                continue
            if fenced:
                continue
            visible = visible_text(original, markdown)
            if not CJK.search(visible):
                continue
            summary["cjk_lines"] += 1
            current = line_findings(relative, number, original, visible)
            summary["findings"] += len(current)
            findings.extend(current)
    total_cjk_lines = sum(item["cjk_lines"] for item in scopes.values())
    return {
        "root": str(root),
        "coverage": {
            "discovered_files": len(discovered),
            "scanned_files": scanned,
            "percent": round(100 * scanned / len(discovered), 2) if discovered else 100.0,
            "cjk_lines": total_cjk_lines,
            "errors": errors,
        },
        "scopes": scopes,
        "finding_count": len(findings),
        "findings": findings,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_text(report: dict, limit: int, new_count: int | None) -> None:
    coverage = report["coverage"]
    print(
        f"表达检查覆盖率：{coverage['percent']:.2f}% "
        f"({coverage['scanned_files']}/{coverage['discovered_files']} 个文件，"
        f"{coverage['cjk_lines']} 行中文内容)"
    )
    unsupported = coverage.get("unsupported_files", [])
    if unsupported:
        print(f"无法读取、未纳入扫描的文件：{len(unsupported)} 个")
    for scope, summary in sorted(report["scopes"].items()):
        print(
            f"  {scope}: {summary['scanned']}/{summary['discovered']} 个文件，"
            f"{summary['cjk_lines']} 行，{summary['findings']} 条候选"
        )
    print(f"候选问题：{report['finding_count']} 条")
    if new_count is not None:
        print(f"相对基线新增：{new_count} 条")
    shown = report["findings"] if limit == 0 else report["findings"][:limit]
    for finding in shown:
        print(
            f"{finding['path']}:{finding['line']}: "
            f"[{finding['kind']}: {finding['term']}] {finding['text']}"
        )
    remaining = len(report["findings"]) - len(shown)
    if remaining:
        print(
            f"另有 {remaining} 条未显示；使用 --limit 0 查看全部，"
            "或 --json-output 保存完整结果。"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="检查项目中文文案的覆盖率和中英混写候选")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--fail-on-findings", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--write-baseline", type=Path)
    parser.add_argument("--allow-unreadable", action="append", default=[])
    args = parser.parse_args()
    root = args.root.resolve()
    report = audit(root)
    allowed_unreadable = set(args.allow_unreadable)
    errors = report["coverage"]["errors"]
    report["coverage"]["unsupported_files"] = [
        item for item in errors if item["path"] in allowed_unreadable
    ]
    report["coverage"]["errors"] = [
        item for item in errors if item["path"] not in allowed_unreadable
    ]
    fingerprints = Counter(fingerprint(item) for item in report["findings"])
    if args.write_baseline:
        write_json(
            args.write_baseline,
            {"version": 1, "fingerprints": sorted(fingerprints.elements())},
        )
    new_count = None
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        old = Counter(baseline.get("fingerprints", []))
        new_count = sum((fingerprints - old).values())
    if args.json_output:
        write_json(args.json_output, report)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report, args.limit, new_count)
    if report["coverage"]["errors"]:
        return 2
    if new_count:
        return 1
    if args.fail_on_findings and report["finding_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
