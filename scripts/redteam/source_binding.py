"""共同使用源码版本和无 Git 目录的内容摘要。"""
import hashlib
import json
import os
import subprocess
from pathlib import Path


def hash_source(source):
    digest = hashlib.sha256()
    paths = sorted(source.rglob("*"), key=lambda path: path.relative_to(source).as_posix())
    for path in paths:
        relative = path.relative_to(source)
        if ".git" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        if path.is_symlink():
            digest.update(b"link\0" + os.readlink(path).encode("utf-8") + b"\0")
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def source_binding(source, manifest):
    try:
        data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    except (OSError, ValueError):
        data = {}
    manifest_source = data.get("source")
    if data.get("commit") and manifest_source and Path(manifest_source).resolve() == source:
        return {"commit": str(data["commit"])}
    try:
        completed = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return {"commit": completed.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"content_sha256": hash_source(source)}
