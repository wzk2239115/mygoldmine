#!/usr/bin/env python3
"""检查运行镜像中的 Python 模块和命令，不执行目标项目代码。"""
import argparse
import json
import shlex
import subprocess
import sys

DEFAULT_MODULES = (
    "openai",
    "yaml",
    "requests",
    "PIL",
    "tree_sitter",
    "tree_sitter_language_pack",
)


def check_module(python, name):
    command = [python, "-c", f"import {name}"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "status": "error", "error": str(exc)}
    if completed.returncode == 0:
        return {"name": name, "status": "ok"}
    return {
        "name": name,
        "status": "missing" if "ModuleNotFoundError" in completed.stderr else "error",
        "error": (completed.stderr or completed.stdout).strip()[-1200:],
    }


def check_command(command):
    parts = shlex.split(command)
    try:
        completed = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "status": "error", "error": str(exc)}
    if completed.returncode == 0:
        return {
            "command": command,
            "status": "ok",
            "stdout": (completed.stdout or "").strip()[-500:],
        }
    return {
        "command": command,
        "status": "error",
        "error": (completed.stderr or completed.stdout).strip()[-1200:],
    }


def run_checks(python, modules, commands):
    module_results = [check_module(python, name) for name in modules]
    command_results = [check_command(command) for command in commands]
    ok = all(item["status"] == "ok" for item in module_results + command_results)
    return {
        "ok": ok,
        "python": python,
        "modules": module_results,
        "commands": command_results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--command", action="append", default=[])
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    modules = args.module or list(DEFAULT_MODULES)
    result = run_checks(args.python, modules, args.command)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["modules"]:
            print(f"module {item['name']}: {item['status']}")
        for item in result["commands"]:
            print(f"command {item['command']}: {item['status']}")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
