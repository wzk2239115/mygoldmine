#!/usr/bin/env python3
"""Fast static scan for model loading trust boundaries."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tempfile
import warnings
from pathlib import Path

SKILL = "model-loading-analyzer"
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "site-packages",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}
CODE_SUFFIXES = {".py", ".pyi", ".json", ".yaml", ".yml", ".toml"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
MAX_FILE_BYTES = 2 * 1024 * 1024


def load_rules() -> list[dict]:
    path = Path(__file__).with_name("patterns") / "transformers.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rules = data.get("rules")
    return rules if isinstance(rules, list) else []


def iter_files(root: Path):
    if root.is_file():
        if root.stat().st_size <= MAX_FILE_BYTES:
            yield root
        return
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                yield path
        except OSError:
            continue


def call_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        return call_name(node.func)
    return ".".join(reversed(parts))


def keyword(node: ast.Call, name: str):
    for item in node.keywords:
        if item.arg == name:
            return item.value
    return None


def is_const(node, value) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def line_text(lines: list[str], lineno: int) -> str:
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:300]
    return ""


def add_finding(findings: list[dict], *, rule: str, severity: str, confidence: str,
                path: Path, line: int, evidence: str, message: str, why: str, fix: str) -> None:
    findings.append({
        "skill": SKILL,
        "rule": rule,
        "severity": severity,
        "confidence": confidence,
        "file": str(path),
        "line": line,
        "evidence": evidence,
        "message": message,
        "why": why,
        "fix": fix,
    })


def scan_python(path: Path, text: str, findings: list[dict]) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text, filename=str(path))
    except (SyntaxError, ValueError):
        return
    lines = text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node.func)
        lineno = getattr(node, "lineno", 0)
        if name.endswith("from_pretrained") or name.endswith("from_config"):
            trust = keyword(node, "trust_remote_code")
            if trust is not None and is_const(trust, True):
                line = getattr(trust, "lineno", lineno)
                add_finding(
                    findings,
                    rule="ML-REMOTE-CODE",
                    severity="medium",
                    confidence="medium",
                    path=path,
                    line=line,
                    evidence=line_text(lines, line),
                    message=f"{name}(trust_remote_code=True)；若模型源不可信则为远程代码执行",
                    why="模型仓库内容会被当作 Python 代码导入执行，需回溯模型 ID 来源",
                    fix="默认 trust_remote_code=False；固定 revision；使用受信模型白名单",
                )
            elif trust is not None and not is_const(trust, False):
                line = getattr(trust, "lineno", lineno)
                add_finding(
                    findings,
                    rule="ML-REMOTE-CODE-DYNAMIC",
                    severity="low",
                    confidence="low",
                    path=path,
                    line=line,
                    evidence=line_text(lines, line),
                    message=f"{name} 的 trust_remote_code 来自变量，需回溯是否可由请求控制",
                    why="动态开关可能被上层配置或请求打开",
                    fix="将开关固定为常量并按模型来源决定",
                )
        if "get_class_from_dynamic_module" in name:
            add_finding(
                findings,
                rule="ML-DYNAMIC-MODULE",
                severity="medium",
                confidence="medium",
                path=path,
                line=lineno,
                evidence=line_text(lines, lineno),
                message=f"{name} 从模型仓库动态加载模块/类",
                why="动态模块会执行仓库内代码",
                fix="移除动态加载或对仓库/实现使用允许列表",
            )
        if name == "torch.load" or name.endswith(".torch.load"):
            weights = keyword(node, "weights_only")
            if weights is not None and is_const(weights, True):
                continue
            line = getattr(weights, "lineno", lineno) if weights is not None else lineno
            unsafe = weights is not None and is_const(weights, False)
            add_finding(
                findings,
                rule="ML-TORCH-LOAD-UNSAFE" if unsafe else "ML-TORCH-LOAD-DEFAULT",
                severity="high" if unsafe else "medium",
                confidence="high" if unsafe else "medium",
                path=path,
                line=line,
                evidence=line_text(lines, line),
                message="torch.load(weights_only=False)" if unsafe else "torch.load 未显式设置 weights_only=True",
                why="torch.load 使用 pickle，加载不可信权重可导致任意代码执行",
                fix="改用 safetensors；必须 torch.load 时强制 weights_only=True",
            )
        if name == "numpy.load":
            allow = keyword(node, "allow_pickle")
            if allow is not None and is_const(allow, True):
                add_finding(
                    findings,
                    rule="ML-NUMPY-PICKLE",
                    severity="medium",
                    confidence="high",
                    path=path,
                    line=getattr(allow, "lineno", lineno),
                    evidence=line_text(lines, getattr(allow, "lineno", lineno)),
                    message="numpy.load(allow_pickle=True) 会反序列化 pickle",
                    why="与 torch.load 相同，文件可被替换时导致 RCE",
                    fix="保持 allow_pickle=False，或改用安全数组格式",
                )


def scan_text_rules(path: Path, text: str, rules: list[dict], findings: list[dict]) -> None:
    lines = text.splitlines()
    for rule in rules:
        pattern = rule.get("regex")
        if not isinstance(pattern, str):
            continue
        try:
            compiled = re.compile(pattern, re.MULTILINE)
        except re.error:
            continue
        for match in compiled.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            add_finding(
                findings,
                rule=str(rule.get("id", "ML-RULE")),
                severity=str(rule.get("severity", "medium")),
                confidence=str(rule.get("confidence", "medium")),
                path=path,
                line=lineno,
                evidence=line_text(lines, lineno),
                message=str(rule.get("message", "模型加载风险")),
                why="规则命中模型加载链路的危险模式",
                fix=str(rule.get("fix", "见 SKILL.md 修复建议")),
            )


def scan_paths(roots: list[Path], rules: list[dict]) -> tuple[list[dict], int]:
    findings: list[dict] = []
    files = 0
    for root in roots:
        for path in iter_files(root):
            if path.suffix.lower() not in CODE_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files += 1
            if path.suffix.lower() in {".py", ".pyi"}:
                scan_python(path, text, findings)
            scan_text_rules(path, text, rules, findings)
    unique: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for finding in findings:
        key = (finding["file"], finding["line"], finding["rule"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique, files


def summarize(findings: list[dict]) -> dict:
    summary = {"high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in findings:
        summary[finding["severity"]] = summary.get(finding["severity"], 0) + 1
    return summary


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="ml-self-test-") as tmp:
        root = Path(tmp)
        (root / "bad.py").write_text(
            "from transformers import AutoModel\n"
            "AutoModel.from_pretrained('evil/model', trust_remote_code=True)\n"
            "torch.load('weights.pt', map_location='cpu')\n"
            "torch.load('safe.pt', weights_only=True)\n"
            "get_class_from_dynamic_module('mod', 'repo')\n"
            "AutoModel.from_config(cfg, trust_remote_code=False)\n",
            encoding="utf-8",
        )
        (root / "config.json").write_text('{"auto_map": {"AutoConfig": "x.Y"}}\n', encoding="utf-8")
        (root / "safe.py").write_text(
            "from transformers import AutoModel\n"
            "AutoModel.from_pretrained('trusted/model', trust_remote_code=False)\n"
            "torch.load('safe.pt', weights_only=True)\n",
            encoding="utf-8",
        )
        (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
        findings, files = scan_paths([root], load_rules())
        rules = {finding["rule"] for finding in findings}
        expected = {"ML-REMOTE-CODE", "ML-TORCH-LOAD-DEFAULT", "ML-DYNAMIC-MODULE", "ML-AUTO-MAP"}
        missing = expected - rules
        if missing:
            print(f"self-test failed: missing {sorted(missing)}", file=sys.stderr)
            return 1
        if any(finding["file"].endswith("safe.py") for finding in findings):
            print("self-test failed: safe file produced findings", file=sys.stderr)
            return 1
        print(json.dumps({
            "self_test": "passed",
            "files_scanned": files,
            "findings": len(findings),
            "rules": sorted(rules),
        }, ensure_ascii=False, indent=2))
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan model loading trust boundaries")
    parser.add_argument("paths", nargs="*", help="files or directories to scan")
    parser.add_argument("--json", action="store_true", help="print JSON (default)")
    parser.add_argument("--self-test", action="store_true", help="run built-in fixture test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.paths:
        parser.print_help(sys.stderr)
        return 2

    roots = [Path(item).resolve() for item in args.paths]
    missing = [str(root) for root in roots if not root.exists()]
    if missing:
        print(f"path not found: {', '.join(missing)}", file=sys.stderr)
        return 2

    findings, files = scan_paths(roots, load_rules())
    findings.sort(key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["file"], item["line"]))
    result = {
        "skill": SKILL,
        "roots": [str(root) for root in roots],
        "files_scanned": files,
        "summary": summarize(findings),
        "findings": findings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
