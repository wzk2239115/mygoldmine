#!/usr/bin/env python3
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_DIFF = 2_000_000

SEVERITY_SCORE = {"critical": 45, "high": 25, "medium": 10, "low": 4}
INSTALL_SURFACE = re.compile(
    r"(^|/)(setup\.py|setup\.cfg|pyproject\.toml|package\.json|Makefile|Dockerfile|"
    r"build\.sh|install\.sh|requirements[^/]*\.txt|\.github/workflows/|\.gitlab-ci\.yml|"
    r"postinstall|preinstall|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|"
    r"package-lock\.json|Cargo\.toml|Cargo\.lock|go\.mod|go\.sum)$",
    re.I,
)
BINARY_EXT = re.compile(r"\.(so|dll|dylib|exe|node|wasm|bin|dat|jar|class|pyc)$", re.I)
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
NETWORK = re.compile(
    r"(curl|wget|Invoke-WebRequest|iwr|http[s]?://|requests\.|urllib|fetch\()", re.I
)
SENSITIVE = re.compile(
    r"(\.ssh/|\.aws/|credentials|\.npmrc|\.pypirc|GITHUB_TOKEN|NPM_TOKEN|"
    r"ANTHROPIC|OPENAI_API_KEY|process\.env|os\.environ|printenv|env\b)",
    re.I,
)
REMOTE_EXEC = re.compile(
    r"(curl[^\n|]{0,200}\|\s*(ba)?sh|wget[^\n|]{0,200}\|\s*(ba)?sh|"
    r"bash\s*<\(\s*curl|iwr[^\n]{0,200}\|\s*iex|Invoke-Expression|"
    r"python[^\n]{0,80}-c\s*['\"][^'\"]*(base64|exec|eval)|"
    r"eval\s*\(\s*(atob|base64)|child_process\.(exec|spawn)|os\.system\s*\(|"
    r"subprocess\.[A-Za-z_]+\([^\n]{0,160}shell\s*=\s*True)",
    re.I,
)
ENCODED = re.compile(
    r"(base64\s+(-d|--decode)|atob\s*\(|bytes\.fromhex|fromhex\(|"
    r"codecs\.decode\([^\n]{0,80}base64|[A-Za-z0-9+/]{200,}={0,2})",
)
DEP_SOURCE = re.compile(
    r"(https?://[^\s\"']+|git\+https?://|file:\.\./|--index-url\s+http://|"
    r"--registry\s+http://|--extra-index-url\s+http://)",
    re.I,
)
CI_DANGER = re.compile(
    r"(pull_request_target|permissions\s*:\s*write-all|secrets\.[A-Za-z_]+|"
    r"curl[^\n]{0,160}\|\s*(ba)?sh|actions/checkout@[^\n]{0,80}ref\s*:\s*\$\{\{\s*github\.event\.pull_request)",
    re.I,
)
CONFIG_INJECT = re.compile(
    r"(NODE_OPTIONS|PYTHONPATH|LD_PRELOAD|DYLD_|PATH\s*=.*(curl|wget|/tmp)|"
    r"alias\s+(curl|wget)|export\s+(http_proxy|https_proxy|HTTP_PROXY|HTTPS_PROXY))",
    re.I,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def git(repo, args, timeout=60):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def head_sha(repo):
    completed = git(repo, ["rev-parse", "HEAD"])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git rev-parse failed")
    return completed.stdout.strip()


def is_ancestor(repo, ancestor, descendant):
    if not ancestor:
        return True
    completed = git(repo, ["merge-base", "--is-ancestor", ancestor, descendant])
    return completed.returncode == 0


def commit_meta(repo, sha):
    fmt = "%H%x00%P%x00%an%x00%ae%x00%aI%x00%s"
    completed = git(repo, ["show", "-s", f"--format={fmt}", sha])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())
    parts = completed.stdout.rstrip("\n").split("\x00")
    while len(parts) < 6:
        parts.append("")
    return {
        "sha": parts[0],
        "parent": parts[1].split()[0] if parts[1] else "",
        "author": parts[2],
        "email": parts[3],
        "committed_at": parts[4],
        "subject": parts[5],
    }


