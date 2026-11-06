#!/usr/bin/env python3
"""对生成和已有环境定义应用相同的有界下载缓存策略。"""

import re
import sys
from pathlib import Path


def apply(text):
    text = re.sub(r"\bdefault-jdk(?=[\s\\])", "default-jdk-headless", text)
    text = text.replace(
        "RUN apt-get update",
        "RUN --mount=type=cache,target=/var/cache/apt,sharing=locked "
        "--mount=type=cache,target=/var/lib/apt/lists,sharing=locked "
        "rm -f /etc/apt/apt.conf.d/docker-clean && apt-get update",
    )
    text = text.replace(
        "apt-get update", "apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=60 update"
    )
    text = text.replace(
        "apt-get install",
        "apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=60 "
        "-o Binary::apt::APT::Keep-Downloaded-Packages=true install",
    )
    if "--mount=type=cache,target=/var/lib/apt/lists" in text:
        text = text.replace("rm -rf /var/lib/apt/lists/*", "true")
    return text


if __name__ == "__main__":
    file = Path(sys.argv[1])
    file.write_text(apply(file.read_text()))
