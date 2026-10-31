#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "system.json"
SUPPORTED = {"zh", "en"}
DEFAULT = "zh"


def load():
    value = os.environ.get("MYGOLDMINE_LANG", "").strip().lower()
    if value in SUPPORTED:
        return value
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        value = str(data.get("language") or DEFAULT).strip().lower()
    except Exception:
        value = DEFAULT
    return value if value in SUPPORTED else DEFAULT


def save(language):
    language = str(language or "").strip().lower()
    if language not in SUPPORTED:
        raise ValueError(f"unsupported language: {language}")
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG.exists():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["language"] = language
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return language


def directive(language=None):
    language = language or load()
    if language == "en":
        return (
            "System language: English. All user-facing titles, summaries, impact, "
            "reachability notes, remediation and report prose must be written in English. "
            "Keep code, paths, commands, identifiers, CVE IDs and raw evidence unchanged. "
            "If the source material is in another language, translate the human-facing parts."
        )
    return (
        "系统语言：简体中文。所有面向人的标题、摘要、影响、可达性说明、修复建议和报告正文"
        "必须用简体中文。代码、路径、命令、标识符、CVE 编号和原始证据保持原样；"
        "英文原始标题保留在 title_en。"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", action="store_true")
    parser.add_argument("--set", dest="set_language", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--name", action="store_true")
    args = parser.parse_args()
    if args.set_language:
        language = save(args.set_language)
        print(json.dumps({"ok": True, "language": language}, ensure_ascii=False))
        return 0
    language = load()
    if args.prompt:
        print(directive(language))
    elif args.name:
        print("简体中文" if language == "zh" else "English")
    elif args.json:
        print(json.dumps({"language": language}, ensure_ascii=False))
    else:
        print(language)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
