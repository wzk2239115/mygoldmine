#!/usr/bin/env python3
"""校验运行镜像依赖清单，只允许清单内的普通 Python 包。"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def normalize(name):
    return name.lower().replace("_", "-")


def read_packages(path):
    packages = []
    errors = []
    for number, line_text in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line_text.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith(("-", "git+", "http://", "https://", "file:")):
            errors.append(f"第 {number} 行不是普通包声明: {line_text.strip()}")
            continue
        name = re.split(r"[\s<>=!~\[]", line, maxsplit=1)[0]
        if not PACKAGE.fullmatch(name):
            errors.append(f"第 {number} 行包名无效: {name}")
            continue
        if not re.fullmatch(
            (
                r"[A-Za-z0-9][A-Za-z0-9._-]*"
                r"(?:(?:~=|==|!=|<=|>=|<|>)[A-Za-z0-9.*+!_-]+"
                r"(?:,(?:~=|==|!=|<=|>=|<|>)[A-Za-z0-9.*+!_-]+)*)?"
            ),
            line,
        ):
            errors.append(f"第 {number} 行版本约束无效: {line_text.strip()}")
            continue
        packages.append(name)
    return packages, errors


def load_allowlist(path):
    names = set()
    for line_text in Path(path).read_text(encoding="utf-8").splitlines():
        line = line_text.split("#", 1)[0].strip()
        if line:
            names.add(normalize(line))
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", default=str(ROOT / "runner" / "requirements.txt"))
    parser.add_argument("--allowlist", default=str(ROOT / "runner" / "allowed-packages.txt"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    packages, errors = read_packages(args.requirements)
    allowed = load_allowlist(args.allowlist)
    for name in packages:
        if normalize(name) not in allowed:
            errors.append(f"不在允许清单中: {name}")
    result = {"ok": not errors, "packages": packages, "errors": errors}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        for error in errors:
            print(error, file=sys.stderr)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
