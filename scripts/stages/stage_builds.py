"""Persistent image builds owned by one isolated stage output directory."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = {
    "type": "object",
    "properties": {
        "dockerfile": {"type": "string"},
        "context": {"type": "string"},
        "image": {"type": "string"},
        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
    },
    "required": ["dockerfile", "context", "image"],
    "additionalProperties": False,
}


def start_build(stage, root, arguments):
    if stage != "redteam-lab" or os.environ.get("STAGE_BUILD_VERIFY_ONLY"):
        raise ValueError("当前阶段只允许验收，不能启动镜像构建")
    root = Path(root).resolve()
    task = json.loads((root / "lab-task.json").read_text())
    dockerfile = Path(arguments["dockerfile"]).resolve(strict=True)
    context = Path(arguments["context"]).resolve(strict=True)
    source = Path(task["source"]).resolve(strict=True)
    if not dockerfile.is_relative_to(root) or not dockerfile.is_file():
        raise ValueError("Dockerfile 必须位于当前场景目录")
    if not context.is_dir() or not (context.is_relative_to(root) or context.is_relative_to(source)):
        raise ValueError("构建上下文只能使用本场景或登记的源码目录")
    image = arguments["image"]
    if (
        not isinstance(image, str)
        or not image
        or image.startswith("-")
        or any(character.isspace() for character in image)
    ):
        raise ValueError("镜像名称无效")
    remaining = int(task.get("build_deadline", time.time() + 1200) - time.time())
    timeout = min(int(arguments.get("timeout_seconds", 1200)), remaining, 3600)
    if timeout < 1:
        raise ValueError("场景构建时间预算已耗尽")
    inputs = {
        "dockerfile": str(dockerfile),
        "sha256": hashlib.sha256(dockerfile.read_bytes()).hexdigest(),
        "context": str(context),
        "image": image,
    }
    identifier = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:24]
    parent = root / ".stage-builds"
    parent.mkdir(exist_ok=True)
    for file in parent.glob("*/task.json"):
        existing = json.loads(file.read_text())
        if existing.get("image") == image and existing.get("status") in ("queued", "running"):
            return {"status": existing["status"], "task_file": str(file), "reused": True}
    spec = {
        "program": "docker",
        "args": ["build", "-f", str(dockerfile), "-t", image, str(context)],
        "cwd": str(root),
        "image": image,
        "timeoutMs": timeout * 1000,
        "successCodes": [0],
        "envFlags": {},
        "owner": os.environ.get("ENV_BUILD_TASK_OWNER", str(root)),
    }
    result = subprocess.run(
        [
            os.environ.get("NODE_BIN", "node"),
            str(ROOT / "ui/server/durable-task.mjs"),
            "--start-spec",
            str(parent / identifier),
            json.dumps(spec),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    data = json.loads(result.stdout)
    return {
        "status": data["status"],
        "task_file": data["file"],
        "output": str(parent / identifier / "output.log"),
    }


def wait_builds(root):
    results = []
    # Only the latest attempt for each image decides readiness; failed attempts stay on disk.
    latest = {}
    for file in (Path(root) / ".stage-builds").glob("*/task.json"):
        value = json.loads(file.read_text())
        key = value.get("image", str(file))
        if key not in latest or value["startedAt"] > latest[key][1]["startedAt"]:
            latest[key] = (file, value)
    for file, value in latest.values():
        result = subprocess.run(
            [
                os.environ.get("NODE_BIN", "node"),
                str(ROOT / "ui/server/durable-task.mjs"),
                "--wait-task",
                str(file),
            ],
            capture_output=True,
            text=True,
            timeout=value["timeoutMs"] / 1000 + 30,
        )
        if not result.stdout.strip():
            raise ValueError("场景构建任务缺少实际终态")
        results.append(json.loads(result.stdout))
    return results
