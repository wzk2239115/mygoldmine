#!/usr/bin/env python3
"""Require model-started Docker builds to use the durable build entry point."""

import json
import re
import sys

request = json.load(sys.stdin)
command = request.get("tool_input", {}).get("command", "")
if re.search(r"\bdocker\s+(?:build\b|buildx\s+build\b)", command):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "请使用本阶段的持久构建入口：环境节点用 build_env.sh，"
                        "场景节点用 start_stage_build；"
                        "不要直接启动依附于模型会话的 Docker 构建。"
                    ),
                }
            },
            ensure_ascii=False,
        )
    )
