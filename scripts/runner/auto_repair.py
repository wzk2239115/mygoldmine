#!/usr/bin/env python3
"""为宿主机上的红队执行准备受控依赖环境，不修改全局解释器。"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/stages"))
from claude_connection import claude_connection  # noqa: E402
from smoke_runner import DEFAULT_MODULES, run_checks  # noqa: E402
from validate_requirements import load_allowlist, normalize, read_packages  # noqa: E402

MODULE_PACKAGES = {
    "openai": "openai",
    "yaml": "PyYAML",
    "requests": "requests",
    "PIL": "Pillow",
    "tree_sitter": "tree-sitter",
    "tree_sitter_language_pack": "tree-sitter-language-pack",
}


def read(file):
    try:
        return json.loads(Path(file).read_text())
    except (OSError, ValueError):
        return {}


def write(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(file)


def command(argv, log, timeout=900, env=None):
    with Path(log).open("w") as stream:
        child = subprocess.Popen(
            argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
        )

        def stop_child(signum, frame):
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise SystemExit(128 + signum)

        previous = {sig: signal.signal(sig, stop_child) for sig in (signal.SIGTERM, signal.SIGINT)}
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            return 124
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def ensure_runner(python, output, model="", missing=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_file = output / "runner-repair.json"
    initial = run_checks(python, ["openai"], [])
    if initial["ok"] and not missing:
        result = {"status": "ready", "python": python, "repaired": False, "smoke": initial}
        write(result_file, result)
        return result
    missing = missing or [row["name"] for row in initial["modules"] if row["status"] != "ok"]
    result = {
        "status": "blocked",
        "error_scope": "harness_dependency",
        "retry_owner": "runner-environment",
        "missing_modules": missing,
        "original_python": python,
        "auto_retry": False,
    }
    requirements = ROOT / "runner/requirements.txt"
    allowed = load_allowlist(ROOT / "runner/allowed-packages.txt")
    packages, errors = read_packages(requirements)
    if errors or any(normalize(name) not in allowed for name in packages):
        result["reason"] = "运行依赖清单未通过校验"
        write(result_file, result)
        return result
    declared = {normalize(name) for name in packages}
    if any(
        name not in MODULE_PACKAGES or normalize(MODULE_PACKAGES[name]) not in declared
        for name in missing
    ):
        result["reason"] = "缺失模块未列入受控运行依赖，不自动安装"
        write(result_file, result)
        return result
    fingerprint = hashlib.sha256(
        (
            str(Path(python).resolve()) + requirements.read_text() + json.dumps(sorted(missing))
        ).encode()
    ).hexdigest()
    root = ROOT / "runs/runner-repairs"
    root.mkdir(parents=True, exist_ok=True)
    record = root / (fingerprint + ".json")
    # 进程锁合并不同候选和不同项目的相同修复，退出或异常后自动释放。
    with (root / "repair.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prior = read(record)
        if prior:
            if (
                prior.get("status") == "ready"
                and run_checks(prior["python"], list(DEFAULT_MODULES), ["claude --version"])["ok"]
            ):
                for name in ("agent.jsonl", "smoke.json"):
                    source = Path(prior["output"]) / name
                    if source.is_file():
                        shutil.copy2(source, output / name)
                write(result_file, prior)
                return prior
            result.update(
                reason="同一依赖故障已尝试修复，请检查既有记录后再解除限制", previous=str(record)
            )
            write(result_file, result)
            return result
        work = root / fingerprint
        work.mkdir(exist_ok=True)
        result.update(status="repairing", fingerprint=fingerprint, output=str(work))
        write(record, result)
        write(result_file, result)
        context = {
            **result,
            "execution_scope": "host_python",
            "stage": "redteam-agent",
            "requirements": str(requirements),
            "provisioning": "host-controlled isolated venv",
        }
        write(work / "context.json", context)
        try:
            selected_model, env = claude_connection(model)
            env.update(
                RUNNER_REPAIR_CONTEXT=str(work / "context.json"), RUNNER_OUTPUT_DIR=str(work)
            )
            prompt = (
                "这是宿主机运行依赖修复。读取运行修复上下文和技能说明，核对故障归属。"
                "本次仅允许读取并输出诊断；依赖安装和验收由调用方的确定性脚本执行。"
                "不要构建镜像，不改目标环境，不执行红队，不调用重排命令。"
                f"上下文：{work / 'context.json'}"
            )
            rc = command(
                [
                    os.environ.get("CLAUDE_BIN", "claude"),
                    "--setting-sources",
                    "project,local",
                    "--agent",
                    "runner-builder",
                    "--model",
                    selected_model,
                    "--tools",
                    "Read",
                    "--permission-mode",
                    "dontAsk",
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    "-p",
                    prompt,
                ],
                work / "agent.jsonl",
                timeout=180,
                env=env,
            )
            if rc:
                raise RuntimeError("修复智能体未正常结束")
            candidate = work / "venv"
            candidate_python = str(candidate / "bin/python")
            if command([python, "-m", "venv", str(candidate)], work / "venv.log", 120):
                raise RuntimeError("无法建立独立运行环境")
            if command(
                [
                    candidate_python,
                    "-m",
                    "pip",
                    "--isolated",
                    "install",
                    "--index-url",
                    "https://pypi.org/simple",
                    "--retries",
                    "1",
                    "--timeout",
                    "60",
                    "-r",
                    str(requirements),
                ],
                work / "install.log",
                900,
            ):
                raise RuntimeError("受控依赖安装失败")
            smoke = run_checks(candidate_python, list(DEFAULT_MODULES), ["claude --version"])
            write(work / "smoke.json", smoke)
            if not smoke["ok"]:
                raise RuntimeError("新运行环境未通过冒烟验收")
            result.update(
                status="ready",
                python=candidate_python,
                repaired=True,
                smoke=smoke,
                auto_retry=True,
                requeue=["redteam-agent"],
            )
        except (OSError, RuntimeError) as exc:
            result.update(status="blocked", reason=str(exc))
        write(record, result)
        for name in ("agent.jsonl", "venv.log", "install.log", "smoke.json"):
            source = work / name
            if source.is_file():
                shutil.copy2(source, output / name)
        write(result_file, result)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--execute-agent", action="store_true")
    args, agent_args = parser.parse_known_args()
    if agent_args and not args.execute_agent:
        parser.error("未知参数")
    result = ensure_runner(args.python, args.output, args.model)
    if result["status"] != "ready":
        print(json.dumps(result, ensure_ascii=False))
        return 78
    if not args.execute_agent:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    agent_args = agent_args[1:] if agent_args[:1] == ["--"] else agent_args
    output = Path(args.output)
    # 只运行固定红队入口；保留第一次启动失败的原始日志，不执行任意外部命令。
    argv = [result["python"], str(ROOT / "scripts/redteam/agent.py"), *agent_args]
    rc = command(argv, output / "execution-first.log", 7200)
    log = (output / "execution-first.log").read_text(errors="replace")
    match = re.search(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)", log)
    if rc and match and not result.get("repaired"):
        result = ensure_runner(
            args.python, output / "runtime-repair", args.model, missing=[match[1].split(".")[0]]
        )
        if result["status"] == "ready":
            rc = command([result["python"], *argv[1:]], output / "execution-retry.log", 7200)
            log = (output / "execution-retry.log").read_text(errors="replace")
        else:
            rc = 78
    write(output / "execution.json", {"returncode": rc, "runner": result})
    print(log[-65536:])
    return rc


if __name__ == "__main__":
    sys.exit(main())