def commit_diff(repo, sha):
    completed = git(repo, ["show", "--no-color", "--no-renames", "--unified=3", "--format=", sha])
    diff = completed.stdout or ""
    return diff[:MAX_DIFF], len(diff) > MAX_DIFF


def commit_stat(repo, sha):
    completed = git(repo, ["show", "--no-color", "--numstat", "--format=", sha])
    files, added, removed = [], 0, 0
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        files.append(path)
        if a.isdigit():
            added += int(a)
        if d.isdigit():
            removed += int(d)
    return {"files": files, "added": added, "removed": removed}


def parse_diff(diff):
    files = []
    added = []
    removed = []
    binary = []
    modes = []
    current = None
    new_line = 0
    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            match = re.match(r"diff --git a/(.*?) b/(.*)$", raw)
            current = match.group(2) if match else raw[11:]
            continue
        if raw.startswith("new file mode "):
            modes.append({"path": current, "mode": raw.split()[-1], "kind": "new"})
            continue
        if raw.startswith("old mode ") or raw.startswith("new mode "):
            modes.append({"path": current, "mode": raw.split()[-1], "kind": "mode"})
            continue
        if raw.startswith("deleted file mode "):
            modes.append({"path": current, "mode": raw.split()[-1], "kind": "deleted"})
            continue
        if raw.startswith("Binary files ") or raw.startswith("GIT binary patch"):
            binary.append(current)
            continue
        if raw.startswith("+++ b/"):
            current = raw[6:]
            if current not in files:
                files.append(current)
            continue
        if raw.startswith("+++ /dev/null"):
            current = None
            continue
        match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if match:
            new_line = int(match.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append({"path": current, "line": new_line, "text": raw[1:]})
            new_line += 1
            continue
        if raw.startswith("-") and not raw.startswith("---"):
            removed.append({"path": current, "line": 0, "text": raw[1:]})
            continue
        new_line += 1
    return {
        "files": files,
        "added": added,
        "removed": removed,
        "binary": [p for p in binary if p],
        "modes": modes,
    }


def add_finding(findings, rule_id, severity, path, line, text, why):
    key = (rule_id, path or "")
    for item in findings:
        if (item["rule"], item["path"] or "") == key:
            if len(item["evidence"]) < 3:
                item["evidence"].append({"line": line, "text": text.strip()[:300]})
            return
    findings.append(
        {
            "rule": rule_id,
            "severity": severity,
            "path": path or "",
            "why": why,
            "evidence": [{"line": line, "text": text.strip()[:300]}],
        }
    )


def analyze(repo, sha):
    meta = commit_meta(repo, sha)
    diff, truncated = commit_diff(repo, sha)
    stat = commit_stat(repo, sha)
    parsed = parse_diff(diff)
    findings = []

    for line in parsed["added"]:
        text = line["text"]
        path = line["path"] or ""
        if REMOTE_EXEC.search(text):
            add_finding(
                findings,
                "remote-code-exec",
                "critical",
                path,
                line["line"],
                text,
                "新增行包含下载即执行、shell/eval 或未加约束的子进程调用",
            )
        if ENCODED.search(text):
            add_finding(
                findings,
                "encoded-payload",
                "high",
                path,
                line["line"],
                text,
                "新增行包含 base64/hex/atob 解码或高熵长串",
            )
        if CI_DANGER.search(text) and (
            ".github/workflows/" in path or path.endswith(".gitlab-ci.yml")
        ):
            add_finding(
                findings,
                "ci-privilege-abuse",
                "critical",
                path,
                line["line"],
                text,
                "CI 配置引入 pull_request_target、写权限或 secret 暴露面",
            )
        if DEP_SOURCE.search(text) and re.search(
            r"(install|dependency|dependencies|registry|index-url)", text, re.I
        ):
            add_finding(
                findings,
                "dependency-source-change",
                "high",
                path,
                line["line"],
                text,
                "依赖安装指向非默认 HTTP/git/file 源",
            )
        if CONFIG_INJECT.search(text):
            add_finding(
                findings,
                "env-injection",
                "high",
                path,
                line["line"],
                text,
                "新增行修改 PATH/LD_PRELOAD/NODE_OPTIONS/代理等执行环境",
            )
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                add_finding(
                    findings,
                    "secret-material",
                    "high",
                    path,
                    line["line"],
                    text,
                    "新增行疑似写入密钥或私钥材料",
                )
                break
        if NETWORK.search(text) and SENSITIVE.search(text):
            add_finding(
                findings,
                "credential-exfil",
                "critical",
                path,
                line["line"],
                text,
                "新增行同时出现外联与凭据/环境变量读取",
            )

    for mode in parsed["modes"]:
        if mode["kind"] == "new" and mode.get("mode") == "100755":
            add_finding(
                findings, "executable-drop", "high", mode.get("path"), 0, "", "新增可执行位文件"
            )
    for path in parsed["binary"]:
        add_finding(
            findings, "binary-change", "high", path, 0, "", "二进制文件变更，无法从 diff 直接审查"
        )
    for path in parsed["files"]:
        if BINARY_EXT.search(path):
            add_finding(findings, "binary-file", "high", path, 0, "", "变更包含可执行/二进制扩展名")

    for path in stat["files"]:
        if INSTALL_SURFACE.search(path):
            add_finding(
                findings, "install-surface", "medium", path, 0, "", "构建/安装/CI 入口被修改"
            )
            break

    if len(parsed["modes"]) >= 10 or len(stat["files"]) >= 40:
        add_finding(
            findings,
            "wide-change",
            "medium",
            "",
            0,
            "",
            f"单次提交触及 {len(stat['files'])} 个文件，建议人工复核范围",
        )
    if stat["removed"] >= 2000:
        add_finding(
            findings, "mass-delete", "medium", "", 0, "", f"单次提交删除 {stat['removed']} 行"
        )
    if truncated:
        add_finding(
            findings,
            "truncated-diff",
            "medium",
            "",
            0,
            "",
            "diff 超过审查上限，已截断，需人工查看完整提交",
        )

    dedup = {}
    for item in findings:
        dedup[item["rule"]] = max(dedup.get(item["rule"], 0), SEVERITY_SCORE[item["severity"]])
    score = min(100, sum(dedup.values()))
    if score >= 60:
        verdict = "critical"
    elif score >= 30:
        verdict = "high"
    elif score >= 12:
        verdict = "review"
    else:
        verdict = "low"
    return {
        "project": Path(repo).name,
        "sha": meta["sha"],
        "parent": meta["parent"],
        "subject": meta["subject"],
        "author": f"{meta['author']} <{meta['email']}>",
        "committed_at": meta["committed_at"],
        "kind": "commit",
        "score": score,
        "verdict": verdict,
        "summary": meta["subject"],
        "findings": findings,
        "stat": stat,
        "truncated": truncated,
        "analyzed_at": now(),
    }


def render_markdown(report):
    lines = [
        f"# Update provenance: {report['project']}",
        "",
        f"- commit: `{report['sha']}`",
        f"- parent: `{report['parent'] or '-'}`",
        f"- author: {report['author']}",
        f"- date: {report['committed_at']}",
        f"- subject: {report['subject']}",
        f"- verdict: **{report['verdict']}** (score {report['score']})",
        f"- files: {len(report['stat']['files'])}  "
        f"+{report['stat']['added']} / -{report['stat']['removed']}",
        "",
    ]
    if not report["findings"]:
        lines += [
            "## Findings",
            "",
            "No high-signal change detected by the static provenance rules.",
            "",
        ]
    else:
        lines += ["## Findings", ""]
        for item in report["findings"]:
            lines.append(f"### {item['severity'].upper()}: {item['rule']}")
            lines.append("")
            lines.append(f"- path: `{item['path'] or '-'}`")
            lines.append(f"- why: {item['why']}")
            for evidence in item["evidence"]:
                text = evidence["text"].replace("`", "'")
                lines.append(f"- line {evidence['line']}: `{text}`")
            lines.append("")
    lines += [
        "## Recommended action",
        "",
        "- critical/high: inspect the diff, then run a focused audit or lab "
        "validation before merging.",
        "- review: confirm the build/install/CI change is expected.",
        "- low: no action beyond normal review.",
        "",
        "_Generated by `scripts/watch/watch.py`; this is a triage signal, "
        "not a vulnerability conclusion._",
        "",
    ]
    return "\n".join(lines)


def write_report(report, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{report['sha'][:12]}.json"
    md_path = out_dir / f"{report['sha'][:12]}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
