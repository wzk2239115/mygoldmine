#!/usr/bin/env python3
"""只读查询基础镜像发行版、架构与本地软件源候选；不联网安装。"""

import argparse
import json
import re
import subprocess


def inspect(image, packages, runner=subprocess.run):
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", name) for name in packages):
        raise ValueError("软件包名称无效")
    script = (
        "cat /etc/os-release; echo __ARCH__; dpkg --print-architecture; "
        "echo __PACKAGES__; "
        "if test -n \"$(find /var/lib/apt/lists -name '*Packages*' -print -quit)\"; "
        "then echo indexes=present; else echo indexes=missing; fi; "
        'for package do echo "PACKAGE=$package"; apt-cache policy "$package"; done'
    )
    result = runner(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--entrypoint",
            "/bin/sh",
            image,
            "-c",
            script,
            "preflight",
            *packages,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        return {
            "status": "unavailable",
            "limitations": ["基础镜像预检失败"],
            "exit_code": result.returncode,
        }
    os_info, tail = result.stdout.split("__ARCH__", 1)
    architecture, package_info = tail.split("__PACKAGES__", 1)
    indexes = "indexes=present" in package_info
    rows = []
    for section in package_info.split("PACKAGE=")[1:]:
        lines = section.splitlines()
        candidate = next(
            (
                line.split(":", 1)[1].strip()
                for line in lines
                if line.strip().startswith("Candidate:")
            ),
            None,
        )
        rows.append(
            {
                "package": lines[0],
                "candidate": candidate,
                "status": "available"
                if candidate and candidate != "(none)"
                else "unavailable"
                if indexes
                else "unknown",
            }
        )
    return {
        "status": "blocked" if any(x["status"] == "unavailable" for x in rows) else "inspected",
        "os_release": os_info.strip(),
        "architecture": architecture.strip(),
        "packages": rows,
        "limitations": []
        if indexes
        else ["基础镜像没有软件源索引，候选版本未知；不得据此声称软件包可用。"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="基础镜像只读工具链预检")
    parser.add_argument("--image", required=True)
    parser.add_argument("--packages", nargs="*", default=[])
    args = parser.parse_args()
    print(json.dumps(inspect(args.image, args.packages), ensure_ascii=False, indent=2))
