#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

def claude_connection(model, environ=None):
    """为各阶段统一配置 Claude 兼容服务、模型和鉴权。"""
    env = dict(os.environ if environ is None else environ)
    model = model or env.get("ANTHROPIC_MODEL") or "360-proxy/deepseek/deepseek-v4.1-flash"
    for prefix in ("360-proxy/", "opencode/"):
        if model.startswith(prefix):
            model = model[len(prefix):]
            break
    env["ANTHROPIC_BASE_URL"] = env.get("ANTHROPIC_BASE_URL") or env.get("GLM_ANTHROPIC_BASE") or "https://api.360.cn"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    if not (env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")):
        token = env.get("GLM_API_KEY", "")
        if not token:
            config = Path(env.get("OPENCODE_CONFIG") or str(Path.home() / ".config/opencode/opencode.json"))
            if config.exists():
                token = json.loads(config.read_text()).get("provider", {}).get("360-proxy", {}).get("options", {}).get("apiKey", "")
        if token:
            env["ANTHROPIC_AUTH_TOKEN"] = token
    if model:
        for key in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            env[key] = model
    return model, env


def main():
    # 用法：python3 claude_connection.py MODEL CLAUDE [参数...]。
    if len(sys.argv) < 3:
        raise SystemExit("缺少模型或 Claude 命令")
    model, env = claude_connection(sys.argv[1])
    command = sys.argv[2:]
    if "--model" in command:
        command[command.index("--model") + 1] = model
    else:
        command += ["--model", model]
    os.execvpe(command[0], [command[0], "--setting-sources", "project,local", *command[1:]], env)


if __name__ == "__main__":
    main()
