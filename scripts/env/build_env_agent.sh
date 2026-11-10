#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SKILL_FILE="${ENV_BUILDER_SKILL_FILE:-}"
PROJECT="${ENV_BUILD_PROJECT:-}"
SOURCE="${ENV_BUILD_REPO:-}"
COMMIT="${ENV_BUILD_COMMIT:-}"
MODE="${ENV_BUILD_MODE:-auto}"
OUT_DIR="${ENV_BUILD_OUT_DIR:-}"
BASE_IMAGE="${ENV_BUILD_BASE_IMAGE:-mygoldmine:dev}"
BUILD_TIMEOUT="${ENV_BUILD_TIMEOUT:-3600}"
NETWORK="${ENV_BUILD_NETWORK:-default}"
MODEL="${ENV_BUILD_MODEL:-}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

if [ -z "$SKILL_FILE" ] || [ ! -f "$SKILL_FILE" ]; then
    echo "[build_env_agent] missing ENV_BUILDER_SKILL_FILE" >&2
    exit 2
fi
if [ -z "$SOURCE" ] || [ ! -d "$SOURCE" ]; then
    echo "[build_env_agent] missing ENV_BUILD_REPO: $SOURCE" >&2
    exit 2
fi
if [ -z "$OUT_DIR" ]; then
    echo "[build_env_agent] missing ENV_BUILD_OUT_DIR" >&2
    exit 2
fi
if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
    echo "[build_env_agent] claude CLI not found: $CLAUDE_BIN" >&2
    exit 4
fi

SOURCE="$(realpath "$SOURCE")"
OUT_DIR="$(realpath -m "$OUT_DIR")"
case "$MODEL" in
    360-proxy/*) MODEL="${MODEL#360-proxy/}" ;;
    opencode/*) MODEL="${MODEL#opencode/}" ;;
esac
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${GLM_ANTHROPIC_BASE:-https://api.360.cn}}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
if [ -n "$MODEL" ]; then
    export ANTHROPIC_MODEL="$MODEL"
    export ANTHROPIC_DEFAULT_OPUS_MODEL="$MODEL"
    export ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL"
    export ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL"
    export ANTHROPIC_SMALL_FAST_MODEL="$MODEL"
    export CLAUDE_CODE_SUBAGENT_MODEL="$MODEL"
fi
if [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    if [ -n "${GLM_API_KEY:-}" ]; then
        export ANTHROPIC_AUTH_TOKEN="$GLM_API_KEY"
    else
        OPENCODE_CFG="${OPENCODE_CONFIG:-$HOME/.config/opencode/opencode.json}"
        if [ -f "$OPENCODE_CFG" ] && command -v jq >/dev/null 2>&1; then
            AUTH_VALUE="$(jq -r '.provider["360-proxy"].options.apiKey // empty' "$OPENCODE_CFG" 2>/dev/null)"
            [ -z "$AUTH_VALUE" ] || export ANTHROPIC_AUTH_TOKEN="$AUTH_VALUE"
        fi
    fi
fi
mkdir -p "$OUT_DIR"
cd "$REPO_ROOT"

LANGUAGE_DIRECTIVE="$(python3 "$REPO_ROOT/scripts/config/language.py" --prompt 2>/dev/null || true)"
PROMPT="${LANGUAGE_DIRECTIVE}

Build a reproducible Docker environment for the source below.

project: ${PROJECT}
source: ${SOURCE}
commit: ${COMMIT}
mode: ${MODE}
env_dir: ${OUT_DIR}
base_image: ${BASE_IMAGE}
build_timeout_seconds: ${BUILD_TIMEOUT}
docker_network: ${NETWORK}

本轮默认最小目标是指定源码可读、Python 可运行和隔离边界成立，不要求完整训练、GPU 或模型加载。
先验收已有匹配镜像；源码级能力已满足时可诚实交付 partial，列出未验证的导入与训练能力。
不要为未出现的具体验证需求安装整套 torch、Ray 或 transformers；需要额外能力时由后续候选的隔离环境按证据补齐。
You own detection, build decisions, failure diagnosis, repair and runtime checks.
Use scripts/env/build_env.sh as a build tool with --env-dir ${OUT_DIR}, not as a
substitute for your own inspection and decisions. Do not stop after a dry-run.
Do not fake ready. Finish by writing ${OUT_DIR}/env-manifest.json with an honest
env_status after an actual build, verified reuse, or an explicit blocked result."

CLAUDE_ARGS=(
    --mcp-config "$(python3 "$REPO_ROOT/scripts/stages/submission.py" config --stage environment --root "$OUT_DIR")"
    --agent environment-builder
    --setting-sources project,local
    --output-format stream-json
    --verbose
    --permission-mode=bypassPermissions
    --disallowed-tools WebSearch,WebFetch
    --append-system-prompt "$(cat "$SKILL_FILE")
$(python3 "$REPO_ROOT/scripts/stages/submission.py" instruction --stage environment --root "$OUT_DIR")"
)
[ -n "$MODEL" ] && CLAUDE_ARGS+=(--model "$MODEL")
delivery_started="$(date +%s)"
accepted_delivery() {
    python3 - "$OUT_DIR" "$delivery_started" <<'PYDELIVERY'
import hashlib
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
manifest = root / "env-manifest.json"
if not manifest.is_file():
    raise SystemExit(1)
digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
for path in (root / ".stage-submissions/environment").glob("*.json"):
    try:
        value = json.loads(path.read_text())
        if (path.stat().st_mtime >= float(sys.argv[2])
                and value.get("decision") == "accepted"
                and value.get("sha256") == digest):
            raise SystemExit(0)
    except (OSError, ValueError):
        continue
raise SystemExit(1)
PYDELIVERY
}
export ENV_BUILD_DURABLE=1
export ENV_BUILD_TASK_OWNER="${ENV_BUILD_TASK_OWNER:-${GOLDMINE_DURABLE_TASK:-$OUT_DIR}}"
set +e
timeout --signal=TERM --kill-after=15 "${ENV_BUILD_AGENT_TIMEOUT:-1800}" "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}" -p "$PROMPT"
agent_rc=$?
# A headless session may end before a background task. The build remains owned here.
if [ -f "$OUT_DIR/.build-tasks/current.json" ]; then
    "${NODE_BIN:-node}" "$REPO_ROOT/ui/server/durable-task.mjs" --wait-build "$OUT_DIR"
    build_rc=$?
    if accepted_delivery; then exit 0; fi
    # Continue with a bounded acceptance session; it cannot launch another build.
    export ENV_BUILD_VERIFY_ONLY=1
    timeout --signal=TERM --kill-after=15 300 "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}" -p "${LANGUAGE_DIRECTIVE}
当前构建任务已经结束（退出码=$build_rc）。仅执行环境验收，不再安装依赖、不修改 Dockerfile、不重建。
项目=$PROJECT，源码=$SOURCE，输出目录=$OUT_DIR。
读取 .build-tasks/current.json 指向的真实结果与 env-manifest.json，核对实际镜像及源码，执行必要的最小断网验收，记录未验证的能力和失败。
partial 是有效的有限能力交付，不要求训练或 GPU 路径就不要扩大目标。
调用 mcp__stage_delivery__submit_environment 提交真实环境状态、验收记录和限制，由工具生成正式清单，返回真实状态；如果没有可用环境，如实报告受阻。"
    agent_rc=$?
fi
if ! accepted_delivery; then
    echo '[build_env_agent] 缺少本次清单对应的有效交付回执，不能把会话结束当成验收完成' >&2
    exit 6
fi
exit 0
