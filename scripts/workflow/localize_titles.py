#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CJK = re.compile(r"[\u4e00-\u9fff]")
BASE_URL = os.environ.get("LOCALIZE_BASE_URL", "http://100.81.81.75:8081/v1").rstrip("/")
MODEL = os.environ.get("LOCALIZE_MODEL", "flint")


def reports(*, all_reports=False):
    found = defaultdict(list)
    for path in (ROOT / "runs").glob("*/*/audit-report.json"):
        found[path.parent.parent.name].append(path)
    if all_reports:
        return sorted(path for paths in found.values() for path in paths)
    return [max(paths, key=lambda item: item.parent.name) for paths in found.values()]


def findings_of(report):
    if isinstance(report.get("findings"), list):
        return report["findings"]
    if isinstance(report.get("vulnerabilities"), list):
        return report["vulnerabilities"]
    return []


def needs_localization(finding):
    title = str(finding.get("title") or "").strip()
    return bool(title) and not CJK.search(title)


def translate(batch):
    numbered = "\n".join(f"{index}. {item['title']}" for index, item in enumerate(batch))
    prompt = f"""把下面的英文安全漏洞标题翻译成简体中文。
要求：
1. 保留 HTTP 方法、路径、参数名、代码标识符、CVE/CWE、产品名等英文技术标识，不要翻译或改写它们。
2. 只翻译面向人的描述部分，标题要简洁、准确。
3. 只输出 JSON 数组，格式为 [{{"i":0,"title":"..."}}]，不要解释，不要 Markdown。

标题：
{numbered}"""
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000,
        "reasoning_effort": "none",
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"].get("content") or ""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    match = re.search(r"\[.*\]", content, flags=re.S)
    if not match:
        raise ValueError("model did not return a JSON array")
    rows = json.loads(match.group(0))
    result = {}
    for row in rows:
        index = int(row.get("i", -1))
        title = str(row.get("title") or "").strip()
        if 0 <= index < len(batch) and title and CJK.search(title):
            result[index] = title
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write translations back to reports")
    parser.add_argument("--all", action="store_true", help="scan all reports, not only latest per project")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--project", default="")
    args = parser.parse_args()

    targets = []
    for path in reports(all_reports=args.all):
        if args.project and path.parent.parent.name != args.project:
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"skip {path}: {exc}", file=sys.stderr)
            continue
        for finding in findings_of(report):
            if needs_localization(finding):
                targets.append((path, report, finding))
    if args.limit:
        targets = targets[: args.limit]
    if not targets:
        print("no titles need localization")
        return 0

    print(f"localizing {len(targets)} titles in {len({item[0] for item in targets})} reports", file=sys.stderr)
    changed = defaultdict(int)
    for start in range(0, len(targets), args.batch_size):
        batch = targets[start : start + args.batch_size]
        items = [{"title": finding["title"]} for _, _, finding in batch]
        try:
            translated = translate(items)
        except Exception as exc:
            print(f"batch {start} failed: {exc}", file=sys.stderr)
            continue
        for index, title in translated.items():
            path, report, finding = batch[index]
            original = str(finding.get("title") or "").strip()
            if not finding.get("title_en"):
                finding["title_en"] = original
            finding["title"] = title
            changed[path] += 1
        print(f"batch {start}-{start + len(batch) - 1}: {len(translated)} translated", file=sys.stderr)

    if args.write:
        for path, count in changed.items():
            report = json.loads(path.read_text(encoding="utf-8"))
            # Re-apply from the in-memory copies so the same finding objects are written.
            print(f"write {path} ({count})", file=sys.stderr)
        # The report objects are referenced by target tuples; dump each unique path once.
        by_path = {}
        for path, report, _ in targets:
            by_path[path] = report
        for path in changed:
            by_path[path].write_text(
                json.dumps(by_path[path], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    print(json.dumps({"targets": len(targets), "translated": sum(changed.values()), "written": bool(args.write)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
